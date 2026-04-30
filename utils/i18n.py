# utils/i18n.py
import json
from pathlib import Path

class Translator:
    def __init__(self, lang: str = "ru"):
        self._lang = lang
        self._translations: dict = {}
        self.load(lang)

    def load(self, lang: str):
        path = Path(__file__).parent.parent / "locales" / f"{lang}.json"
        if path.exists():
            try:
                self._translations = json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[i18n] Ошибка загрузки {lang}.json: {e}")
                self._translations = {}
        self._lang = lang

    def _(self, key: str, **kwargs) -> str:
        text = self._translations.get(key, key)
        return text.format(**kwargs) if kwargs else text

    def __call__(self, key: str, **kwargs) -> str:
        return self._(key, **kwargs)

# Глобальный экземпляр
tr = Translator("ru")

def set_language(lang: str):
    """Смена языка на лету"""
    tr.load(lang)

def get_available_languages() -> dict[str, str]:
    """
    Сканирует папку locales/ и возвращает {lang_code: display_name}.
    Если в файле есть ключ "lang" — используется он, иначе — имя файла.
    """
    locales_dir = Path(__file__).parent.parent / "locales"
    langs = {}
    if locales_dir.exists():
        for json_file in sorted(locales_dir.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                # Используем ключ "lang" для красивого имени, или имя файла как фолбэк
                display_name = data.get("lang", json_file.stem)
                langs[json_file.stem] = display_name
            except Exception:
                # Если файл битый — показываем просто имя
                langs[json_file.stem] = json_file.stem
    return langs

def save_language_preference(lang: str):
    """Сохраняет выбранный язык в ui_config.json"""
    from utils.config import BASE_DIR
    cfg = BASE_DIR / "ui_config.json"
    try:
        data = {}
        if cfg.exists():
            data = json.loads(cfg.read_text(encoding="utf-8"))
        data["language"] = lang
        cfg.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[i18n] Не удалось сохранить язык: {e}")

def load_language_preference() -> str | None:
    """Загружает сохранённый язык из ui_config.json"""
    from utils.config import BASE_DIR
    cfg = BASE_DIR / "ui_config.json"
    try:
        if cfg.exists():
            data = json.loads(cfg.read_text(encoding="utf-8"))
            return data.get("language")
    except Exception:
        pass
    return None