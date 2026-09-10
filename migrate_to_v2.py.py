# migrate_to_v2.py
import os
import shutil

def create_project_v2():
    # Находим корень текущего проекта
    root_dir = os.path.dirname(os.path.abspath(__file__))
    v2_dir = os.path.join(root_dir, "version2")
    
    print("=" * 60)
    # Очищаем старую папку version2, если она существовала, для чистой сборки
    if os.path.exists(v2_dir):
        print("[Скрипт] Обнаружена старая папка version2. Полная очистка...")
        shutil.rmtree(v2_dir)
        
    # 1. Описываем структуру каталогов для новой версии
    folders_to_create = [
        "version2",
        "version2/arduino",
        "version2/vision",
        "version2/auto_calibrator",
        "version2/auto_calibrator/debug_images",
        "version2/combat_profiles"
    ]
    
    print("[Скрипт] Создание новой чистой структуры папок...")
    for folder in folders_to_create:
        os.makedirs(os.path.join(root_dir, folder), exist_ok=True)
        
    # 2. Карта копирования: (исходный файл относительно корня -> куда скопировать в version2)
    files_to_copy = [
        # Конфиги и системные зависимости из старой версии
        ("config.json", "version2/config.json"),
        ("presets/skull_boss.png", "version2/vision/skull.png"), # Переносим шаблон в папку vision
        
        # Модули Ардуино и Компьютерного Зрения
        ("arduino/arduino_controller_async.py", "version2/arduino/arduino_controller_async.py"),
        ("vision/target_validator.py", "version2/vision/target_validator.py"),
        ("vision/screen_capture.py", "version2/vision/screen_capture.py"),
        
        # Наши новые модули универсального ядра
        ("auto_calibrator/screen_bus.py", "version2/auto_calibrator/screen_bus.py"),
        ("auto_calibrator/defense_manager.py", "version2/auto_calibrator/defense_manager.py"),
        ("auto_calibrator/universal_core.py", "version2/auto_calibrator/universal_core.py"),
    ]
    
    # Инициализируем пустые файлы-маркеры инициализации пакетов Python
    with open(os.path.join(v2_dir, "arduino", "__init__.py"), "w") as f: pass
    with open(os.path.join(v2_dir, "vision", "__init__.py"), "w") as f: pass
    with open(os.path.join(v2_dir, "auto_calibrator", "__init__.py"), "w") as f: pass
    with open(os.path.join(v2_dir, "combat_profiles", "__init__.py"), "w") as f: pass

    # Копируем файлы по карте
    print("[Скрипт] Перенос файлов ядра и системных конфигураций...")
    for src_rel, dest_rel in files_to_copy:
        src_path = os.path.join(root_dir, src_rel)
        dest_path = os.path.join(root_dir, dest_rel)
        
        if os.path.exists(src_path):
            shutil.copy2(src_path, dest_path)
            print(f"  -> Успешно перенесен: {src_rel}")
        else:
            print(f"  -> [Пропуск] Исходный файл не найден: {src_rel}")

    # 3. Интегрируем калибровочные данные из config.json в calibrator.json
    print("[Скрипт] Извлечение и конвертация калибровочных данных...")
    config_src = os.path.join(root_dir, "config.json")
    calibrator_dest = os.path.join(v2_dir, "calibrator.json")
    
    if os.path.exists(config_src):
        try:
            with open(config_src, "r", encoding="utf-8") as f:
                old_cfg = json.load(f)
            
            # Строим чистый формат калибратора, вытаскивая координаты из старого конфига
            calibrator_structure = {
                "calibrated_profiles": {
                    "NB_Moi": {
                        "hp_start": old_cfg.get("profiles", {}).get("NB_Moi", {}).get("start_point"),
                        "hp_end": old_cfg.get("profiles", {}).get("NB_Moi", {}).get("end_point"),
                        "cp_start": old_cfg.get("profiles", {}).get("NB_Moi", {}).get("player_hp_start"), # Фолбэк на ХП для безопасности
                        "cp_end": old_cfg.get("profiles", {}).get("NB_Moi", {}).get("player_hp_end"),
                        "mp_start": old_cfg.get("profiles", {}).get("NB_Moi", {}).get("player_mp_start"),
                        "mp_end": old_cfg.get("profiles", {}).get("NB_Moi", {}).get("player_mp_end")
                    }
                }
            }
            with open(calibrator_dest, "w", encoding="utf-8") as f:
                json.dump(calibrator_structure, f, indent=4, ensure_ascii=False)
            print("  -> Файл calibrator.json успешно сгенерирован на основе старого config.json!")
        except Exception as e:
            print(f"  -> [Ошибка] Не удалось распарсить config.json: {e}")
            
    print("\n[Успех] Проект version2 собран и готов к работе в изолированном режиме!")
    print("Выполните запуск: python version2/main.py")
    print("=" * 60)

if __name__ == "__main__":
    import json
    create_project_v2()
