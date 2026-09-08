import os


def merge_my_project_only(output_filename="project_code.txt"):
    # Полный черный список папок окружений и системного мусора
    ignore_dirs = {
        "venv",
        ".venv",
        "env",
        "__pycache__",
        ".git",
        ".idea",
        ".vscode",
        "build",
        "dist",
        "eggs",
        "lib",
        "lib64",
        "parts",
        "sdist",
        "var",
        "wheels",
        "tests",
    }

    total_files = 0
    total_lines = 0

    with open(output_filename, "w", encoding="utf-8") as outfile:
        for root, dirs, files in os.walk("."):
            # Модифицируем dirs на месте: os.walk вообще НЕ ПОЙДЕТ в эти папки
            dirs[:] = [d for d in dirs if d not in ignore_dirs]

            for file in files:
                # Берем только файлы кода и исключаем сам этот скрипт
                if file.endswith(".py") and file != os.path.basename(__file__):
                    file_path = os.path.join(root, file)

                    # Нормализуем путь (убираем точки в начале для красоты)
                    clean_path = os.path.normpath(file_path)

                    try:
                        with open(file_path, "r", encoding="utf-8") as infile:
                            lines = infile.readlines()

                        # Записываем разделитель
                        outfile.write("\n" + "=" * 80 + "\n")
                        outfile.write(f" FILE: {clean_path} ({len(lines)} lines)\n")
                        outfile.write("=" * 80 + "\n\n")

                        # Записываем код
                        outfile.writelines(lines)
                        outfile.write("\n\n")

                        total_files += 1
                        total_lines += len(lines)

                    except Exception as e:
                        outfile.write(f"[Ошибка чтения файла {clean_path}: {e}]\n\n")

    print(f"🔥 Успешно собрано!")
    print(f"📁 Обработано ваших файлов: {total_files}")
    print(f"📊 Всего строк чистого кода: {total_lines}")
    print(f"💾 Результат сохранен в: {output_filename}")


if __name__ == "__main__":
    merge_my_project_only()
