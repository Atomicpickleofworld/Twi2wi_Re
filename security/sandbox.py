# security/sandbox.py
"""
Менеджер песочницы плагинов.

Новые коллбэки:
    on_register_tab(plugin_id, title, icon, html)  — плагин хочет вкладку
    on_style_patch(plugin_id, css)                 — плагин применяет CSS-патч
"""

from __future__ import annotations

import json
import logging
import queue
import subprocess
import sys
import threading
import time
import zipfile
import hashlib
import shutil
from pathlib import Path
from typing import Callable

from PyQt6.QtWidgets import QApplication

from security.permissions import PluginPermissions, validate_manifest

logger = logging.getLogger(__name__)


# ── Загрузка и верификация ZIP ───────────────────────────────────────────────

class PluginLoadError(Exception):
    pass


def install_plugin_from_zip(zip_path: Path, plugins_root: Path) -> Path:
    plugins_root.mkdir(parents=True, exist_ok=True)

    if not zipfile.is_zipfile(zip_path):
        raise PluginLoadError(f"Файл '{zip_path}' не является ZIP-архивом.")

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()

        for name in names:
            if ".." in name or name.startswith("/") or name.startswith("\\"):
                raise PluginLoadError(f"Архив содержит опасный путь: '{name}' (zip-slip атака).")

        if "plugin.json" not in names:
            raise PluginLoadError("Архив не содержит plugin.json в корне.")

        manifest_raw = zf.read("plugin.json")
        try:
            manifest = json.loads(manifest_raw)
        except json.JSONDecodeError as e:
            raise PluginLoadError(f"plugin.json невалиден: {e}")

        errors = validate_manifest(manifest)
        if errors:
            raise PluginLoadError("Ошибки в plugin.json:\n" + "\n".join(errors))

        plugin_id = manifest["id"]
        entry     = manifest["entry"]

        if entry not in names:
            raise PluginLoadError(f"Файл точки входа '{entry}' не найден в архиве.")

        allowed_extensions = {".py", ".json", ".txt", ".md", ".png", ".svg"}
        for name in names:
            suffix = Path(name).suffix.lower()
            if suffix and suffix not in allowed_extensions:
                raise PluginLoadError(
                    f"Архив содержит недопустимый тип файла: '{name}'. "
                    f"Разрешены: {', '.join(sorted(allowed_extensions))}"
                )

        target_dir = plugins_root / plugin_id
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True)
        zf.extractall(target_dir)

    logger.info(f"Плагин '{plugin_id}' установлен в {target_dir}")
    return target_dir


def compute_file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ── Класс песочницы ──────────────────────────────────────────────────────────

