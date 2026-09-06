/*
 * L2 Bot Arduino Leonardo Sketch (НАСТОЯЩИЙ НАМПАД)
 * Эмулирует нажатия клавиш и клики мыши для Lineage 2 LU4
 */

#include <Keyboard.h>
#include <Mouse.h>

void setup() {
  Serial.begin(115200);
  Keyboard.begin();
  Mouse.begin();
  
  delay(2000);
  Serial.println("Arduino L2 Bot готов к работе!");
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    handleCommand(cmd);
  }
}

void handleCommand(char cmd) {
  switch(cmd) {
    // ── F-клавиши (заглавные буквы A-K) ──
    case 'A': pressFKey(KEY_F1); break;
    case 'B': pressFKey(KEY_F2); break;
    case 'C': pressFKey(KEY_F3); break;
    case 'D': pressFKey(KEY_F4); break;
    case 'E': pressFKey(KEY_F5); break;
    case 'F': pressFKey(KEY_F6); break;
    case 'G': pressFKey(KEY_F7); break;
    case 'H': pressFKey(KEY_F8); break;
    case 'I': pressFKey(KEY_F9); break;
    case 'J': pressFKey(KEY_F10); break;
    case 'K': pressFKey(KEY_F11); break;
    case 'L': 
      Mouse.press(MOUSE_LEFT); 
      delay(50); 
      Mouse.release(MOUSE_LEFT); 
      break;
    
    // ── Верхний ряд цифр (строчные буквы c-n) ──
    case 'c': pressKey('1'); break;
    case 'd': pressKey('2'); break;
    case 'e': pressKey('3'); break;
    case 'f': pressKey('4'); break;
    case 'g': pressKey('5'); break;
    case 'h': pressKey('6'); break;
    case 'i': pressKey('7'); break;
    case 'j': pressKey('8'); break;
    case 'k': pressKey('9'); break;
    case 'l': pressKey('0'); break;
    case 'm': pressKey('-'); break;
    case 'n': pressKey('='); break;
    
    // ── НАСТОЯЩИЙ Numpad (строчные буквы o-z) ──
    // Используем жесткие аппаратные скан-коды Windows Keypad
    case 'o': pressKey(220); break;  // Num1
    case 'p': pressKey(221); break;  // Num2
    case 'q': pressKey(222); break;  // Num3
    case 'r': pressKey(223); break;  // Num4
    case 's': pressKey(224); break;  // Num5
    case 't': pressKey(225); break;  // Num6
    case 'u': pressKey(226); break;  // Num7
    case 'v': pressKey(227); break;  // Num8
    case 'w': pressKey(228); break;  // Num9
    case 'x': pressKey(219); break;  // Num0
    case 'y': pressKey(218); break;  // Num/
    case 'z': pressKey(215); break;  // Num*
    
    // ── Специальные команды ──
    case 'P': pressKey('p'); break;       
    case 'R': 
      Mouse.press(MOUSE_RIGHT); 
      delay(50); 
      Mouse.release(MOUSE_RIGHT); 
      break;                              
    case 'X': pressKey(KEY_ESC); break;    
    
    default:
      Serial.print("Неизвестная команда: ");
      Serial.println(cmd);
  }
}

void pressKey(char key) {
  Keyboard.press(key);
  delay(50);
  Keyboard.release(key);
}

// Перегрузка функции для работы со скан-кодами int (Нампад и F-клавиши)
void pressKey(int key) {
  Keyboard.press(key);
  delay(50);
  Keyboard.release(key);
}

void pressFKey(int key) {
  Keyboard.press(key);
  delay(50);
  Keyboard.release(key);
}
