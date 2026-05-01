# security/plugin_runner.py
"""
Точка входа ВНУТРИ дочернего процесса-песочницы.

Запускается так:
    python -m security.plugin_runner <plugin_dir> <permissions_json>

Получает события из stdin (JSON-строки), вызывает хуки плагина,
отправляет результат в stdout (JSON-строки).

Плагин НЕ имеет доступа к:
  - основному процессу VPNManager
  - файлам за пределами своей папки
  - модулям os, sys, subprocess, socket (блокируются)
"""

from __future__ import annotations

import sys
import json
import importlib.util
import traceback
import types
from pathlib import Path


# ── Блокировка опасных модулей ───────────────────────────────────────────────

_BLOCKED_MODULES = {
    "subprocess", "multiprocessing", "ctypes", "socket",
    "ssl", "http", "urllib", "requests", "httpx",
    "winreg", "msvcrt", "_winapi",
}

_original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__


def _safe_import(name, *args, **kwargs):
    top = name.split(".")[0]
    if top in _BLOCKED_MODULES:
        raise ImportError(
            f"[sandbox] Модуль '{name}' заблокирован политикой безопасности."
        )
    return _original_import(name, *args, **kwargs)


def _install_import_hook():
    import builtins
    builtins.__import__ = _safe_import


# ── Ограничение файловой системы ─────────────────────────────────────────────

_allowed_root: Path | None = None


def _safe_open(file, mode="r", *args, **kwargs):
    try:
        target = Path(file).resolve()
    except Exception:
        raise PermissionError(f"[sandbox] Недопустимый путь: {file}")

    if _allowed_root and not str(target).startswith(str(_allowed_root)):
        raise PermissionError(
            f"[sandbox] Доступ к '{target}' запрещён. "
            f"Плагин может читать только '{_allowed_root}'."
        )
    return _original_open(file, mode, *args, **kwargs)


_original_open = open


def _install_fs_hook(plugin_dir: Path):
    global _allowed_root
    _allowed_root = plugin_dir.resolve()
    import builtins
    builtins.open = _safe_open


# ── Загрузка плагина ─────────────────────────────────────────────────────────

