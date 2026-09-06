import asyncio
import random
from vision.hp_tracker import HPTracker
from vision.target_validator import TargetValidator
from arduino.arduino_controller_async import AsyncArduinoController

class SummonerCombat:
    def __init__(self, tracker: HPTracker, validator: TargetValidator, arduino: AsyncArduinoController):
        """
        Класс управления боевой логикой сумонера с тактикой удержания спота.
        """
        self.tracker = tracker
        self.validator = validator
        self.arduino = arduino
        
        # Флаг паузы, которым будет управлять BotManager
        self.is_paused = False
        
        # Конфигурация боевых таймингов
        self.combat_timeout = 20.0       
        self.search_delay = 0.07         
        self.empty_spot_delay = 0.5      
        self.escape_delay = 0.1          
        self.loot_delay = 0.05           
        self.pet_tank_delay = 0.5        

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
                    print("[Поиск] Цели нет. МГНОВЕННЫЙ поиск моба (Нажимаем F2)...")
                    await self.arduino.send_button("F2")
                    await asyncio.sleep(self.search_delay)
                    
                    current_hp = self.tracker.get_current_hp()
                    if current_hp == 0:
                        await asyncio.sleep(self.empty_spot_delay)
                        continue

                # Шаг 2: Анализ состояния найденной цели
                print(f"[Таргет] Обнаружена цель. Текущее ХП моба: {current_hp}%")
                
                # ЕСЛИ МОБ РАНЕНЫЙ (<100% ХП)
                if current_hp < 100:
                    if self.is_paused: continue
                    print("[Защита] Моб ранен (<100% ХП). Пробуем найти другого (Нажимаем F2)...")
                    
                    # Запоминаем текущее ХП раненого моба перед попыткой переключения
                    last_damaged_hp = current_hp
                    
                    # Прожимаем нексттаргет поверх него, чтобы переключить цель
                    await self.arduino.send_button("F2")
                    await asyncio.sleep(self.search_delay)
                    
                    # Проверяем, изменился ли таргет после нажатия F2
                    new_hp = self.tracker.get_current_hp()
                    
                    # Если таргет остался на том же раненом мобе или спот пуст (новое ХП равно 0 или старому раненому значению)
                    if new_hp == 0 or new_hp == last_damaged_hp:
                        print("[Защита] Следующий моб не найден. Включаем режим ожидания (3 сек)...")
                        
                        # Запускаем 3-секундный таймер слежения за ХП раненого моба
                        start_wait = asyncio.get_event_loop().time()
                        is_someone_attacking = False
                        
                        # Возвращаем таргет на этого моба, если он сбросился в 0
                        if new_hp == 0:
                            await self.arduino.send_button("F2")
                            await asyncio.sleep(self.search_delay)
                        
                        while asyncio.get_event_loop().time() - start_wait < 3.0:
                            await asyncio.sleep(0.2)
                            if self.is_paused: break
                            
                            check_hp = self.tracker.get_current_hp()
                            # Если за эти 3 секунды ХП моба уменьшилось — значит, его точно КТО-ТО БЬЕТ
                            if check_hp < last_damaged_hp and check_hp > 0:
                                print(f"[Защита] ХП моба падает ({check_hp}% < {last_damaged_hp}%)! Его бьют. Пропускаем спот...")
                                is_someone_attacking = True
                                break
                            
                        if self.is_paused: continue
                        
                        if is_someone_attacking:
                            # Если моба бьют, сбрасываем его через Esc и уходим спать на пустой спот
                            await self.arduino.send_button("Esc")
                            await asyncio.sleep(self.empty_spot_delay)
                            continue
                        else:
                            # Если за 3 секунды ХП не упало — моб наш (агр или реген). Идем атаковать!
                            print("[Защита] ХП стабильно в течение 3 сек. Моб наш! Принимаем бой...")
                            current_hp = self.tracker.get_current_hp()
                    else:
                        # Если F2 успешно переключил на другого моба — уходим на начало цикла анализировать его
                        print("[Поиск] Успешно переключились на другую цель через F2.")
                        continue

                # Шаг 3: Проверка на босса (череп)
                # Если это босс, мы не ждем 3 секунды, а агрессивно жмем F2 дальше
                is_boss = await self.validator.is_boss_selected()
                if is_boss:
                    if self.is_paused: continue
                    print("[Защита] ВНИМАНИЕ! ОБНАРУЖЕН БОСС (ЧЕРЕП)! Ищем следующего через F2...")
                    await self.arduino.send_button("F2") 
                    await asyncio.sleep(self.search_delay)
                    continue

                # Шаг 4: Цель окончательно одобрена. Инициация атаки
                if self.is_paused: continue
                print("[Бой] Цель одобрена! Начинаем атаку слугой...")
                await self.arduino.send_button("1") 
                await asyncio.sleep(self.pet_tank_delay)
                
                if self.is_paused: continue
                print("[Бой] Начинаем атаку персонажем...")
                await self.arduino.send_button("F4")   
                
                # Таймеры контроля боя
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
                    
                    # Условие А: Моб успешно повержен (0% ХП)
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
                    
                    # Условие Б: Защита от застревания (Таймаут)
                    if now - start_combat_time >= self.combat_timeout:
                        if self.is_paused: break
                        print("[Таймаут] Застряли или нет урона. Сброс цели через Esc...")
                        await self.arduino.send_button("Esc")
                        await asyncio.sleep(self.loot_delay)
                        break
                    
                    # Если урон идет, сдвигаем таймер атаки вперед (не спамим кнопки)
                    if current_hp < max_seen_hp:
                        max_seen_hp = current_hp
                        last_attack_time = now  
                    
                    # Условие В: Урон застопорился. Повторная атака
                    if now - last_attack_time >= random.uniform(1.0, 4.0):
                        if self.is_paused: continue
                        print("[Бой] ХП моба не падает. Повторное прожатие атаки...")
                        await self.arduino.send_button("1")
                        last_attack_time = now

            except Exception as e:
                print(f"[Критическая ошибка] Ошибка в боевом цикле сумонера: {e}")
                await asyncio.sleep(1.0)
