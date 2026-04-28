# import json
# import zipfile
# import importlib.util
# import sys
# import logging
# import shutil
# from pathlib import Path
# from typing import Dict, Any, Optional
#
# # Импортируем функцию проверки версии из твоего файла version.py
# from utils.version import version_check
#
#
# class PluginManager:
#     """Ядро управления плагинами Twi2wi_Re"""
#
#     def __init__(self, app_context: Any, base_dir: Path):
#         self.app = app_context  # Ссылка на экземпляр VPNManager
#         self.base_dir = base_dir
#         self.plugins_dir = self.base_dir / "plugins"
#         self.active_dir = self.plugins_dir / "active"
#
#         self.plugins_meta: Dict[str, dict] = {}
#
#         # Создаем папки, если нет
#         self.plugins_dir.mkdir(parents=True, exist_ok=True)
#         self.active_dir.mkdir(parents=True, exist_ok=True)
#
#         self.loaded_plugins: Dict[str, Any] = {}  # id -> instance
#         self.log = logging.getLogger("Twi2wi.Plugins")
#
#     def scan_and_load(self):
#         """
#         Основной метод запуска:
#         1. Проходит по всем .zip в plugins/
#         2. Валидирует plugin.json и версию
#         3. Распаковывает в active/
#         4. Загружает модули
#         """
#         if not self.plugins_dir.exists():
#             return
#
#         valid_ids = set()
#
#         # 1. Обработка архивов
#         for zip_path in self.plugins_dir.glob("*.zip"):
#             try:
#                 plugin_id = self._validate_and_extract(zip_path)
#                 if plugin_id:
#                     valid_ids.add(plugin_id)
#             except Exception as e:
#                 self.log.error(f"Ошибка обработки {zip_path.name}: {e}")
#
#         # 2. Очистка старых плагинов из active/, которых нет в архивах
#         for item in self.active_dir.iterdir():
#             if item.is_dir() and item.name not in valid_ids:
#                 self.log.info(f"Удаление устаревшего плагина: {item.name}")
#                 try:
#                     shutil.rmtree(item)
#                 except Exception as e:
#                     self.log.warning(f"Не удалось удалить папку {item.name}: {e}")
#
#         # 3. Загрузка всех валидных плагинов из active/
#         self._load_active_plugins()
#
#     def _validate_and_extract(self, zip_path: Path) -> Optional[str]:
#         """
#         Проверяет plugin.json внутри zip и распаковывает его в active/.
#         Возвращает ID плагина или None, если проверка не пройдена.
#         """
#         try:
#             with zipfile.ZipFile(zip_path, 'r') as z:
#                 names = z.namelist()
#
#                 # Проверка наличия plugin.json в корне архива
#                 if "plugin.json" not in names:
#                     self.log.warning(f"Пропуск {zip_path.name}: отсутствует plugin.json в корне")
#                     return None
#
#                 # Чтение метаданных
#                 meta_bytes = z.read("plugin.json")
#                 meta = json.loads(meta_bytes.decode("utf-8"))
#
#                 # --- ПРОВЕРКА ОБЯЗАТЕЛЬНЫХ ПОЛЕЙ ---
#                 mandatory_fields = ["id", "name", "version", "main", "class"]
#                 for field in mandatory_fields:
#                     if field not in meta:
#                         raise ValueError(f"Отсутствует обязательное поле: '{field}'")
#
#                 plugin_id = meta["id"]
#
#                 # --- ПРОВЕРКА ВЕРСИИ (min_version) ---
#                 min_ver = meta.get("min_version")
#                 if min_ver:
#                     if not version_check(min_ver):
#                         self.log.warning(
#                             f"Плагин {plugin_id} требует версию >= {min_ver}, "
#                             f"текущая версия приложения не подходит."
#                         )
#                         return None  # Пропускаем этот плагин
#
#                 # --- РАСПАКОВКА ---
#                 target_dir = self.active_dir / plugin_id
#
#                 # Если папка уже есть, удаляем её перед распаковкой (обновление)
#                 if target_dir.exists():
#                     shutil.rmtree(target_dir)
#
#                 target_dir.mkdir(parents=True, exist_ok=True)
#
#                 # Безопасная распаковка всех файлов
#                 for member in z.infolist():
#                     # Защита от Path Traversal
#                     if ".." in member.filename or member.filename.startswith("/"):
#                         continue
#
#                     z.extract(member, target_dir)
#
#                 self.log.info(f"✅ Плагин распакован: {plugin_id} (v{meta['version']})")
#                 return plugin_id
#
#         except zipfile.BadZipFile:
#             self.log.error(f"Файл {zip_path.name} поврежден.")
#             return None
#         except json.JSONDecodeError:
#             self.log.error(f"Неверный JSON в plugin.json архива {zip_path.name}.")
#             return None
#         except Exception as e:
#             self.log.error(f"Ошибка валидации {zip_path.name}: {e}")
#             return None
#
#     def _load_active_plugins(self):
#         """Динамически импортирует и инициализирует плагины из папки active/"""
#         for plugin_dir in self.active_dir.iterdir():
#             if not plugin_dir.is_dir(): continue
#
#             meta_path = plugin_dir / "plugin.json"
#             if not meta_path.exists(): continue
#
#             try:
#                 with open(meta_path, "r", encoding="utf-8") as f:
#                     meta = json.load(f)
#
#                 main_file = plugin_dir / meta["main"]
#                 if not main_file.exists():
#                     raise FileNotFoundError(f"Файл точки входа {meta['main']} не найден")
#
#                 # Изолированная загрузка модуля
#                 module_name = f"twi2wi.plugin.{meta['id']}"
#                 spec = importlib.util.spec_from_file_location(module_name, main_file)
#                 module = importlib.util.module_from_spec(spec)
#                 sys.modules[module_name] = module
#                 spec.loader.exec_module(module)
#
#                 # Инстанцирование класса плагина
#                 plugin_cls = getattr(module, meta["class"])
#                 instance = plugin_cls()
#
#                 # Подготовка контекста для плагина
#                 context = {
#                     "app": self.app,
#                     "log": self.log.info,
#                     "plugins_dir": self.plugins_dir,
#                     "trigger_hook": self.trigger_hook
#                 }
#
#                 # Вызов метода загрузки плагина (если есть)
#                 if hasattr(instance, "on_load"):
#                     instance.on_load(context)
#                     self.plugins_meta[meta["id"]] = meta
#
#                 self.loaded_plugins[meta["id"]] = instance
#                 self.log.info(f"🔌 Загружен: {meta['name']} v{meta['version']}")
#
#             except Exception as e:
#                 self.log.error(f"❌ Ошибка загрузки плагина {plugin_dir.name}: {e}")
#                 import traceback
#                 self.log.debug(traceback.format_exc())
#
#     def trigger_hook(self, hook_name: str, **kwargs):
#         """Безопасный вызов события (хука) у всех активных плагинов"""
#         for pid, instance in list(self.loaded_plugins.items()):
#             try:
#                 method = getattr(instance, hook_name, None)
#                 if callable(method):
#                     method(**kwargs)
#             except Exception as e:
#                 self.log.error(f"Ошибка в хуке {hook_name} [{pid}]: {e}")
#
#     def unload_all(self):
#         """Корректное завершение работы всех плагинов при закрытии приложения"""
#         for pid, instance in list(self.loaded_plugins.items()):
#             try:
#                 if hasattr(instance, "on_unload"):
#                     instance.on_unload()
#             except Exception as e:
#                 self.log.error(f"Ошибка при выгрузке плагина {pid}: {e}")
#         self.loaded_plugins.clear()
#         self.log.info("🧹 Все плагины выгружены.")