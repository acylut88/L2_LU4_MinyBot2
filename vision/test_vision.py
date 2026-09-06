import asyncio
import sys
import os

# Добавляем корень проекта в системный путь, чтобы питон видел модули правильно
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vision.hp_tracker import HPTracker

async def main():
    # Создаем объект трекера. Интервал проверки ставим 1.0 для тестов
    tracker = HPTracker(profile_name="PK_den4ika", check_interval=1.0)
    
    # Пытаемся загрузить профиль. Если его нет — запускаем калибровку.
    # Если хотите перекалибровать заново — временно раскомментируйте строку ниже:
    # tracker.calibrate()
    
    if not tracker.load_profile():
        print("Профиль не найден в конфиге. Запуск ручной калибровки...")
        tracker.calibrate()
        
    # Переходим к постоянному мониторингу
    await tracker.track_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nТестирование завершено пользователем.")
