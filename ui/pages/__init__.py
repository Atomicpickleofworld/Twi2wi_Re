# ui/pages/__init__.py
from .connect_page import build_connect_page, ConnectController
from .configs_page import build_configs_page, ConfigsController
from .ping_page import build_ping_page, PingController
from .sys_page import build_sys_page
from .plugins_page import (
    build_plugins_page,
    PluginsController,
    create_plugin_card,
    apply_plugin_style,
    render_plugins,
    plugin_event_filter,
    filter_plugins,
    view_full_description,
    show_plugin_menu,
    delete_plugin,
    toggle_plugin,
    show_import_menu,
    import_plugin_file,
    import_plugin_git,
)

__all__ = [
    # Фабрики страниц
    "build_connect_page",
    "build_configs_page",
    "build_ping_page",
    "build_sys_page",
    "build_plugins_page",
    # Контроллеры
    "ConnectController",
    "ConfigsController",
    "PingController",
    "PluginsController",
    # Свободные функции плагинов (обратная совместимость)
    "create_plugin_card",
    "apply_plugin_style",
    "render_plugins",
    "plugin_event_filter",
    "filter_plugins",
    "view_full_description",
    "show_plugin_menu",
    "delete_plugin",
    "toggle_plugin",
    "show_import_menu",
    "import_plugin_file",
    "import_plugin_git",
]