def _load_plugin(plugin_dir: Path, entry: str) -> types.ModuleType:
    entry_path = plugin_dir / entry
    if not entry_path.exists():
        raise FileNotFoundError(f"Файл плагина не найден: {entry_path}")

    spec = importlib.util.spec_from_file_location("plugin_module", entry_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── CSS-валидатор (внутри runner, без импорта ui) ────────────────────────────

_CSS_MAX_BYTES = 8 * 1024  # 8 KB

# Запрещённые CSS-паттерны (безопасность)
_CSS_BLOCKED_PATTERNS = [
    "url(",         # внешние ресурсы
    "qproperty-",   # Qt-специфичные свойства которые могут навредить
    "image:",
    "@import",
    "javascript:",
    "-qt-",
]


def _validate_css(css: str) -> str:
    """
    Минимальная проверка CSS от плагина.
    Возвращает очищенный CSS или бросает ValueError.
    """
    if not isinstance(css, str):
        raise ValueError("CSS должен быть строкой")
    if len(css.encode("utf-8")) > _CSS_MAX_BYTES:
        raise ValueError(f"CSS превышает лимит {_CSS_MAX_BYTES // 1024} KB")
    low = css.lower()
    for pattern in _CSS_BLOCKED_PATTERNS:
        if pattern in low:
            raise ValueError(f"CSS содержит запрещённый паттерн: '{pattern}'")
    return css.strip()


# ── Контекст который передаётся плагину вместо прямого доступа ──────────────

class PluginContext:
    """
    Единственный объект который видит плагин.
    Никаких ссылок на VPNManager, конфиги, файлы.
    """
    def __init__(self, permissions: set[str]):
        self._permissions = permissions
        self._log_buffer: list[str] = []
        self._notifications: list[str] = []
        self._style_patch: str | None = None
        self._tab_info: dict | None = None
        self._tab_html: str | None = None

    # ── Базовые методы ───────────────────────────────────────────────────────

    def log(self, message: str):
        """Плагин может писать в свой лог."""
        if not isinstance(message, str):
            return
        self._log_buffer.append(str(message)[:500])

    def notify(self, message: str):
        """Отправить уведомление в UI (если есть право notify:ui)."""
        if "notify:ui" not in self._permissions:
            raise PermissionError("[sandbox] Нет права notify:ui")
        if not isinstance(message, str):
            return
        self._notifications.append(str(message)[:200])

    # ── UI: стили ────────────────────────────────────────────────────────────

    def set_style(self, css: str):
        """
        Передать CSS-патч для применения к приложению.
        Требует право ui:style.

        Пример:
            def on_get_style(ctx, payload):
                ctx.set_style(\"\"\"
                    #sidebar { background: #1a1a2e; }
                    #nav_btn { color: #e94560; }
                \"\"\")
        """
        if "ui:style" not in self._permissions:
            raise PermissionError("[sandbox] Нет права ui:style")
        self._style_patch = _validate_css(css)

    def clear_style(self):
        """Убрать CSS-патч (вернуть дефолтные стили)."""
        if "ui:style" not in self._permissions:
            raise PermissionError("[sandbox] Нет права ui:style")
        self._style_patch = ""   # пустая строка = сбросить патч

    # ── UI: вкладка ──────────────────────────────────────────────────────────

    def register_tab(self, title: str, icon: str = "🔌", html: str = ""):
        """
        Зарегистрировать вкладку в сайдбаре.
        Требует право ui:tab.

        Параметры:
            title  — название кнопки в сайдбаре (до 30 символов)
            icon   — эмодзи иконка (опционально)
            html   — HTML-контент для вкладки (до 32 KB)

        Пример:
            def on_build_tab(ctx, payload):
                ctx.register_tab(
                    title="Статистика",
                    icon="📊",
                    html="<h2>Всё хорошо</h2><p>Подключений: 42</p>"
                )
        """
        if "ui:tab" not in self._permissions:
            raise PermissionError("[sandbox] Нет права ui:tab")

        title = str(title)[:30].strip()
        icon  = str(icon)[:8].strip()

        if not title:
            raise ValueError("Название вкладки не может быть пустым")

        if not isinstance(html, str):
            raise ValueError("html должен быть строкой")
        if len(html.encode("utf-8")) > 32 * 1024:
            raise ValueError("HTML вкладки превышает лимит 32 KB")

        # Базовая защита от XSS в HTML
        _BLOCKED_HTML = ["<script", "javascript:", "onerror=", "onload=", "<iframe"]
        low = html.lower()
        for blocked in _BLOCKED_HTML:
            if blocked in low:
                raise ValueError(f"HTML содержит запрещённый элемент: '{blocked}'")

        self._tab_info = {"title": title, "icon": icon}
        self._tab_html = html

    # ── Внутренний метод сборки ответа ───────────────────────────────────────

    def flush(self) -> dict:
        """Собрать все накопленные ответы для отправки в основной процесс."""
        result: dict = {
            "logs":          self._log_buffer[:],
            "notifications": self._notifications[:],
        }

        if self._style_patch is not None:
            result["style_patch"] = self._style_patch

        if self._tab_info is not None:
            result["tab_info"] = self._tab_info
            result["tab_html"] = self._tab_html or ""

        self._log_buffer.clear()
        self._notifications.clear()
        self._style_patch = None
        self._tab_info    = None
        self._tab_html    = None

        return result


# ── Главный цикл ─────────────────────────────────────────────────────────────

def _send(data: dict):
    print(json.dumps(data, ensure_ascii=False), flush=True)


def _run(plugin_dir: Path, permissions: set[str], entry: str):
    _install_import_hook()
    _install_fs_hook(plugin_dir)

    try:
        module = _load_plugin(plugin_dir, entry)
    except Exception as e:
        _send({"type": "error", "message": f"Ошибка загрузки плагина: {e}"})
        return

    ctx = PluginContext(permissions)
    _send({"type": "ready"})

    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            _send({"type": "error", "message": "Невалидный JSON в событии"})
            continue

        hook_name = event.get("hook", "")
        payload   = event.get("payload", {})

        if hook_name not in permissions and f"hook:{hook_name}" not in permissions:
            if "hooks:read" not in permissions:
                _send({"type": "error", "message": f"Хук '{hook_name}' не разрешён"})
                continue

        handler = getattr(module, hook_name, None)
        if handler is None:
            _send({"type": "ok", "hook": hook_name, **ctx.flush()})
            continue

        try:
            handler(ctx, payload)
        except Exception:
            tb = traceback.format_exc(limit=5)
            _send({"type": "plugin_error", "hook": hook_name,
                   "traceback": tb, **ctx.flush()})
            continue

        _send({"type": "ok", "hook": hook_name, **ctx.flush()})


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"type": "error", "message": "usage: plugin_runner.py <dir> <permissions_json>"}))
        sys.exit(1)

    _plugin_dir  = Path(sys.argv[1])
    _permissions = set(json.loads(sys.argv[2]))
    _entry       = sys.argv[3] if len(sys.argv) > 3 else "main.py"

    _run(_plugin_dir, _permissions, _entry)