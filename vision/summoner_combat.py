import asyncio
import random
from vision.hp_tracker import HPTracker
from vision.target_validator import TargetValidator
from vision.target_puller import TargetPuller
from arduino.arduino_controller_async import AsyncArduinoController

class SummonerCombat:
    def __init__(self, tracker: HPTracker, validator: TargetValidator, arduino: AsyncArduinoController):
        """
        Класс управления боевой логикой сумонера.
        """
        self.tracker = tracker
        self.validator = validator
        self.arduino = arduino
        
        self.puller = TargetPuller(self.tracker, self.arduino)
        self.is_paused = False
        
        # Боевые тайминги
        self.combat_timeout = 20.0       
        self.search_delay = 0.07         
        self.empty_spot_delay = 0.5      
        self.escape_delay = 0.1          
        self.loot_delay = 0.05           
        self.pet_tank_delay = 0.5        

        # Счетчик неудачных нажатий F2 для вызова макроса "0"
        self.f2_fail_count = 0

    async def start_loop(self):
        print("\n[Бой] Класс Суммонер успешно запущен. Входим в боевой цикл...")
        self.tracker.check_interval = 0.1
        
        while True:
            try:
                if self.is_paused:
                    await asyncio.sleep(0.2)
                    continue

                # Шаг 1: Проверяем наличие цели в таргете
                current_hp = self.tracker.get_current_hp()
                
                if current_hp == 0:
                    if self.is_paused: continue
                    
                    # КРИТИЧЕСКАЯ ФИЧА: Если мы 5 раз промазали по F2 ИЛИ спот пуст 30 секунд
                    # (Пуллер проверит 30 сек внутри check_and_pull автоматически)
                    if self.f2_fail_count >= 5 or await self.puller.check_and_pull(self.validator):
                        print(f"[Контр-фича] Ошибка поиска цели (Фейлов F2: {self.f2_fail_count}). Ищем через макрос '0'...")
                        self.f2_fail_count = 0 # Сбрасываем счетчик фейлов
                        
                        # Если пуллер вызывается по лимиту F2, принудительно активируем его
                        self.puller.is_long_range_pull = True
                        await self.puller.arduino.send_button("0")
                        await asyncio.sleep(self.search_delay)
                        
                        # Если по имени нашли — бежим, если нет — подстраховка F2
                        if self.tracker.get_current_hp() > 0:
                            if await self.puller.check_and_pull(self.validator): # Проверка на босса
                                await self.puller.run_inertial_run_and_scan(init_attack_keys=["1", "F4"])
                            continue
                        else:
                            await self.arduino.send_button("F2")
                            await asyncio.sleep(self.search_delay)
                            if self.tracker.get_current_hp() > 0:
                                if await self.puller.check_and_pull(self.validator):
                                    await self.puller.run_inertial_run_and_scan(init_attack_keys=["1", "F4"])
                                continue
                    
                    # ШТАТНЫЙ РЕЖИМ ПОИСКА ПО F2
                    print("[Поиск] Цели нет. МГНОВЕННЫЙ поиск моба (Нажимаем F2)...")
                    await self.arduino.send_button("F2")
                    await asyncio.sleep(self.search_delay)
                    
                    current_hp = self.tracker.get_current_hp()
                    if current_hp == 0:
                        self.f2_fail_count += 1 # Наращиваем счетчик неудачных поисков
                        await asyncio.sleep(self.empty_spot_delay)
                        continue

                # Как только физически нашли моба (ХП > 0) — сбрасываем счетчик фейлов F2 и таймер пуллера
                self.f2_fail_count = 0
                self.puller.reset_timer()

                # Шаг 2: Анализ состояния найденной цели
                print(f"[Таргет] Обнаружена цель. Текущее ХП моба: {current_hp}%")
                
                if current_hp < 100:
                    if self.is_paused: continue
                    print("[Защита] Моб ранен (<100% ХП). Пробуем найти другого (Нажимаем F2)...")
                    
                    last_damaged_hp = current_hp
                    await self.arduino.send_button("F2")
                    await asyncio.sleep(self.search_delay)
                    
                    new_hp = self.tracker.get_current_hp()
                    
                    if new_hp == 0 or new_hp == last_damaged_hp:
                        print("[Защита] Следующий моб не найден. Включаем режим ожидания (3 сек)...")
                        start_wait = asyncio.get_event_loop().time()
                        is_someone_attacking = False
                        
                        if new_hp == 0:
                            await self.arduino.send_button("F2")
                            await asyncio.sleep(self.search_delay)
                        
                        while asyncio.get_event_loop().time() - start_wait < 3.0:
                            await asyncio.sleep(0.2)
                            if self.is_paused: break
                            
                            check_hp = self.tracker.get_current_hp()
                            if check_hp < last_damaged_hp and check_hp > 0:
                                print(f"[Защита] ХП моба падает! Пропускаем...")
                                is_someone_attacking = True
                                break
                            
                        if self.is_paused: continue
                        
                        if is_someone_attacking:
                            await self.arduino.send_button("Esc")
                            await asyncio.sleep(self.empty_spot_delay)
                            continue
                        else:
                            print("[Защита] ХП стабильно 3 сек. Моб наш! Принимаем бой...")
                            current_hp = self.tracker.get_current_hp()
                    else:
                        print("[Поиск] Успешно переключились на другую цель через F2.")
                        continue

                # Шаг 3: Проверка на босса (череп)
                is_boss = await self.validator.is_boss_selected()
                if is_boss:
                    if self.is_paused: continue
                    print("[Защита] ВНИМАНИЕ! ОБНАРУЖЕН БОСС (ЧЕРЕП)! Сбрасываем таргет через Esc...")
                    await self.arduino.send_button("Esc") 
                    await asyncio.sleep(self.escape_delay)
                    
                    await self.arduino.send_button("F2") 
                    await asyncio.sleep(self.search_delay)
                    continue

                # Шаг 4: Цель одобрена. Обычная атака
                if self.is_paused: continue
                print("[Бой] Цель одобрена! Начинаем атаку слугой...")
                await self.arduino.send_button("1") 
                await asyncio.sleep(self.pet_tank_delay)
                
                if self.is_paused: continue
                print("[Бой] Начинаем атаку персонажем...")
                await self.arduino.send_button("F4")   
                
                start_combat_time = asyncio.get_event_loop().time()
                last_attack_time = start_combat_time
                max_seen_hp = current_hp
                
                # Внутренний цикл сражения с мобом
                while True:
                    await asyncio.sleep(0.05)
                    if self.is_paused:
                        await asyncio.sleep(0.2)
                        continue
                    
                    current_hp = self.tracker.get_current_hp()
                    now = asyncio.get_event_loop().time()
                    
                    if current_hp == 0:
                        if self.is_paused: break
                        print("[Бой] Моб повержен! МГНОВЕННЫЙ сбор лута...")
                        loot_clicks = random.randint(3, 5)
                        for _ in range(loot_clicks):
                            if self.is_paused: break
                            await self.arduino.send_button("F1")
                            await asyncio.sleep(self.loot_delay) 
                        print("[Бой] Сбор завершен. Переходим к следующему мобу.")
                        break
                    
                    if now - start_combat_time >= self.combat_timeout:
                        if self.is_paused: break
                        print("[Таймаут] Застряли или нет урона. Сброс цели через Esc...")
                        await self.arduino.send_button("Esc")
                        await asyncio.sleep(self.loot_delay)
                        break
                    
                    if current_hp < max_seen_hp:
                        max_seen_hp = current_hp
                        last_attack_time = now  
                    
                    if now - last_attack_time >= random.uniform(1.0, 4.0):
                        if self.is_paused: continue
                        print("[Бой] ХП моба не падает. Повторное прожатие атаки...")
                        await self.arduino.send_button("1")
                        last_attack_time = now

            except Exception as e:
                print(f"[Критическая ошибка] Ошибка в боевом цикле сумонера: {e}")
                await asyncio.sleep(1.0)
