import asyncio
import sys
import os
import random

# Корректный импорт модулей из структуры проекта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vision.state_tracker import StateTracker
from vision.target_validator import TargetValidator
from vision.target_puller import TargetPuller
from arduino.arduino_controller_async import AsyncArduinoController

async def combat_loop(tracker: StateTracker, validator: TargetValidator, arduino: AsyncArduinoController):
    print("\n[Бой] Запуск ускоренной боевой логики в тестовом файле...")
    
    tracker.check_interval = 0.1
    f2_fail_count = 0  # Счетчик неудачных нажатий F2
    
    while True:
        try:
            current_hp = tracker.get_current_hp()
            
            # Шаг 1: Если цели нет в таргете
            if current_hp == 0:
                # КОНТР-ФИЧА: Если 5 раз нажали F2 и никого не нашли
                if f2_fail_count >= 5:
                    print(f"[Контр-фича] 5 фейлов F2! Прожимаем макрос дальнего поиска (Кнопка '0')...")
                    f2_fail_count = 0  # Сбрасываем счетчик
                    
                    await arduino.send_button("0")
                    
                    # МНОГОКРАТНАЯ ПРОВЕРКА: Ждем появления ХП-бара дальнего маяка (15 проверок по 100 мс)
                    current_hp = 0
                    for i in range(15):
                        await asyncio.sleep(0.1)
                        current_hp = tracker.get_current_hp()
                        if current_hp > 0:
                            print(f"[Контр-фича] Дальний маяк успешно обнаружен на {i+1}-й проверке (ХП: {current_hp}%)!")
                            break
                    
                    # Если дальний моб по макросу "0" успешно нашелся
                    if current_hp > 0:
                        # Проверяем, не БОСС ли это
                        is_boss = await validator.is_boss_selected()
                        if is_boss:
                            print("[Защита] ВНИМАНИЕ! По макросу '0' найден БОСС! Сбрасываем таргет...")
                            await arduino.send_button("Esc")
                            await asyncio.sleep(0.1)
                            continue
                            
                        # Инициируем атаку, чтобы персонаж начал физически бежать к нему
                        print("[Контр-фича] Дальняя цель одобрена. Начинаем атаку для инициации движения...")
                        await arduino.send_button("1")   # Отправляем слугу
                        await asyncio.sleep(0.12)
                        await arduino.send_button("F4")  # Начинаем атаку персонажем
                        
                        # Даем персонажу ровно 1 секунду, чтобы он развернулся и побежал
                        print("[Контр-фича] Чар побежал. Ждем 1 секунду в движении...")
                        await asyncio.sleep(1.0)
                        
                        # ЖЕСТКАЯ КОНТР-МЕРА: Сбрасываем дальний таргет спамом Esc (3 раза с КД 0.3 сек)
                        print("[Контр-фича] Жестко отменяем дальнюю цель спамом Esc на бегу...")
                        for _ in range(3):
                            await arduino.send_button("Esc")
                            await asyncio.sleep(0.3)
                            
                        # Входим в фазу агрессивного перехвата ближних мобов на бегу (макс 5 секунд)
                        print("[Контр-фича] Сканируем ближнюю зону через F2 каждые 0.5 сек...")
                        start_run_time = asyncio.get_event_loop().time()
                        
                        while asyncio.get_event_loop().time() - start_run_time < 5.0:
                            await arduino.send_button("F2")
                            await asyncio.sleep(0.07)  # Пауза на отрисовку ХП
                            
                            run_hp = tracker.get_current_hp()
                            if run_hp > 0:
                                print(f"[Контр-фича] На бегу успешно перехвачен ближний моб (ХП: {run_hp}%)!")
                                break
                            
                            await asyncio.sleep(0.43)  # Общий интервал поиска на бегу ~0.5 сек
                        
                        # Возвращаемся на начало большого цикла анализировать перехваченного моба
                        continue
                    else:
                        print("[Контр-фича] По макросу '0' никто не нашелся. Возвращаемся к штатному поиску.")
                        continue
                
                # ШТАТНЫЙ РЕЖИМ ПОИСКА ПО F2
                print("[Поиск] Цели нет. МГНОВЕННЫЙ поиск моба (Нажимаем F2)...")
                await arduino.send_button("F2")
                await asyncio.sleep(0.07)
                
                current_hp = tracker.get_current_hp()
                if current_hp == 0:
                    f2_fail_count += 1  # Наращиваем количество фейлов поиска
                    await asyncio.sleep(0.5)
                    continue

            # Если моб нашелся обычным способом (или перехвачен на бегу) — сбрасываем фейлы F2
            f2_fail_count = 0

            # Шаг 2: Анализ состояния найденной цели
            print(f"[Таргет] Обнаружена цель. Текущее ХП моба: {current_hp}%")
            
            # Логика проверки раненых мобов (3 секунды ожидания)
            if current_hp < 100:
                print("[Защита] Моб ранен (<100% ХП). Пробуем найти другого через F2...")
                last_damaged_hp = current_hp
                await arduino.send_button("F2")
                await asyncio.sleep(0.07)
                
                new_hp = tracker.get_current_hp()
                if new_hp == 0 or new_hp == last_damaged_hp:
                    print("[Защита] Следующий моб не найден. Режим ожидания (3 сек)...")
                    start_wait = asyncio.get_event_loop().time()
                    is_someone_attacking = False
                    
                    if new_hp == 0:
                        await arduino.send_button("F2")
                        await asyncio.sleep(0.07)
                    
                    while asyncio.get_event_loop().time() - start_wait < 3.0:
                        await asyncio.sleep(0.2)
                        check_hp = tracker.get_current_hp()
                        if check_hp < last_damaged_hp and check_hp > 0:
                            print("[Защита] ХП моба падает! Его бьют. Пропускаем...")
                            is_someone_attacking = True
                            break
                            
                    if is_someone_attacking:
                        await arduino.send_button("Esc")
                        await asyncio.sleep(0.5)
                        continue
                    else:
                        print("[Защита] ХП стабильно 3 сек. Принимаем бой...")
                        current_hp = tracker.get_current_hp()
                else:
                    continue

            # Шаг 3: Проверка на босса (череп) для обычного режима
            is_boss = await validator.is_boss_selected()
            if is_boss:
                print("[Защита] ВНИМАНИЕ! ОБНАРУЖЕН БОСС (ЧЕРЕП)! Сбрасываем таргет...")
                await arduino.send_button("Esc") 
                await asyncio.sleep(0.1)
                continue

            # Шаг 4: ШТАТНАЯ АТАКА (если моб ближний)
            print("[Бой] Цель одобрена! Начинаем атаку слугой...")
            await arduino.send_button("1") 
            await asyncio.sleep(0.5)
            print("[Бой] Начинаем атаку персонажем...")
            await arduino.send_button("F4")   
            
            start_combat_time = asyncio.get_event_loop().time()
            last_attack_time = start_combat_time
            max_seen_hp = current_hp
            
            # Внутренний цикл обычного сражения
            while True:
                await asyncio.sleep(0.05)
                current_hp = tracker.get_current_hp()
                now = asyncio.get_event_loop().time()
                
                if current_hp == 0:
                    print("[Бой] Моб повержен! МГНОВЕННЫЙ сбор лута...")
                    loot_clicks = random.randint(3, 5)
                    for _ in range(loot_clicks):
                        await arduino.send_button("F1")
                        await asyncio.sleep(0.05) 
                    break
                
                if now - start_combat_time >= 20.0:
                    print("[Таймаут] Застряли. Сброс цели...")
                    await arduino.send_button("Esc")
                    await asyncio.sleep(0.05)
                    break
                
                if current_hp < max_seen_hp:
                    max_seen_hp = current_hp
                    last_attack_time = now  
                
                if now - last_attack_time >= random.uniform(1.0, 4.0):
                    print("[Бой] ХП моба не падает. Повторное прожатие атаки...")
                    await arduino.send_button("1")
                    last_attack_time = now

        except Exception as e:
            print(f"[Критическая ошибка] {e}")
            await asyncio.sleep(1.0)
async def main():
    print("=== ТЕСТИРОВАНИЕ ОПТИМИЗИРОВАННОЙ ЛОГИКИ СТЯГИВАНИЯ ===")
    
    arduino = AsyncArduinoController()
    if not await arduino.connect():
        print("[Ошибка] Нет связи с Ардуино. Тест отменен.")
        return

    tracker = StateTracker(profile_name="PK_den4ika")
    if not tracker.load_profile():
        tracker.calibrate()

    validator = TargetValidator(profile_name="PK_den4ika", threshold=0.68)
    if not validator.load_profile():
        validator.calibrate_target_zone()

    # Запускаем параллельно зрение и наш тестовый цикл стягивания
    tracker_task = asyncio.create_task(tracker.track_loop())
    combat_task = asyncio.create_task(combat_loop(tracker, validator, arduino))
    
    try:
        await asyncio.gather(tracker_task, combat_task)
    except KeyboardInterrupt:
        print("\n[Выход] Тестирование прервано пользователем.")
    finally:
        tracker_task.cancel()
        combat_task.cancel()
        arduino.close()
        print("[Готово] Порты закрыты.")

if __name__ == "__main__":
    asyncio.run(main())
