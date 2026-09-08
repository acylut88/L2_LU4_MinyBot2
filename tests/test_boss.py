import asyncio
import sys
import os

# Добавляем корень проекта в пути, чтобы Python корректно импортировал ScreenCapturer
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vision.target_validator import TargetValidator

async def main():
    # Создаем валидатор босса (порог совпадения 0.75)
    validator = TargetValidator(profile_name="PK_den4ika", threshold=0.75)
    
    # Загружаем профиль из config.json. Если его нет — запускаем калибровку рамки
    if not validator.load_profile():
        print("Зона цели не настроена. Запуск ручной калибровки...")
        validator.calibrate_target_zone()
        
    print("\nСтарт асинхронной проверки босса. Каждую секунду проверяем область...")
    print("В корне проекта обновляется файл 'debug_boss.png' для проверки рамки.")
    
    try:
        while True:
            # Вызываем асинхронный метод через AWAIT! Текущий поток не блокируется.
            if await validator.is_boss_selected():
                print("[!] ОБНАРУЖЕН БОСС! В рамке найден череп.")
            else:
                print("[ОК] Обычный моб. Череп не найден.")
                
            # Проверка раз в секунду
            await asyncio.sleep(1.0)
            
    except KeyboardInterrupt:
        print("\nТестирование завершено.")

if __name__ == "__main__":
    asyncio.run(main())