class PluginSandbox:
    """Управляет одним плагином в отдельном subprocess."""

    def __init__(
        self,
        plugin_dir: Path,
        on_log: Callable[[str], None] | None = None,
        on_notify: Callable[[str], None] | None = None,
        on_register_tab: Callable[[str, str, str, str], None] | None = None,
        on_style_patch: Callable[[str, str], None] | None = None,
    ):
        self.plugin_dir = plugin_dir.resolve()
        self.on_log = on_log or (lambda msg: logger.info(f"[plugin] {msg}"))
        self.on_notify = on_notify or (lambda msg: None)
        # on_register_tab(plugin_id, title, icon, html)
        self.on_register_tab = on_register_tab or (lambda *a: None)
        # on_style_patch(plugin_id, css)
        self.on_style_patch = on_style_patch or (lambda *a: None)

        self._process: subprocess.Popen | None = None
        self._reader_thread: threading.Thread | None = None
        self._response_queue: queue.Queue = queue.Queue()

        self.manifest: dict = {}
        self.permissions: PluginPermissions | None = None
        self._entry: str = "main.py"
        self._ready = False
        self._lock = threading.Lock()
        self._file_hashes: dict[str, str] = {}

    # ── Загрузка ─────────────────────────────────────────────────────────────

    def load(self) -> None:
        manifest_path = self.plugin_dir / "plugin.json"
        if not manifest_path.exists():
            raise PluginLoadError(f"plugin.json не найден в {self.plugin_dir}")

        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        errors = validate_manifest(self.manifest)
        if errors:
            raise PluginLoadError("Ошибки манифеста:\n" + "\n".join(errors))

        self._entry = self.manifest["entry"]
        self.permissions = PluginPermissions.from_list(
            self.manifest.get("permissions", [])
        )

        if self.permissions.errors:
            logger.warning(
                f"Плагин '{self.manifest['id']}': "
                f"отклонённые права: {self.permissions.denied}"
            )

        for py_file in self.plugin_dir.glob("*.py"):
            self._file_hashes[py_file.name] = compute_file_hash(py_file)

        self._start_process()

    def _start_process(self) -> None:
        permissions_json = json.dumps(list(self.permissions.granted))
        runner = Path(__file__).parent / "plugin_runner.py"

        self._process = subprocess.Popen(
            [
                sys.executable,
                str(runner),
                str(self.plugin_dir),
                permissions_json,
                self._entry,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

        # Поток чтения ответов
        self._reader_thread = threading.Thread(
            target=self._read_loop, daemon=True,
            name=f"plugin-reader-{self.manifest.get('id', '?')}"
        )
        self._reader_thread.start()

        # Ждём сигнала «ready» до 5 секунд
        try:
            resp = self._response_queue.get(timeout=5)
            if resp.get("type") == "ready":
                self._ready = True
                logger.info(f"Плагин '{self.manifest['id']}' загружен.")
            else:
                raise PluginLoadError(f"Неожиданный ответ при старте: {resp}")
        except queue.Empty:
            self.unload()
            raise PluginLoadError(
                f"Плагин '{self.manifest.get('id', '?')}' не ответил за 5 секунд."
            )

    # ── Отправка события ─────────────────────────────────────────────────────

    def trigger(self, hook: str, payload: dict | None = None) -> dict | None:
        if not self._ready or not self._process:
            return None
        if not self.permissions.can_use_hook(hook):
            return None
        if not self._verify_integrity():
            logger.error(
                f"[sandbox] Плагин '{self.manifest['id']}': "
                "обнаружена подмена файлов! Плагин остановлен."
            )
            self.unload()
            return None

        event = json.dumps({"hook": hook, "payload": payload or {}}, ensure_ascii=False)

        with self._lock:
            try:
                self._process.stdin.write(event + "\n")
                self._process.stdin.flush()
            except (BrokenPipeError, OSError):
                logger.error(f"Плагин '{self.manifest['id']}' недоступен.")
                self._ready = False
                return None

        try:
            resp = self._response_queue.get(timeout=3)
        except queue.Empty:
            logger.warning(
                f"Плагин '{self.manifest['id']}' не ответил на '{hook}' за 3 сек."
            )
            return None

        # ── Обрабатываем стандартные коллбэки ────────────────────────────────
        for log_line in resp.get("logs", []):
            self.on_log(f"[{self.manifest['id']}] {log_line}")

        for note in resp.get("notifications", []):
            self.on_notify(note)

        # ── Новые UI-коллбэки ─────────────────────────────────────────────────

        # CSS-патч от плагина
        if "style_patch" in resp and self.permissions.can_patch_style():
            css = resp["style_patch"]
            self.on_style_patch(self.plugin_id, css)

        # Регистрация вкладки
        if "tab_info" in resp and self.permissions.can_register_tab():
            tab_info = resp["tab_info"]
            tab_html = resp.get("tab_html", "")
            self.on_register_tab(
                self.plugin_id,
                tab_info.get("title", self.plugin_name),
                tab_info.get("icon", "🔌"),
                tab_html,
            )

        if resp.get("type") == "plugin_error":
            logger.warning(
                f"Плагин '{self.manifest['id']}' ошибка в '{hook}':\n"
                f"{resp.get('traceback', '')}"
            )

        return resp

    # ── Проверка целостности ──────────────────────────────────────────────────

    def _verify_integrity(self) -> bool:
        for filename, original_hash in self._file_hashes.items():
            current_path = self.plugin_dir / filename
            if not current_path.exists():
                logger.error(f"[integrity] Файл '{filename}' пропал!")
                return False
            current_hash = compute_file_hash(current_path)
            if current_hash != original_hash:
                logger.error(
                    f"[integrity] Файл '{filename}' изменён! "
                    f"Оригинал: {original_hash[:12]}… Сейчас: {current_hash[:12]}…"
                )
                return False
        return True

    # ── Остановка ────────────────────────────────────────────────────────────

    def unload(self) -> None:
        self._ready = False
        if self._process:
            try:
                self._process.stdin.close()
            except Exception:
                pass
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
        logger.info(f"Плагин '{self.manifest.get('id', '?')}' выгружен.")

    def _read_loop(self) -> None:
        try:
            for line in self._process.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    self._response_queue.put(data)
                except json.JSONDecodeError:
                    logger.warning(f"[sandbox] Мусор из плагина: {line[:100]}")
        except Exception:
            pass

    @property
    def is_running(self) -> bool:
        return self._ready and self._process is not None

    @property
    def plugin_id(self) -> str:
        return self.manifest.get("id", "unknown")

    @property
    def plugin_name(self) -> str:
        return self.manifest.get("name", "Unknown Plugin")


# ── Менеджер нескольких плагинов ─────────────────────────────────────────────

class SandboxManager:
    """
    Держит все активные песочницы.

    Новые коллбэки:
        on_register_tab(plugin_id, title, icon, html)
        on_style_patch(plugin_id, css)
    """

    def __init__(
        self,
        plugins_root: Path,
        on_log: Callable[[str], None] | None = None,
        on_notify: Callable[[str], None] | None = None,
        on_register_tab: Callable[[str, str, str, str], None] | None = None,
        on_style_patch: Callable[[str, str], None] | None = None,
    ):
        self._last_trigger: dict[str, float] = {}
        self.plugins_root = plugins_root
        self.on_log = on_log
        self.on_notify = on_notify
        self.on_register_tab = on_register_tab or (lambda *a: None)
        self.on_style_patch  = on_style_patch  or (lambda *a: None)
        self._sandboxes: dict[str, PluginSandbox] = {}

        self._throttle = {
            "on_ping_result": 5.0,
            "on_log":         1.0,
        }

    def load_all(self, saved_state: dict[str, bool] | None = None) -> None:
        """Загружает все плагины, пропуская UI-хуки для выключенных."""
        if not self.plugins_root.exists():
            return
        saved_state = saved_state or {}
        for plugin_dir in self.plugins_root.iterdir():
            if plugin_dir.is_dir() and (plugin_dir / "plugin.json").exists():
                plugin_id = self._load_one(plugin_dir)
                if plugin_id:
                    if saved_state.get(plugin_id, True):
                        # Плагин включён — активируем UI-хуки
                        self.activate(plugin_id)
                    else:
                        # Плагин выключен — сразу выгружаем
                        self.unload(plugin_id)

    def install_from_zip(self, zip_path: Path) -> str:
        plugin_dir = install_plugin_from_zip(zip_path, self.plugins_root)
        return self._load_one(plugin_dir)

    def list_all_plugins(self) -> list[dict]:
        """Возвращает ВСЕ плагины (и активные, и выключенные)."""
        plugins = []
        if not self.plugins_root.exists():
            return plugins

        for plugin_dir in self.plugins_root.iterdir():
            if not plugin_dir.is_dir():
                continue
            manifest_path = plugin_dir / "plugin.json"
            if not manifest_path.exists():
                continue

            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            plugin_id = manifest.get("id", plugin_dir.name)
            sandbox = self._sandboxes.get(plugin_id)
            is_running = sandbox is not None

            plugins.append({
                "id": plugin_id,
                "name": manifest.get("name", plugin_id),
                "running": is_running,
                "permissions": manifest.get("permissions", []),
                "version": manifest.get("version", "?"),
                "description": manifest.get("description", ""),
            })

        return plugins

    def _load_one(self, plugin_dir: Path) -> str:
        sandbox = PluginSandbox(
            plugin_dir=plugin_dir,
            on_log=self.on_log,
            on_notify=self.on_notify,
            on_register_tab=self.on_register_tab,
            on_style_patch=self.on_style_patch,
        )
        try:
            sandbox.load()
            self._sandboxes[sandbox.plugin_id] = sandbox
            return sandbox.plugin_id
        except PluginLoadError as e:
            logger.error(f"Не удалось загрузить плагин из {plugin_dir}: {e}")
            return ""

    def activate(self, plugin_id: str) -> None:
        """Включает плагин и триггерит UI-хуки."""
        if plugin_id not in self._sandboxes:
            return
        sandbox = self._sandboxes[plugin_id]

        # СНАЧАЛА вкладка
        if sandbox.permissions.can_register_tab():
            resp = sandbox.trigger("on_build_tab", {})
            # print(f"[DEBUG] on_build_tab resp: {resp}")
            if resp and self.on_register_tab:
                tab_info = resp.get("tab_info")
                tab_html = resp.get("tab_html", "")
                # print(f"[DEBUG] tab_info={tab_info}, html_len={len(tab_html)}")
                if tab_info:
                    self.on_register_tab(
                        plugin_id,
                        tab_info.get("title", sandbox.plugin_name),
                        tab_info.get("icon", "🔌"),
                        tab_html,
                    )
                    # print(f"[DEBUG] on_register_tab CALLED")

        # ПОТОМ стиль
        if sandbox.permissions.can_patch_style():
            resp = sandbox.trigger("on_get_style", {})
            if resp:
                style_patch = resp.get("style_patch")
                if style_patch is not None and self.on_style_patch:
                    self.on_style_patch(plugin_id, style_patch)
                    # Принудительно перерисовываем окно после применения CSS
                    import time
                    time.sleep(0.05)  # маленькая пауза для обработки событий Qt
                    QApplication.processEvents()

    def trigger_hook(self, hook: str, **payload) -> None:
        now = time.monotonic()
        min_interval = self._throttle.get(hook, 0)
        last = self._last_trigger.get(hook, 0)

        if now - last < min_interval:
            return

        self._last_trigger[hook] = now

        dead = []
        for pid, sandbox in self._sandboxes.items():
            if sandbox.is_running:
                sandbox.trigger(hook, payload)
            else:
                dead.append(pid)
        for pid in dead:
            del self._sandboxes[pid]

    def unload_all(self) -> None:
        for sandbox in self._sandboxes.values():
            sandbox.unload()
        self._sandboxes.clear()

    def unload(self, plugin_id: str) -> None:
        if plugin_id in self._sandboxes:
            self._sandboxes[plugin_id].unload()
            del self._sandboxes[plugin_id]

    def list_plugins(self) -> list[dict]:
        return [
            {
                "id":          s.plugin_id,
                "name":        s.plugin_name,
                "running":     s.is_running,
                "permissions": list(s.permissions.granted) if s.permissions else [],
            }
            for s in self._sandboxes.values()
        ]