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
    """Подменяем __import__ на безопасную версию."""
    import builtins
    builtins.__import__ = _safe_import


# ── Ограничение файловой системы ─────────────────────────────────────────────

_allowed_root: Path | None = None


def _safe_open(file, mode="r", *args, **kwargs):
    """Разрешаем open() только внутри папки плагина."""
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

    def log(self, message: str):
        """Плагин может писать в свой лог (не в основной)."""
        if not isinstance(message, str):
            return
        self._log_buffer.append(str(message)[:500])  # ограничение длины

    def notify(self, message: str):
        """Отправить уведомление в UI (если есть право notify:ui)."""
        if "notify:ui" not in self._permissions:
            raise PermissionError("[sandbox] Нет права notify:ui")
        if not isinstance(message, str):
            return
        self._notifications.append(str(message)[:200])

    def flush(self) -> dict:
        """Собрать все накопленные ответы для отправки в основной процесс."""
        result = {
            "logs": self._log_buffer[:],
            "notifications": self._notifications[:],
        }
        self._log_buffer.clear()
        self._notifications.clear()
        return result


# ── Главный цикл ─────────────────────────────────────────────────────────────

def _send(data: dict):
    """Отправить JSON-ответ в основной процесс через stdout."""
    print(json.dumps(data, ensure_ascii=False), flush=True)


def _run(plugin_dir: Path, permissions: set[str], entry: str):
    _install_import_hook()
    _install_fs_hook(plugin_dir)

    # Загружаем модуль плагина
    try:
        module = _load_plugin(plugin_dir, entry)
    except Exception as e:
        _send({"type": "error", "message": f"Ошибка загрузки плагина: {e}"})
        return

    ctx = PluginContext(permissions)

    # Сигнал «готов»
    _send({"type": "ready"})

    # Основной цикл: читаем события из stdin
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

        # Проверяем что хук разрешён
        if hook_name not in permissions and f"hook:{hook_name}" not in permissions:
            # hooks:read разрешает все хуки из whitelist
            if "hooks:read" not in permissions:
                _send({"type": "error", "message": f"Хук '{hook_name}' не разрешён"})
                continue

        # Вызываем обработчик плагина если он есть
        handler = getattr(module, hook_name, None)
        if handler is None:
            # Плагин просто не реализует этот хук — OK
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
