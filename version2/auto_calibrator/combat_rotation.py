# version2/auto_calibrator/combat_rotation.py
import asyncio

class CombatRotation:
    def __init__(self, core):
        self.core = core

    async def execute_skills(self, current_mob_hp):
        """Прожимает умения, кулдауны и базовую атаку в бою."""
        profile = self.core.combat_profile
        rot = profile.get("combat_rotation", {})
        dwarf = profile.get("dwarf_spoiler_logic", {})
        flags = profile.get("features_flags", {})
        core_act = profile.get("core_actions", {})

        # 1. Прожатие Спойла на старте боя (100% HP)
        if flags.get("use_dwarf_logic") and dwarf.get("spoil_setup", {}).get("enabled"):
            spoil = dwarf["spoil_setup"]
            if spoil["trigger_condition"] == "on_start" and current_mob_hp == "100%":
                if not self.core.spoil_attempted:
                    for _ in range(spoil["max_attempts"]):
                        await self.core.hardware_press_log(spoil["key"], "Спойл")
                        await asyncio.sleep(spoil["delay_between_attempts_ms"] / 1000)
                    self.core.spoil_attempted = True

        # 2. Условие Оверхита (Добивание 1-20%)
        if current_mob_hp == "1-20%":
            for oh in rot.get("overhit_skills", []):
                if oh.get("enabled"):
                    act_id = f"oh_{oh['key']}"
                    if self.core.defense.check_cooldown(act_id, oh["cooldown_ms"]):
                        await self.core.hardware_press_log(oh["key"], "💥 ОВЕРХИТ")

        # 3. Спам дополнительных атак класса по КД
        for atk in rot.get("additional_attacks", []):
            if atk.get("enabled"):
                act_id = f"atk_{atk['key']}"
                if self.core.defense.check_cooldown(act_id, atk["cooldown_ms"]):
                    await self.core.hardware_press_log(atk["key"], "Доп. Атака")

        # 4. Базовая атака / Нюк в паузах между КД скиллов
        if self.core.defense.check_cooldown("normal_attack", 600):
            await self.core.hardware_press_log(core_act["normal_attack"]["key"], "Удар")
