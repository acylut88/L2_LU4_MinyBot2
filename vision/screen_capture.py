import os
import time
import numpy as np
import tkinter as tk
from PIL import ImageGrab, ImageTk, ImageDraw

# Фикс масштабирования Windows
try:
    from ctypes import windll
    windll.user32.SetProcessDPIAware()
except Exception as e:
    print("DPI Awareness предупреждение:", e)

class ScreenCapturer:
    @staticmethod
    def take_screenshot():
        """Делает полноэкранный снимок пиксель-в-пиксель."""
        return ImageGrab.grab(all_screens=True)

    @staticmethod
    def get_bgr_array(screenshot):
        """Конвертирует PIL Image в массив BGR для OpenCV."""
        import cv2
        return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    def select_line_on_screen(self):
        """Открывает стабильное окно Tkinter для калибровки линии."""
        print("Подготовьте ХП-бар в игре. Калибровка через 1 секунду...")
        time.sleep(1)
        
        screenshot = self.take_screenshot()
        screen_bgr = self.get_bgr_array(screenshot)
        
        root = tk.Tk()
        root.attributes("-fullscreen", True)
        root.attributes("-topmost", True)
        
        canvas = tk.Canvas(root, cursor="cross", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        
        tk_img = ImageTk.PhotoImage(screenshot)
        canvas.create_image(0, 0, anchor="nw", image=tk_img)
        
        start_point = None
        end_point = None
        current_line = None
        
        def on_press(event):
            nonlocal current_line, start_point
            start_point = (event.x, event.y)
            if current_line:
                canvas.delete(current_line)
                
        def on_drag(event):
            nonlocal current_line
            if start_point:
                if current_line:
                    canvas.delete(current_line)
                current_line = canvas.create_line(
                    start_point[0], start_point[1], 
                    event.x, event.y, 
                    fill="red", width=2
                )
                
        def on_release(event):
            nonlocal end_point
            end_point = (event.x, event.y)
            root.destroy()

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        
        print("\n=== КАЛИБРОВКА ===")
        print("Зажмите ЛКМ в начале ХП-бара, протащите до конца и отпустите.")
        root.mainloop()
        
        if start_point and end_point:
            return start_point, end_point, screen_bgr
        raise ValueError("Линия калибровки не была начерчена!")
