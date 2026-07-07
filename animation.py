import tkinter as tk
import random
import math


class PizzaAnimation:
    """Анимация падающих кусочков пиццы (ХОРОШО ВИДИМЫХ!)"""
    
    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.slices = []
        self.animation_id = None
        self._init_slices()
    
    def _init_slices(self):
        """Создаёт кусочки пиццы - КРУПНЫЕ и ЯРКИЕ"""
        # Яркие, хорошо видимые цвета
        self.colors = [
            {"crust": "#D2691E", "cheese": "#FFD700", "sauce": "#DC143C", "topping": "#228B22"},
            {"crust": "#8B4513", "cheese": "#FFA500", "sauce": "#FF4500", "topping": "#006400"},
            {"crust": "#A0522D", "cheese": "#FFD700", "sauce": "#B22222", "topping": "#2E8B57"},
        ]
        
        # 15 крупных кусочков — хорошо видно!
        for _ in range(15):
            self.slices.append({
                "x": random.randint(50, 1050),
                "y": random.randint(-200, 800),
                "speed": random.uniform(1.5, 3.5),
                "rotation": random.uniform(0, 360),
                "rot_speed": random.uniform(-3, 3),
                "size": random.randint(35, 55),  # БОЛЬШОЙ размер!
                "sway": random.uniform(0, math.pi * 2),
                "colors": random.choice(self.colors),
            })
    
    def _draw_slice(self, x, y, size, rotation, colors):
        """Рисует один крупный кусок пиццы"""
        angle = math.radians(rotation)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        
        # Основной треугольник - тесто с корочкой
        points = [
            (x, y - size),
            (x - size * 0.45, y + size * 0.6),
            (x + size * 0.45, y + size * 0.6),
        ]
        
        rotated = []
        for px, py in points:
            rx = x + (px - x) * cos_a - (py - y) * sin_a
            ry = y + (px - x) * sin_a + (py - y) * cos_a
            rotated.extend([rx, ry])
        
        # Корочка (тёмная)
        self.canvas.create_polygon(
            rotated,
            fill=colors["crust"],
            outline="#654321",
            width=2,
            tags="pizza"
        )
        
        # Сыр (жёлтый круг в центре)
        inner_size = size * 0.7
        inner_points = []
        for px, py in points:
            # Сдвигаем к центру
            cx = x + (px - x) * 0.6
            cy = y + (py - y) * 0.6
            rx = x + (cx - x) * cos_a - (cy - y) * sin_a
            ry = y + (cx - x) * sin_a + (cy - y) * cos_a
            inner_points.extend([rx, ry])
        
        self.canvas.create_polygon(
            inner_points,
            fill=colors["cheese"],
            outline="",
            tags="pizza"
        )
        
        # Соус (красный круг)
        self.canvas.create_oval(
            x - size * 0.25, y - size * 0.2,
            x + size * 0.25, y + size * 0.3,
            fill=colors["sauce"],
            outline="",
            tags="pizza"
        )
        
        # Пепперони/топпинги (зелёные/красные кружочки)
        for _ in range(3):
            tx = x + random.uniform(-size * 0.3, size * 0.3)
            ty = y + random.uniform(-size * 0.2, size * 0.4)
            self.canvas.create_oval(
                tx - 4, ty - 4, tx + 4, ty + 4,
                fill=colors["topping"],
                outline="",
                tags="pizza"
            )
    
    def animate(self):
        """Цикл анимации"""
        self.canvas.delete("pizza")
        
        for s in self.slices:
            # Движение
            s["y"] += s["speed"]
            s["rotation"] += s["rot_speed"]
            s["x"] += math.sin(s["y"] * 0.02 + s["sway"]) * 1.5
            
            # Возврат наверх
            if s["y"] > 850:
                s["y"] = -100
                s["x"] = random.randint(50, 1050)
                s["speed"] = random.uniform(1.5, 3.5)
            
            self._draw_slice(s["x"], s["y"], s["size"], s["rotation"], s["colors"])
        
        self.animation_id = self.canvas.after(40, self.animate)
    
    def stop(self):
        if self.animation_id:
            self.canvas.after_cancel(self.animation_id)