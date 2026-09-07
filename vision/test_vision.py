import asyncio
import sys
import os
import numpy as np
from PIL import ImageDraw

# Добавляем корень проекта в системный путь, чтобы питон видел модули правильно
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vision.hp_tracker import HPTracker

async def visual_debug_loop(tracker: HPTracker):
    """
    Изолированный асинхронный цикл отрисовки дебаг-кадра.
    Работает только в тестовом режиме, не нагружая боевой класс.
    """
    print("[Дебаг] Запущена генерация файла 'debug_scan.png' для проверки разметки...")
    
    # Находим корень проекта, чтобы сохранить картинку туда
    vision_dir = os.path.dirname(os.path.abspath(__file__))
    debug_path = os.path.join(os.path.dirname(vision_dir), "debug_scan.png")
    
    await asyncio.sleep(1.0) # Даем трекеру время запустить первый скриншот
    
    while True:
        try:
            # Если точки еще не рассчитаны — ждем
            if not tracker.points or not tracker.start_point:
                await asyncio.sleep(0.5)
                continue
                
            # Делаем снимок экрана для отрисовки дебага
            screenshot = tracker.capturer.take_screenshot()
            draw = ImageDraw.Draw(screenshot)
            
            # Рисуем синюю эталонную линию ХП-бара
            draw.line([tracker.start_point, tracker.end_point], fill="blue", width=2)
            
            # Отрисовываем 5 точек контроля
            for i, (x, y) in enumerate(tracker.points):
                # Проверяем текущий статус точки
                is_alive = tracker.points_status[i] if i < len(tracker.points_status) else True
                dot_color = "green" if is_alive else "red"
                
                # Рисуем кружок
                r = 5
                draw.ellipse([x-r, y-r, x+r, y+r], fill=dot_color, outline="white")
                
            # Сохраняем готовый размеченный снимок в корень проекта
            screenshot.save(debug_path)
            
            # Обновляем картинку раз в секунду
            await asyncio.sleep(1.0)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Ошибка Дебага] Не удалось обновить картинку: {e}")
            await asyncio.sleep(2.0)

async def main():
    # Создаем объект трекера. Интервал проверки ставим 1.0 для тестов
    tracker = HPTracker(profile_name="PK_den4ika", check_interval=1.0)
    
    # Пытаемся загрузить профиль. Если его нет — запускаем калибровку.
    if not tracker.load_profile():
        print("Профиль не найден в конфиге. Запуск ручной калибровки...")
        tracker.calibrate()
        
    # Запускаем параллельно штатный трекер и наш тестовый дебаг-рисовальщик
    tracker_task = asyncio.create_task(tracker.track_loop())
    debug_task = asyncio.create_task(visual_debug_loop(tracker))
    
    try:
        await asyncio.gather(tracker_task, debug_task)
    except KeyboardInterrupt:
        print("\nТестирование завершено пользователем.")
    finally:
        tracker_task.cancel()
        debug_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
