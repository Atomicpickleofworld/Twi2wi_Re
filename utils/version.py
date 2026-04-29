# utils/version.py
"""
Централизованное управление версией приложения.
Формат: МАЖОР.МИНОР.ПАТЧ (например, 1.4.0)
"""

__version__ = "2.0.1"
__version_info__ = (2, 0, 1)


__app_name__ = "Twi2wi_Re"
__author__ = "Atomicpickleofworld"
__github__ = "https://github.com/Atomicpickleofworld/Twi2wi_Re"

def get_version() -> str:
    """Возвращает версию как строку."""
    return __version__

def get_version_tuple() -> tuple[int, int, int]:
    """Возвращает версию как кортеж для сравнений."""
    return __version_info__

def version_check(min_required: str) -> bool:
    """Проверяет, что текущая версия >= требуемой."""
    def _parse(v: str) -> tuple:
        return tuple(map(int, v.strip().split(".")))
    return get_version_tuple() >= _parse(min_required)