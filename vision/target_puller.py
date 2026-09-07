import asyncio

class TargetPuller:
    def __init__(self, tracker, arduino, search_delay=0.07, empty_spot_delay=0.5):
        """
        Универсальный класс для вывода персонажа из затыка на пустом споте (Long-Range Pulling).
        """
        self.tracker = tracker
        self.arduino = arduino
        self.search_delay = search_delay
        self.empty_spot_delay = empty_spot_delay
        
        # Счетчик неудачных поисков по F2 для вызова макроса "0"
        self.f2_fail_count = 0

    def reset_f2_fails(self):
        """Сбрасывает счетчик фейлов (вызывать, когда обычный моб найден)."""
        self.f2_fail_count = 0

    def register_f2_fail(self):
        """Регистрирует неудачный поиск по F2."""
        self.f2_fail_count += 1

    async def execute_pulling(self, validator, init_attack_keys: list) -> bool:
        """
        Линейная фича дальнего стягивания. Вызывается, если f2_fail_count >= 5.
        """
        if self.f2_fail_count < 5:
            return False

        print(f"[Puller] Накоплено {self.f2_fail_count} фейлов F2! Ищем дальнего моба по имени (Кнопка '0')...")
        self.f2_fail_count = 0  # Сбрасываем счетчик фейлов
        
        await self.arduino.send_button("0")
        
        # МНОГОКРАТНАЯ ПРОВЕРКА: Ждем появления ХП-бара дальнего маяка (15 проверок по 100 мс)
        current_hp = 0
        for i in range(15):
            await asyncio.sleep(0.1)
            current_hp = self.tracker.get_current_hp()
            if current_hp > 0:
                print(f"[Puller] Дальний маяк успешно обнаружен на {i+1}-й проверке (ХП: {current_hp}%)!")
                break
        
        # Шаг А: Если дальний моб по макросу "0" успешно нашелся
        if current_hp > 0:
            # Проверяем, не БОСС ли это
            is_boss = await validator.is_boss_selected()
            if is_boss:
                print("[Puller] ВНИМАНИЕ! По макросу '0' найден БОСС! Сбрасываем таргет...")
                await self.arduino.send_button("Esc")
                await asyncio.sleep(0.1)
                return False
                
            # Инициируем атаку, чтобы персонаж начал физически бежать к нему
            print("[Puller] Дальняя цель одобрена. Начинаем атаку для инициации движения...")
            for key in init_attack_keys:
                await self.arduino.send_button(key)
                await asyncio.sleep(0.12)
            
            # Даем персонажу ровно 1 секунду, чтобы он набрал скорость бега
            print("[Puller] Чар побежал. Ждем 1 секунду в движении...")
            await asyncio.sleep(1.0)
            
            # ЖЕСТКАЯ КОНТР-МЕРА: Сбрасываем дальний таргет спамом Esc (3 раза с КД 0.3 сек)
            print("[Puller] Жестко отменяем дальнюю цель спамом Esc на бегу...")
            for _ in range(3):
                await self.arduino.send_button("Esc")
                await asyncio.sleep(0.3)
                
            # Входим в фазу агссивного перехвата ближних мобов на бегу (макс 5 секунд)
            print("[Puller] Сканируем ближнюю зону через F2 каждые 0.5 сек...")
            start_run_time = asyncio.get_event_loop().time()
            
            while asyncio.get_event_loop().time() - start_run_time < 5.0:
                await self.arduino.send_button("F2")
                await asyncio.sleep(self.search_delay)  # Пауза на отрисовку ХП
                
                run_hp = self.tracker.get_current_hp()
                if run_hp > 0:
                    print(f"[Puller] На бегу успешно перехвачен ближний моб (ХП: {run_hp}%)!")
                    return True
                
                await asyncio.sleep(0.43)  # Общий интервал поиска на бегу ~0.5 сек
            
            return False
        else:
            print("[Puller] По макросу '0' никто не нашелся. Возвращаемся к штатному поиску.")
            return False
