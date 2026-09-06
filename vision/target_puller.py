import asyncio

class TargetPuller:
    def __init__(self, tracker, arduino, search_delay=0.2, empty_spot_delay=0.5):
        """
        Универсальный класс для вывода персонажа из затыка на пустом споте (Long-Range Pulling).
        """
        self.tracker = tracker
        self.arduino = arduino
        self.search_delay = search_delay
        self.empty_spot_delay = empty_spot_delay
        
        self.no_target_timer = None       
        self.is_long_range_pull = False   

    def reset_timer(self):
        self.no_target_timer = None

    async def check_and_pull(self, validator) -> bool:
        """
        Проверяет время простоя. Если оно достигло 6 сек, запускает стягивание.
        Защищено проверкой на босса.
        """
        if self.no_target_timer is None:
            self.no_target_timer = asyncio.get_event_loop().time()
            return False
            
        now = asyncio.get_event_loop().time()
        
        if now - self.no_target_timer < 6.0:
            return False
            
        print("[Puller] Спот пуст 6 секунд! Ищем дальнего моба по имени (Кнопка '0')...")
        await self.arduino.send_button("0")
        await asyncio.sleep(self.search_delay)
        
        current_hp = self.tracker.get_current_hp()
        
        # Если по макросу "0" никто не нашелся
        if current_hp == 0:
            print("[Puller] По имени моб не нашелся. Пробуем подстраховочный F2...")
            await self.arduino.send_button("F2")
            await asyncio.sleep(self.search_delay)
            
            current_hp = self.tracker.get_current_hp()
            if current_hp == 0:
                print("[Puller] Спот полностью пуст. Ждем...")
                await asyncio.sleep(self.empty_spot_delay)
                return False
                
        # --- КРИТИЧЕСКАЯ ПРОВЕРКА НА БОСCA НА ДАЛЬНЕМ РАССТОЯНИИ ---
        is_boss = await validator.is_boss_selected()
        if is_boss:
            print("[Puller] ВНИМАНИЕ! ПО МАКРОСУ '0' ВЫДЕЛЕН БОСС (ЧЕРЕП)! Сбрасываем таргет...")
            await self.arduino.send_button("Esc")
            await asyncio.sleep(0.15)
            # Возвращаем False, чтобы бот не бежал к нему, а начал отсчет заново или искал по F2
            return False
        # -----------------------------------------------------------
                
        print("[Puller] Дальняя цель одобрена! Активируем режим стягивания.")
        self.is_long_range_pull = True
        self.no_target_timer = None
        return True

    async def run_inertial_run_and_scan(self, init_attack_keys: list):
        """
        Запускает атаку для инициации бега, ЖЕСТКО сбрасывает таргет спамом Esc
        и агрессивно сканирует пространство на бегу каждые 0.5 сек.
        """
        # 1. Отправляем команды атаки, чтобы персонаж физически побежал к дальней цели
        print("[Puller] Сагрили дальний маяк. Инициация бега...")
        for key in init_attack_keys:
            await self.arduino.send_button(key)
            await asyncio.sleep(0.12) # Чуть увеличили паузу, чтобы Ардуино успевала прожать
            
        # 2. ЖЕСТКАЯ КОНТР-МЕРА: Нажимаем Esc 3 раза с микропаузами.
        print("[Puller] Персонаж в движении. Жестко сбрасываем дальний таргет спамом Esc...")
        for _ in range(5):
            await self.arduino.send_button("Esc")
            await asyncio.sleep(0.2)
        
        # 3. Цикл агрессивного перехвата ближних мобов на бегу
        print("[Puller] Начинаем сканирование ближней зоны каждые 0.5 сек...")
        while self.is_long_range_pull:
            await asyncio.sleep(0.5)
            
            # Нажимаем ближний некст-таргет
            await self.arduino.send_button("F2")
            await asyncio.sleep(self.search_delay)
            
            run_hp = self.tracker.get_current_hp()
            
            # Как только на бегу зацепили ХП-бар ЛЮБОГО ближнего моба
            if run_hp > 0:
                print(f"[Puller] На бегу успешно перехвачен ближний моб (ХП: {run_hp}%)! Стягивание завершено.")
                self.is_long_range_pull = False
                break