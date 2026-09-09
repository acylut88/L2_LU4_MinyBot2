from enum import Enum, auto

class CombatAction(Enum):
    # --- БАЗОВАЯ БОЕВАЯ ЛИНЕЙКА (1-13) ---
    ACTION_HAND_ATTACK = auto()    # 1. Атака с руки
    ACTION_NUKE_1 = auto()         # 2. Маг/Физ атака обычная 1
    ACTION_NUKE_2 = auto()         # 3. Маг/Физ атака обычная 2
    ACTION_HEAVY_NUKE_1 = auto()   # 4. Усиленная атака 1
    ACTION_HEAVY_NUKE_2 = auto()   # 5. Усиленная атака 2
    ACTION_HEAVY_NUKE_3 = auto()   # 6. Усиленная атака 3
    ACTION_OVER_HIT = auto()       # 7. Овер-хит (добивание)
    ACTION_DEBUFF_1 = auto()       # 8. Дебафф 1
    ACTION_DEBUFF_2 = auto()       # 9. Дебафф 2
    ACTION_DEBUFF_3 = auto()       # 10. Дебафф 3
    ACTION_DEBUFF_4 = auto()       # 11. Дебафф 4
    ACTION_DEBUFF_5 = auto()       # 12. Дебафф 5
    ACTION_SIT_STAND = auto()      # 13. Сесть / Встать
    ACTION_LONG_PULL = auto()      # Дальний маяк стягивания (кнопка 0)

    # --- ЛИНЕЙКА ПОДДЕРЖКИ И ВЫЖИВАНИЯ (НОВЫЕ 14-20) ---
    ACTION_HP_SKILL = auto()       # 14. Селф-хил / Вампирик / Скилл-бафф дварфа
    ACTION_HP_POTION = auto()      # 15. Обычные ХП-банки (без отката)
    ACTION_CP_ELIXIR_SMALL = auto()# 16. Малый ЦП-эликсир (по 50 ЦП, откат 3 мин)
    ACTION_CP_ELIXIR_BIG = auto()  # 17. Большой ЦП-эликсир (по 200/300 ЦП, откат 3 мин)
    ACTION_HP_ELIXIR = auto()      # 18. ХП-эликсир (откат 3 мин)


# Дефолтная базовая карта для Mage_dwarf, расширенная новыми экшенами
DEFAULT_MAGE_DWARF_MAP = {
    CombatAction.ACTION_HAND_ATTACK: "4",
    CombatAction.ACTION_NUKE_1: "1",
    CombatAction.ACTION_NUKE_2: "2",
    CombatAction.ACTION_HEAVY_NUKE_1: "3",
    CombatAction.ACTION_OVER_HIT: "7",
    CombatAction.ACTION_DEBUFF_1: "8",
    CombatAction.ACTION_SIT_STAND: "Num*",
    CombatAction.ACTION_LONG_PULL: "0",
    
    # Резервируем кнопки для банок и селф-хила по умолчанию (при необходимости переопределим в JSON)
    CombatAction.ACTION_HP_SKILL: "9",
    CombatAction.ACTION_HP_POTION: "-",
    CombatAction.ACTION_CP_ELIXIR_SMALL: "Num1",
    CombatAction.ACTION_CP_ELIXIR_BIG: "Num2",
    CombatAction.ACTION_HP_ELIXIR: "Num3"
}
