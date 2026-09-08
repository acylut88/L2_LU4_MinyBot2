import asyncio
import sys
import os
import numpy as np
from PIL import ImageDraw

# Добавляем корень проекта в системный путь, чтобы питон видел модули правильно
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from setup_wizard import BotSetupWizard
from vision.state_tracker import StateTracker

async def visual_debug_loop(profile_name: str, trackers: dict):
    """
    Изолированный асинхронный цикл отрисовки дебаг-кадра.
    Рисует на одном скриншоте все три линии (Target HP, Player HP, Player MP).
    """
    print(f"\n[Дебаг] Запущена генерация файла 'debug_scan.png' для профиля [{profile_name}]...")
    print("[Дебаг] Обновление картинки происходит раз в секунду. Нажмите Ctrl+C для выхода.")
    
    # Находим корень проекта, чтобы сохранить картинку туда
    test_dir = os.path.dirname(os.path.abspath(__file__))
    debug_path = os.path.join(os.path.dirname(test_dir), "debug_scan.png")
    
    # Берем capturer от любого трекера, они одинаковые
    capturer = list(trackers.values())[0].capturer
    
    await asyncio.sleep(1.0) # Даем трекерам время сделать первые снимки
    
    while True:
        try:
            # Делаем свежий снимок экрана
            screenshot = capturer.take_screenshot()
            draw = ImageDraw.Draw(screenshot)
            
            # Цветовая схема для отрисовки линий шкал
            mode_colors = {
                "target_hp": {"line": "red", "name": "Target HP"},
                "player_hp": {"line": "green", "name": "Player HP"},
                "player_mp": {"line": "blue", "name": "Player MP"}
            }
            
            for mode, tracker in trackers.items():
                # Если для этой шкалы точки в профиле еще не настроены — пропускаем её
                if not tracker.points or not tracker.start_point:
                    continue
                    
                colors = mode_colors[mode]
                
                # 1. Рисуем эталонную линию шкалы
                draw.line([tracker.start_point, tracker.end_point], fill=colors["line"], width=2)
                
                # Добавим текстовую метку рядом с началом линии
                x_text, y_text = tracker.start_point
                draw.text((x_text, max(0, y_text - 15)), colors["name"], fill=colors["line"])
                
                # 2. Отрисовываем 5 точек контроля для этой шкалы
                for i, (x, y) in enumerate(tracker.points):
                    is_full = tracker.points_status[i] if i < len(tracker.points_status) else True
                    dot_color = "green" if is_full else "red"
                    
                    r = 5
                    draw.ellipse([x-r, y-r, x+r, y+r], fill=dot_color, outline="white")
                
            # Сохраняем готовый размеченный снимок в корень проекта
            screenshot.save(debug_path)
            
            # Обновляем картинку раз в секунду
            await asyncio.sleep(3.0)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Ошибка Дебага] Не удалось обновить картинку: {e}")
            await asyncio.sleep(2.0)

async def main():
    # 1. Используем наш Wizard для интерактивного выбора профиля прямо в тесте
    wizard = BotSetupWizard()
    avail_profiles = wizard.get_available_profiles()
    
    print("=" * 50)
    print("     ТЕСТИРОВАНИЕ И ВИЗУАЛЬНЫЙ ДЕБАГ ШКАЛ     ")
    print("=" * 50)
    print("\n Доступные профили разметки экрана:")
    for idx, p in enumerate(avail_profiles, 1):
        print(f"  {idx}. {p}")
        
    try:
        choice = int(input("\nВыберите номер профиля для проверки: ").strip())
        profile_name = avail_profiles[choice - 1]
    except (ValueError, IndexError):
        profile_name = "PK_den4ika"
        print(f"Некорректный ввод. Выбран профиль по умолчанию: {profile_name}")
        
    # 2. Инициализируем три независимых трекера под каждую задачу
    modes = ["target_hp", "player_hp", "player_mp"]
    trackers = {}
    tasks = []
    
    print(f"\n[Система] Загрузка шкал для профиля '{profile_name}'...")
    for mode in modes:
        tracker = StateTracker(profile_name=profile_name, check_interval=0.1, mode=mode)
        if tracker.load_profile():
            print(f" -> Шкала [{mode}] успешно загружена. Точки рассчитаны.")
            trackers[mode] = tracker
            # Запускаем фоновый асинхронный цикл мониторинга для этой шкалы
            tasks.append(asyncio.create_task(tracker.track_loop()))
        else:
            print(f" -> [Предупреждение] Координаты для [{mode}] отсутствуют в конфиге.")
            
    if not trackers:
        print("[Ошибка] Ни одна шкала не была загружена. Проверьте config.json. Выход.")
        return

    # 3. Запускаем наш универсальный визуальный дебаггер-рисовальщик
    debug_task = asyncio.create_task(visual_debug_loop(profile_name, trackers))
    tasks.append(debug_task)
    
    try:
        # Удерживаем все асинхронные задачи активными
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("\n[Тест] Тестирование успешно завершено пользователем.")
    finally:
        # Корректно отменяем все запущенные корутины при выходе
        for task in tasks:
            task.cancel()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
