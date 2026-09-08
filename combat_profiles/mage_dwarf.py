import asyncio
import random
from vision.state_tracker import StateTracker
from vision.target_validator import TargetValidator
from vision.target_puller import TargetPuller

class Mage_dwarfCombat:
    def __init__(self, tracker: StateTracker, validator: TargetValidator, arduino, buff_system=None):
        self.tracker = tracker
        self.validator = validator
        self.arduino = arduino
        self.buff_system = buff_system  
        self.bot_manager = None         # Ссылка на BotManager запишется при старте
        self.puller = TargetPuller(self.tracker, self.arduino)
        self.is_paused = False
        self.aggressive_mode = True
        
        self.player_hp_tracker = StateTracker(profile_name=self.tracker.profile_name, mode="player_hp")
        self.player_mp_tracker = StateTracker(profile_name=self.tracker.profile_name, mode="player_mp")
        self.player_hp_tracker.load_profile()
        self.player_mp_tracker.load_profile()

        self.combat_timeout = 6.0
        self.search_delay = 0.07
        self.empty_spot_delay = 0.5
        self.f2_fail_count = 0
        
        self.is_resting = False  # Флаг состояния медитации (для соло-режима)

    async def _check_mana_and_recharge(self):
        """
        Универсальный контроль маны:
        Автоматически переключается между заливкой (Dual-Box) и сидением на жопе (Single-Box).
        """
        current_mp = self.player_mp_tracker.get_current_value()
        
        # Запускаем регенерацию, только если МП упало до 20% и ниже
        if current_mp <= 20:
            
            # ВАРИАНТ А: Режим Двух окон (Dual-Box) -> Вызываем заливку от саппорта
            if self.bot_manager and getattr(self.bot_manager, 'bot_mode', 'Single-Box') == "Dual-Box":
                # Метод request_recharge сам поставит бой на паузу, переключит окна и нажмет "-"
                await self.bot_manager.request_recharge()
                await asyncio.sleep(1.0)
                
            # ВАРИАНТ Б: Режим Одного окна (Single-Box / Соло) -> Садимся на жопу
            else:
                if not self.is_resting:
                    print(f"\n[Регенерация Соло] МП мало: {current_mp}%. Садимся отдыхать (Кнопка 'Num*')...")
                    self.is_resting = True
                    await self.arduino.send_button("Num*") # Прожимаем посадку
                    
                    while self.is_resting:
                        await asyncio.sleep(2.0)
                        if self.is_paused: continue
                        
                        mp_now = self.player_mp_tracker.get_current_value()
                        print(f"[Регенерация Соло] Восстановление маны: {mp_now}% / 80%")
                        
                        # Ждем регена до 80% маны
                        if mp_now >= 80:
                            print("[Регенерация Соло] Мана восстановлена! Встаем (Кнопка 'Num*') и продолжаем бой...")
                            await self.arduino.send_button("Num*") # Встаем
                            self.is_resting = False
                            await asyncio.sleep(1.0)

    async def start_loop(self):
        print(f"\n[Бой] Профиль Маг-Дварф запущен. Гибридный мониторинг шкал активен...")
        asyncio.create_task(self.player_hp_tracker.track_loop())
        asyncio.create_task(self.player_mp_tracker.track_loop())
        
        while True:
            try:
                if self.is_paused:
                    await asyncio.sleep(0.2)
                    continue

                # Проверка потребности в мане строго перед поиском новой цели
                await self._check_mana_and_recharge()

                current_hp = self.tracker.get_current_value()
                
                if current_hp == 0:
                    if self.is_paused: continue
                    
                    # Проверка ребаффа саппорта (только для режима Dual-Box)
                    if self.buff_system:
                        await self.buff_system.check_and_run_pending_buffs()

                    if self.is_paused: continue
                    
                    # === ЛИНЕЙНАЯ ИНТЕГРАЦИЯ ДАЛЬНЕГО МАЯКА (МВП СТЯГИВАНИЕ) ===
                    if self.f2_fail_count >= 5:
                        print(f"[Маяк] {self.f2_fail_count} фейлов F2! Прожимаем макрос дальнего поиска (Кнопка '0')...")
                        self.f2_fail_count = 0 # Обнуляем счетчик
                        
                        await self.arduino.send_button("0") # Прожимаем макрос стягивания
                        
                        # === ЖЕСТКИЙ ЦИКЛ ОЖИДАНИЯ ОТРИСОВКИ ХП-БАРА ДАЛЬНЕГО МОБА ===
                        current_hp = 0
                        for i in range(12): # 12 проверок по 100 мс = максимум 1.2 секунды ожидания кадра
                            await asyncio.sleep(0.1)
                            current_hp = self.tracker.get_current_value()
                            if current_hp > 0:
                                print(f"[Маяк] Дальняя цель успешно зацеплена на {i+1}-й проверке кадра (ХП: {current_hp}%)!")
                                break
                        
                        # Если за 1.2 секунды ХП-бар на экране игры действительно появился
                        if current_hp > 0:
                            # Проверяем на босса (череп)
                            if await self.validator.is_boss_selected():
                                print("[Маяк] ВНИМАНИЕ! По макросу '0' пойман БОСС! Сброс.")
                                await self.arduino.send_button("Esc")
                                await asyncio.sleep(0.2)
                                continue
                                
                            print("[Маяк] Цель одобрена. Инициируем атаку для сближения персонажа...")
                            await self.arduino.send_button("1") # Скилл для старта движения / нюк
                            await asyncio.sleep(0.15)
                            await self.arduino.send_button("4") # Обычный удар, чтобы чар бежал к нему
                            
                            # Даем дварфу побежать вперед в сторону дальнего моба
                            print("[Маяк] Персонаж набрал инерцию. Бежим вперед 1.2 сек...")
                            await asyncio.sleep(1.2)
                            
                            # На ходу жестко отвязываемся от дальнего моба
                            await self.arduino.send_button("Esc")
                            await asyncio.sleep(0.1)
                            
                            # Спамим Next Target на ходу для перехвата ближних целей на пути бега
                            print("[Маяк] Перехватываем ближних мобов через F2 на ходу...")
                            for _ in range(4):
                                await self.arduino.send_button("F2")
                                await asyncio.sleep(0.2)
                                if self.tracker.get_current_value() > 0:
                                    print("[Маяк] На бегу успешно перехвачен ближний моб! Входим в ближний бой.")
                                    break
                            continue
                        else:
                            print("[Маяк] За 1.2 сек ХП-бар цели не отрисовался. Возможно, моб вне зоны видимости. Возврат к F2.")
                            continue
                    
                    await self.arduino.send_button("F2")
                    await asyncio.sleep(self.search_delay)
                    
                    current_hp = self.tracker.get_current_value()
                    if current_hp == 0:
                        self.f2_fail_count += 1
                        await asyncio.sleep(self.empty_spot_delay)
                        continue

                self.f2_fail_count = 0

                # ФАЗА ИНИЦИАЦИИ
                print(f"[Таргет] Цель найдена. ХП моба: {current_hp}%. Начинаем атаку...")
                max_seen_hp = current_hp
                start_combat_time = asyncio.get_event_loop().time()
                
                while current_hp == max_seen_hp:
                    if self.is_paused: break
                    if asyncio.get_event_loop().time() - start_combat_time >= 7.0:
                        await self.arduino.send_button("Esc")
                        break
                    await self.arduino.send_button("1")
                    await asyncio.sleep(random.uniform(0.1, 0.3))
                    await self.arduino.send_button("4")
                    await asyncio.sleep(random.uniform(0.2, 0.5))
                    current_hp = self.tracker.get_current_value()

                # ОСНОВНОЙ БОЙ
                while current_hp > 0:
                    await asyncio.sleep(0.05)
                    if self.is_paused: continue
                    current_hp = self.tracker.get_current_value()
                    
                    if asyncio.get_event_loop().time() - start_combat_time >= self.combat_timeout:
                        await self.arduino.send_button("Esc")
                        break

                    if 0 < current_hp <= 20:
                        await self.arduino.send_button("4")
                        while current_hp > 0:
                            await asyncio.sleep(0.05)
                            current_hp = self.tracker.get_current_value()
                        break
                    
                    if current_hp > 20:
                        await self.arduino.send_button("1")
                        await asyncio.sleep(0.2)

                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"[Ошибка] Критический сбой боевого цикла: {e}")
                await asyncio.sleep(1.0)
