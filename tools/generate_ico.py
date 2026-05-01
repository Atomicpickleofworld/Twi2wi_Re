"""
Генератор .ico файла из одного большого PNG.
Использование:
    python tools/generate_ico.py
(Убедись, что assets/icon.png существует, минимум 256x256)
"""

from PIL import Image
from pathlib import Path

# Пути
BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_PNG = BASE_DIR / "assets" / "icon.png"
OUTPUT_ICO = BASE_DIR / "assets" / "icon.ico"

# Список нужных разрешений — от большего к меньшему!
# Windows использует ПЕРВЫЙ подходящий размер, поэтому 256 идёт первым.
SIZES = [256, 128, 64, 48, 32, 24, 16]

def main():
    if not INPUT_PNG.exists():
        print(f"Ошибка: {INPUT_PNG} не найден!")
        return

    img = Image.open(INPUT_PNG)
    print(f"Исходное изображение: {img.size}, mode={img.mode}")

    # Приводим к RGBA (обязательно для .ico)
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    # Генерируем набор иконок
    icons = []
    for size in SIZES:
        resized = img.resize((size, size), Image.LANCZOS)
        icons.append(resized)
        print(f"  ✓ {size}x{size}")

    # Сохраняем в .ico — первый размер = 256, он будет "главным"
    icons[0].save(
        OUTPUT_ICO,
        format="ICO",
        sizes=[(i.width, i.height) for i in icons],
        append_images=icons[1:]
    )
    print(f"\nГотово → {OUTPUT_ICO} (содержит {len(SIZES)} размеров)")

    # Проверка: читаем обратно и смотрим размер
    print("\n📋 Проверка записанного файла:")
    with Image.open(OUTPUT_ICO) as ico:
        print(f"  Формат: {ico.format}")
        print(f"  Размер: {ico.size}")
        print(f"  Режим: {ico.mode}")
        # Пробуем посчитать количество "страниц" вручную
        try:
            # Pillow показывает только первый кадр при простом чтении
            # Но мы можем проверить через .info
            if hasattr(ico, 'info') and ico.info:
                print(f"  Доп. информация: {ico.info}")
        except Exception:
            pass
        print("  (Все размеры записаны успешно, если выше нет ошибок)")

if __name__ == "__main__":
    main()