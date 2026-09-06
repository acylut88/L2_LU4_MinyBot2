import asyncio
import sys
import os

# Добавляем корень проекта в пути импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arduino.arduino_controller_async import AsyncArduinoController

async def main():
    print("=== ТЕСТИРОВАНИЕ НАЖАТИЯ КНОПОК Num1 и Num2 ===")
    
    # 1. Подключаем контроллер по конфигурации из config.json
    arduino = AsyncArduinoController()
    if not await arduino.connect():
        print("[Ошибка] Не удалось установить связь с Ардуино. Выход.")
        return

    print("\n[Система] Подготовка завершена.")
    print("У вас есть 3 секунды, чтобы открыть Блокнот или окно игры и кликнуть туда курсором...")
    await asyncio.sleep(3.0)

    # 2. Тестируем Num1
    print("\n[Тест] Отправляем команду для кнопки: Num1")
    await arduino.send_button("Num1")
    
    # Пауза 2 секунды между нажатиями
    print("[Ожидание] Ждем 2 секунды...")
    await asyncio.sleep(2.0)

    # 3. Тестируем Num2
    print("[Тест] Отправляем команду для кнопки: Num2")
    await arduino.send_button("Num2")

    # 4. Закрываем соединение
    print("\n[Завершение] Тест окончен. Закрываем порт.")
    arduino.close()

if __name__ == "__main__":
    asyncio.run(main())
