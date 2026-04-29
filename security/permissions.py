# security/permissions.py
"""
Whitelist разрешённых хуков и разрешений для плагинов.
Плагин запрашивает права в plugin.json → здесь проверяем что они легальны.
"""

from __future__ import annotations
from dataclasses import dataclass, field


# ── Все хуки которые вообще существуют в системе ────────────────────────────

ALLOWED_HOOKS: set[str] = {
    "on_connect",       # VPN подключился   → payload: {"config": {...}}
    "on_disconnect",    # VPN отключился    → payload: {}
    "on_log",           # новая строка лога → payload: {"line": "..."}
    "on_ping_result",   # результат пинга   → payload: {"name": "...", "ms": 0, "loss": 0.0}
    "on_config_added",  # добавлен конфиг   → payload: {"name": "...", "type": "..."}
    "on_config_removed",# удалён конфиг     → payload: {"name": "..."}
}

# ── Права которые плагин может запросить ─────────────────────────────────────

KNOWN_PERMISSIONS: set[str] = {
    "hooks:read",       # получать события (обязательное минимальное право)
    "log:read",         # читать строки лога
    "network:http",     # делать HTTP-запросы (через безопасный прокси-API)
    "notify:ui",        # отправлять уведомление в UI (только текст)
}

# Права без которых плагин не работает вообще
REQUIRED_PERMISSIONS: set[str] = {"hooks:read"}

# Права которые разрешают сетевой доступ — требуют отдельного подтверждения
NETWORK_PERMISSIONS: set[str] = {"network:http"}


@dataclass
class PluginPermissions:
    """Распарсенные и валидированные права конкретного плагина."""
    raw: list[str] = field(default_factory=list)
    granted: set[str] = field(default_factory=set)
    denied: set[str] = field(default_factory=set)
    errors: list[str] = field(default_factory=list)

    @classmethod
    def from_list(cls, requested: list[str]) -> "PluginPermissions":
        granted: set[str] = set()
        denied:  set[str] = set()
        errors:  list[str] = []

        for perm in requested:
            if perm not in KNOWN_PERMISSIONS:
                errors.append(f"Неизвестное право: '{perm}'")
                denied.add(perm)
            else:
                granted.add(perm)

        # Обязательные права добавляем всегда
        granted |= REQUIRED_PERMISSIONS

        return cls(raw=requested, granted=granted, denied=denied, errors=errors)

    def has(self, perm: str) -> bool:
        return perm in self.granted

    def can_use_hook(self, hook: str) -> bool:
        return hook in ALLOWED_HOOKS and self.has("hooks:read")

    def can_use_network(self) -> bool:
        return self.has("network:http")

    def can_notify_ui(self) -> bool:
        return self.has("notify:ui")


def validate_manifest(manifest: dict) -> list[str]:
    """
    Проверяет plugin.json на корректность.
    Возвращает список ошибок (пустой = OK).
    """
    errors: list[str] = []

    required_fields = ["id", "name", "version", "entry", "permissions"]
    for f in required_fields:
        if f not in manifest:
            errors.append(f"Отсутствует обязательное поле: '{f}'")

    if "id" in manifest:
        plugin_id = manifest["id"]
        if not isinstance(plugin_id, str) or not plugin_id.isidentifier():
            errors.append(f"id должен быть валидным Python-идентификатором, получено: '{plugin_id}'")

    if "permissions" in manifest:
        if not isinstance(manifest["permissions"], list):
            errors.append("permissions должен быть списком строк")
        else:
            for p in manifest["permissions"]:
                if p not in KNOWN_PERMISSIONS:
                    errors.append(f"Неизвестное право: '{p}'")

    if "entry" in manifest:
        entry = manifest["entry"]
        if not isinstance(entry, str) or not entry.endswith(".py"):
            errors.append(f"entry должен указывать на .py файл, получено: '{entry}'")
        # Защита от path traversal
        if ".." in entry or "/" in entry or "\\" in entry:
            errors.append(f"entry не может содержать пути с '..' или слэшами: '{entry}'")

    return errors
