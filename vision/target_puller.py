import asyncio

class TargetPuller:
    def __init__(self, tracker, arduino, search_delay=0.07, empty_spot_delay=0.5):
        """
        Универсальный легковесный класс для проверки наличия дальних целей.
        """
        self.tracker = tracker
        self.arduino = arduino
        self.search_delay = search_delay
        self.empty_spot_delay = empty_spot_delay
        self.f2_fail_count = 0

    def reset_f2_fails(self):
        """Сбрасывает счетчик фейлов."""
        self.f2_fail_count = 0

    def register_f2_fail(self):
        """Регистрирует неудачный поиск по Next Target."""
        self.f2_fail_count += 1

    async def execute_pulling(self, validator, init_attack_keys: list) -> bool:
        """
        Универсальный метод проверки дальнего пулла.
        Отвечает только за нажатие макроса и первичную фиксацию ХП.
        """
        if self.f2_fail_count < 5:
            return False

        # Счетчик сбрасываем, так как попытка пулла пошла в обработку
        self.f2_fail_count = 0 
        return True
