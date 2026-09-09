import os
import json
import time

class BotSetupWizard:
    def __init__(self, config_name="config.json", combat_dir_name="combat_profiles"):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(base_dir, config_name)
        self.cp_dir = os.path.join(base_dir, combat_dir_name)
        
        # ИНИЦИАЛИЗАЦИЯ ДИРЕКТОРИЙ ФИЛЬТРОВ (Исправляет AttributeError)
        self.white_list_dir = os.path.join(base_dir, "vision", "white_list")
        self.black_list_dir = os.path.join(base_dir, "vision", "black_list")
        os.makedirs(self.white_list_dir, exist_ok=True)
        os.makedirs(self.black_list_dir, exist_ok=True)
        
        self.config_data = self._load_raw_config()

    def _load_raw_config(self) -> dict:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        example_path = os.path.join(base_dir, "config.json.example")

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        if os.path.exists(example_path):
            try:
                with open(example_path, "r", encoding="utf-8") as f:
                    default_config = json.load(f)
                print("[Мастер] Рабочий config.json восстановлен из шаблона .example")
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, indent=4, ensure_ascii=False)
                return default_config
            except Exception:
                pass

        return {
            "connection": {"port": "COM4", "baudrate": 115200, "dtr": True, "rts": True},
            "buttons": {"F1": "A", "F2": "B", "1": "c", "4": "f", "Esc": "X", "Num*": "z", "-": "m", "F5": "E"},
            "profiles": {}, 
            "characters": ["UnReviver", "Acylut", "VeraWater", "alise"], 
            "game_windows": {"mode": "Single-Box", "Main_Window": "UnReviver", "Second_Window": "", "second_window_mode": 0}
        }

    def _save_raw_config(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config_data, f, indent=4, ensure_ascii=False)

    def get_available_profiles(self) -> list:
        profiles = list(self.config_data.get("profiles", {}).keys())
        return profiles if profiles else ["PK_den4ika"]

    def get_available_combat_profiles(self) -> list:
        if not os.path.exists(self.cp_dir):
            return ["summoner"]
        try:
            files = os.listdir(self.cp_dir)
            profiles = [f[:-3] for f in files if f.endswith(".py") and f != "__init__.py"]
            return profiles if profiles else ["summoner"]
        except Exception:
            return ["summoner"]

    def _setup_character_selection(self, window_title: str, exclude_char: str = "") -> str:
        """Интерактивный выбор персонажа с фильтрацией уже занятых никнеймов."""
        while True:
            base_chars = self.config_data.setdefault("characters", ["UnReviver", "Acylut", "VeraWater", "alise"])
            
            # Фильтруем список, убирая занятого персонажа
            display_chars = [c for c in base_chars if c != exclude_char]
            
            print(f"\n Выберите персонажа для [{window_title}]:")
            for idx, char in enumerate(display_chars, 1):
                print(f"  {idx}. {char}")
            print(f"  {len(display_chars) + 1}. [+] Добавить нового персонажа в базу...")
            
            try:
                choice = int(input(f"Ваш выбор для {window_title}: ").strip())
                if choice == len(display_chars) + 1:
                    new_char = input("Введите точный никнейм нового персонажа (чувствителен к регистру): ").strip()
                    if new_char and new_char not in base_chars:
                        base_chars.append(new_char)
                        self._save_raw_config()
                    return new_char if new_char else "UnReviver"
                else:
                    return display_chars[choice - 1]
            except (ValueError, IndexError):
                print("Некорректный ввод. Попробуйте еще раз.")

    def manage_mob_filters(self, profile_name: str):
        """Инструмент создания графических фильтров с ручным выделением зоны проверки ХП."""
        print("\n" + "=" * 50)
        print("   МАСТЕР НАСТРОЙКИ ГРАФИЧЕСКИХ ФИЛЬТРОВ ХП МОБОВ   ")
        print("=" * 50)
        
        filter_zones = self.config_data.setdefault("filter_zones", {})
        p_name = str(profile_name)
        
        if p_name not in filter_zones:
            print(f"\n[Калибровка] Для профиля '{p_name}' еще не задана зона распознавания цифр ХП!")
            print("Инструкция: У вас есть 4 секунды, чтобы развернуть Lineage 2 и взять моба в таргет.")
            print("Затем экран заморозится, и вам нужно будет выделить ЖЕЛТОЙ РАМКОЙ")
            print("строго ту область, где написан слеш и цифры МАКС ХП (например, '/ 1282').")
            
            # --- НОВАЯ ЗАДЕРЖКА ДЛЯ ПЕРЕКЛЮЧЕНИЯ НА ИГРУ ---
            for i in range(4, 0, -1):
                print(f"Замораживание экрана для разметки через {i}...")
                time.sleep(1.0)
                
            print("[Захват] Экран зафиксирован! Ожидайте отрисовку сетки...")
            
            import tkinter as tk
            from PIL import ImageGrab, ImageTk
            screenshot = ImageGrab.grab(all_screens=True)
            
            root = tk.Tk()
            root.attributes("-fullscreen", True)
            root.attributes("-topmost", True)
            canvas = tk.Canvas(root, cursor="cross", highlightthickness=0)
            canvas.pack(fill="both", expand=True)
            tk_img = ImageTk.PhotoImage(screenshot)
            canvas.create_image(0, 0, anchor="nw", image=tk_img)
            
            lbl = tk.Label(root, text="ОБВЕДИТЕ РАМКОЙ ЦИФРЫ МАКСИМАЛЬНОГО ХП ЦЕЛИ", font=("Arial", 20, "bold"), fg="yellow", bg="black", padx=10, pady=5)
            lbl.pack(side="top", pady=40)

            
            start_x, start_y = 0, 0
            rect_id = None
            bbox_res = None
            
            def on_press(event):
                nonlocal start_x, start_y, rect_id
                start_x, start_y = event.x, event.y
                if rect_id: canvas.delete(rect_id)
            def on_drag(event):
                nonlocal rect_id
                if rect_id: canvas.delete(rect_id)
                rect_id = canvas.create_rectangle(start_x, start_y, event.x, event.y, outline="yellow", width=2)
            def on_release(event):
                nonlocal bbox_res
                x = min(start_x, event.x)
                y = min(start_y, event.y)
                w = abs(event.x - start_x)
                h = abs(event.y - start_y)
                bbox_res = (x, y, w, h)
                root.destroy()

            canvas.bind("<ButtonPress-1>", on_press)
            canvas.bind("<B1-Motion>", on_drag)
            canvas.bind("<ButtonRelease-1>", on_release)
            root.mainloop()
            
            if bbox_res and bbox_res[2] > 3 and bbox_res[3] > 3:
                import tkinter as tk
                rt = tk.Tk()
                sw, sh = rt.winfo_screenwidth(), rt.winfo_screenheight()
                rt.destroy()
                img_w, img_h = screenshot.size
                
                # ФИКС ИНДЕКСОВ: делим отдельные элементы кортежа по осям
                log_x = int(bbox_res[0] / (img_w / sw))
                log_y = int(bbox_res[1] / (img_h / sh))
                log_w = int(bbox_res[2] / (img_w / sw))
                log_h = int(bbox_res[3] / (img_h / sh))
                
                filter_zones[p_name] = [log_x, log_y, log_w, log_h]
                self._save_raw_config()
                print(f"[Успех] Координаты зоны фильтра сохранены: {filter_zones[p_name]}")
            else:
                print("[Ошибка] Область не была выделена. Отмена операции.")
                return

        log_x, log_y, log_w, log_h = filter_zones[p_name]
        
        print("\nИнструкция для создания шаблона:")
        print("1. Разверните окно игры Lineage 2.")
        print("2. Возьмите в таргет целевого моба.")
        print("3. У вас есть 3 секунды...")
        for i in range(3, 0, -1):
            print(f"Захват через {i}...")
            time.sleep(1.0)
            
        print("[Захват] Делаем скриншот числовой зоны ХП...")
        from vision.screen_capture import ScreenCapturer
        screenshot = ScreenCapturer.take_screenshot()
        
        import tkinter as tk
        root = tk.Tk()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.destroy()
        img_w, img_h = screenshot.size
        
        x = int(log_x * (img_w / sw))
        y = int(log_y * (img_h / sh))
        w = int(log_w * (img_w / sw))
        h = int(log_h * (img_h / sh))
        
        roi_img = screenshot.crop((x, y, x + w, y + h))
        try:
            roi_img.show()
        except Exception:
            pass

        print("\nКуда сохранить этот шаблон ХП?")
        print("  1. В БЕЛОЙ СПИСОК (Бот БУДЕТ бить этого моба)")
        print("  2. В ЧЕРНЫЙ СПИСОК (Бот БУДЕТ ПРОПУСКАТЬ этого моба)")
        print("  3. Отмена")
        
        choice = input("Выберите действие (1-3): ").strip()
        if choice not in ["1", "2"]:
            print("[Мастер] Действие успешно отменено. Возврат в главное меню.\n")
            return
            
        target_dir = self.white_list_dir if choice == "1" else self.black_list_dir
        list_label = "White-лист" if choice == "1" else "Black-лист"
        
        file_name = input("Введите имя для этого моба (английскими буквами, например, 'zombie_1282'): ").strip()
        if not file_name: 
            file_name = f"hp_{int(time.time())}"
            
        final_path = os.path.join(target_dir, f"{file_name}.png")
        roi_img.save(final_path, "PNG")
        print(f"[Успех] Шаблон успешно сохранен в {list_label}!")
        print(f"Путь: {final_path}\n")

    def run_interactive_menu(self) -> tuple[str, str]:
        print("=" * 50)
        print("       ЗАПУСК АСИНХРОННОГО БОТА LINEAGE 2       ")
        print("=" * 50)
        
        # 1. Выбор графического профиля калибровки ХП
        avail_profiles = self.get_available_profiles()
        print("\n Доступные профили разметки экрана:")
        for idx, p in enumerate(avail_profiles, 1):
            print(f"  {idx}. {p}")
        print(f"  {len(avail_profiles) + 1}. Создать новый профиль...")
        print(f"  {len(avail_profiles) + 2}. [ФИЛЬТРЫ] Добавить ХП моба в Белый/Черный список...")
        
        is_new_profile = False
        try:
            choice = int(input("Выберите номер профиля или действия: ").strip())
            if choice == len(avail_profiles) + 1:
                profile_name = input("Введите имя для нового профиля (например, NB_Moi): ").strip()
                is_new_profile = True
            elif choice == len(avail_profiles) + 2:
                # Вход в режим создания фильтров мобов
                print("\nВыберите профиль разметки, для которого создается фильтр:")
                for i, p in enumerate(avail_profiles, 1):
                    print(f"  {i}. {p}")
                p_choice = int(input("Номер профиля: ").strip())
                selected_profile = avail_profiles[p_choice - 1]
                
                # Запускаем наш новый инструмент
                self.manage_mob_filters(selected_profile)
                
                # После завершения возвращаем управление в стандартное меню
                return self.run_interactive_menu()
            else:
                profile_name = avail_profiles[choice - 1]
        except (ValueError, IndexError):
            profile_name = "PK_den4ika"
            print(f"Некорректный ввод. Выбран профиль: {profile_name}")
            
        if is_new_profile:
            print(f"\n[Мастер] Запуск сквозной калибровки для нового профиля '{profile_name}'")
            print("Подготовьте окна игры. Выделите моба в таргет.")
            input("Нажмите ENTER, когда будете готовы начать калибровку шкал...")
            
            from vision.state_tracker import StateTracker
            temp_tracker = StateTracker(profile_name=profile_name)
            
            print("\nШаг 1/3: Калибровка ХП МОБА.")
            temp_tracker.calibrate_by_mode("target_hp")
            time.sleep(1.0)
            
            print("\nШаг 2/3: Калибровка ХП ПЕРСОНАЖА.")
            temp_tracker.calibrate_by_mode("player_hp")
            time.sleep(1.0)
            
            print("\nШаг 3/3: Калибровка МП ПЕРСОНАЖА.")
            temp_tracker.calibrate_by_mode("player_mp")
            print("\n[Успех] Все три шкалы для профиля успешно настроены!")

        self.config_data = self._load_raw_config()
        windows_settings = self.config_data.setdefault("game_windows", {})

        # 2. Настройка окон и РОЛИ саппорта
        print("\n Выберите режим работы бота:")
        print("  1. Single-Box (Фарм в 1 окно, без баффера)")
        print("  2. Dual-Box (Фарм в 2 окна с окном поддержки)")
        
        mode_choice = input("Выберите режим (1 или 2): ").strip()
        if mode_choice == "2":
            windows_settings["mode"] = "Dual-Box"
            main_char = self._setup_character_selection("Основное окно (Мейн / Фармер)")
            second_char = self._setup_character_selection("Второе окно (Саппорт)", exclude_char=main_char)
            
            print("\n Выберите алгоритм поведения для Второго окна саппорта:")
            print("  1. Баффер (Только ребафф по таймеру, без пати и заливок - Овер/Варк)")
            print("  2. Заливка + Бафф (Ребафф 7 кнопок + заливка МП с инвайтом через F5 - ЕЕ/ШЕ)")
            print("  3. Заливка (Только заливка маны при просадке МП, без ребаффа)")
            print("  4. Ничего, просто бегать (Заглушка следования за основой)")
            
            try:
                sub_mode = int(input("Выберите номер режима (1-4): ").strip())
                if not (1 <= sub_mode <= 4):
                    sub_mode = 2
            except ValueError:
                sub_mode = 2
                
            windows_settings["Main_Window"] = main_char
            windows_settings["Second_Window"] = second_char
            windows_settings["second_window_mode"] = sub_mode
        else:
            windows_settings["mode"] = "Single-Box"
            main_char = self._setup_character_selection("Основное окно (Мейн)")
            windows_settings["Main_Window"] = main_char
            windows_settings["Second_Window"] = ""
            windows_settings["second_window_mode"] = 0

        self._save_raw_config()

        # 3. Выбор боевого профиля класса мейна
        avail_combat = self.get_available_combat_profiles()
        print("\n Доступные боевые профили классов:")
        for idx, cp in enumerate(avail_combat, 1):
            print(f"  {idx}. {cp.capitalize()}")
            
        try:
            choice_combat = int(input("Выберите номер боевого класса: ").strip())
            combat_name = avail_combat[choice_combat - 1]
        except (ValueError, IndexError):
            combat_name = "summoner"
            print(f"По умолчанию загружен боевой профиль: {combat_name}")
            
        mode_labels = {1: "БАФФЕР (ОВЕР/ВАРК)", 2: "ЗАЛИВКА + БАФФ (ЕЕ/ШЕ)", 3: "ТОЛЬКО ЗАЛИВКА", 4: "ПРОСТО БЕГАТЬ (ЗАГЛУШКА)"}
        print("\n" + "-" * 50)
        print(f"-> Калибровка: {profile_name}")
        print(f"-> Режим:      {windows_settings['mode']}")
        print(f"-> Мейн окно:  LU4 - {main_char}")
        if mode_choice == "2":
            print(f"-> Саппорт:    LU4 - {second_char} [{mode_labels.get(sub_mode)}]")
        print(f"-> Класс боя:  {combat_name.upper()}")
        print("-" * 50 + "\n")
        
        return profile_name, combat_name