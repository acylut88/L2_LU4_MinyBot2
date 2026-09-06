String inputString = "";         // Переменная для хранения входящих данных
bool stringComplete = false;     // Флаг завершения приема строки

void setup() {
  Serial.begin(9600);            // Инициализация COM-порта на скорости 9600
  inputString.reserve(50);       // Резервируем память под строку
}

void loop() {
  // Проверяем, пришла ли полная строка от Python
  if (stringComplete) {
    inputString.trim();          // Удаляем пробелы и символы перевода строки \r или \n
    
    // Логика обработки команд
    if (inputString.length() > 0) {
      Serial.print("Received action for button: ");
      Serial.println(inputString);
      
      // Здесь вы можете добавить свою логику. Например:
      // if (inputString == "1") { выполнить действие для кнопки 1 }
      // if (inputString == "ESC") { выполнить действие для кнопки Esc }
    }
    
    // Очищаем строку для следующих данных
    inputString = "";
    stringComplete = false;
  }
}

// Встроенное прерывание, вызывается автоматически при поступлении байт в Serial
void serialEvent() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    inputString += inChar;
    // Если пришел символ новой строки, значит команда передана полностью
    if (inChar == '\n') {
      stringComplete = true;
    }
  }
}
