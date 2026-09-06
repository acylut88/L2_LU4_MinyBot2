import json
import asyncio
import aioserial

class AsyncArduinoController:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.connection = None
        self.config = self._load_config()
        
        # Извлекаем параметры подключения из конфига
        conn_settings = self.config.get("connection", {})
        self.port = conn_settings.get("port", "COM4")
        self.baudrate = conn_settings.get("baudrate", 115200)
        self.dtr_setting = conn_settings.get("dtr", True)
        self.rts_setting = conn_settings.get("rts", True)
        
        # Извлекаем карту кнопок
        self.button_map = self.config.get("buttons", {})

    def _load_config(self) -> dict:
        """Загружает параметры и карту кнопок из JSON."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Ошибка: Файл конфигурации '{self.config_path}' не найден!")
            return {}
        except json.JSONDecodeError as e:
            print(f"Ошибка чтения JSON в '{self.config_path}': {e}")
            return {}

    async def connect(self) -> bool:
        """Подключается к порту, используя считанные из JSON параметры."""
        if not self.button_map:
            print("Ошибка запуска: Конфигурация пуста или не загружена.")
            return False
            
        try:
            # Инициализация с динамическими параметрами
            self.connection = aioserial.AioSerial(
                port=self.port, 
                baudrate=self.baudrate,
                dsrdtr=self.dtr_setting,
                rtscts=self.rts_setting
            )
            
            # Принудительно выставляем DTR/RTS для Leonardo
            self.connection.dtr = self.dtr_setting
            self.connection.rts = self.rts_setting
            
            print(f"Порт {self.port} ({self.baudrate}) открыт.")
            print("Ожидаем инициализацию Leonardo...")
            
            # Даем плате время на перезагрузку и запуск setup()
            await asyncio.sleep(2.5)
            
            if self.connection.in_waiting > 0:
                response = await self.connection.readline_async()
                decoded = response.decode('utf-8', errors='ignore').strip()
                print(f"Ответ от платы: {decoded}")
                print("Успешное подключение! Ардуино готова к работе.")
            else:
                print("Плата готова (входящий буфер пуст, линии DTR/RTS активны).")
                
            return True
                
        except Exception as e:
            print(f"Ошибка подключения к порту {self.port}: {e}")
            return False

    async def send_button(self, button_name: str):
        if not self.connection or not self.connection.is_open:
            print("Ошибка: Нет активного соединения.")
            return
            
        if button_name in self.button_map:
            # Переводим символ из JSON в байтовую строку непосредственно при отправке
            char_to_send = self.button_map[button_name]
            byte_data = char_to_send.encode('utf-8')
            
            await self.connection.write_async(byte_data)
            print(f"Отправлена команда для кнопки: {button_name} (символ: '{char_to_send}')")
        else:
            print(f"Кнопка '{button_name}' отсутствует в файле конфигурации.")

    def close(self):
        if self.connection and self.connection.is_open:
            self.connection.close()
            print("Подключение закрыто.")

async def main():
    # Класс сам подтянет config.json из текущей директории
    arduino = AsyncArduinoController() 
    
    print(f"Инициализация подключения по конфигу...")
    if not await arduino.connect():
        return
    
    print("Ждем 3 секунд...")
    await asyncio.sleep(3) 
    
    # проверочная отправка команды для кнопки "1" (символ 'с' в config_arduino.json)
    await arduino.send_button("1")
    
    arduino.close()

if __name__ == "__main__":
    asyncio.run(main())
