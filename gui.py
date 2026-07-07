import tkinter as tk
from tkinter import scrolledtext, ttk
import threading

from config import COLORS, FONTS
from animation import PizzaAnimation


class PizzaGUI:
    """Жёлтый GUI Pizza GPT"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🍕 Pizza GPT - Твой кулинарный помощник")
        self.root.geometry("1000x750")
        self.root.configure(bg=COLORS["bg_main"])
        self.root.resizable(True, True)
        
        self.graph = None
        self.config = {"configurable": {"thread_id": "pizza_session"}}
        
        self._setup_styles()
        self._create_widgets()
        
        # Анимация пиццы
        self.animation = PizzaAnimation(self.pizza_canvas)
        self.animation.animate()
    
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", font=FONTS["text"], padding=8, background=COLORS["bg_header"])
        style.configure("TEntry", font=FONTS["text"])
    
    def _create_widgets(self):
        """Создаёт все виджеты"""
        # Canvas для анимации (поверх всего фона, но под виджетами)
        self.pizza_canvas = tk.Canvas(
            self.root,
            width=1000,
            height=750,
            bg=COLORS["bg_main"],
            highlightthickness=0,
            bd=0,
        )
        self.pizza_canvas.place(x=0, y=0)
        
        # Заголовок
        header = tk.Frame(self.root, bg=COLORS["bg_header"], bd=3, relief=tk.RAISED)
        header.pack(fill=tk.X, padx=15, pady=(10, 5))
        
        tk.Label(
            header,
            text="🍕 PIZZA GPT 🍕",
            font=FONTS["title"],
            bg=COLORS["bg_header"],
            fg=COLORS["text_light"],
        ).pack(side=tk.LEFT, padx=20, pady=10)
        
        tk.Label(
            header,
            text="Твой умный кулинарный помощник",
            font=FONTS["italic"],
            bg=COLORS["bg_header"],
            fg=COLORS["text_light"],
        ).pack(side=tk.LEFT, padx=10)
        
        # Основной контейнер
        main = tk.Frame(self.root, bg=COLORS["bg_chat"], bd=2, relief=tk.RIDGE)
        main.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        # Заголовок чата
        tk.Label(
            main,
            text="💬 Беседа с Pizza GPT",
            font=FONTS["header"],
            bg=COLORS["bg_chat"],
            fg=COLORS["text_dark"],
        ).pack(fill=tk.X, padx=10, pady=(5, 5))
        
        # Область чата
        self.chat_area = scrolledtext.ScrolledText(
            main,
            wrap=tk.WORD,
            font=FONTS["text"],
            bg=COLORS["bg_chat"],
            fg=COLORS["text_dark"],
            relief=tk.FLAT,
            state=tk.DISABLED,
            highlightthickness=2,
            highlightbackground=COLORS["bg_header"],
        )
        self.chat_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Теги для оформления
        self.chat_area.tag_configure("user", foreground="#0066CC", font=("Arial", 11, "bold"))
        self.chat_area.tag_configure("bot", foreground=COLORS["accent"], font=FONTS["text"])
        self.chat_area.tag_configure("system", foreground="#666666", font=FONTS["italic"])
        
        # Индикатор загрузки
        self.loading_frame = tk.Frame(main, bg=COLORS["bg_chat"])
        self.loading_label = tk.Label(
            self.loading_frame,
            text="🍕 Готовим пиццу",
            font=FONTS["italic"],
            bg=COLORS["bg_chat"],
            fg=COLORS["text_dark"],
        )
        self.loading_label.pack(side=tk.LEFT, padx=10)
        
        self.loading_dots = tk.Label(
            self.loading_frame,
            text="",
            font=FONTS["text"],
            bg=COLORS["bg_chat"],
            fg=COLORS["text_dark"],
        )
        self.loading_dots.pack(side=tk.LEFT)
        
        self.progress = ttk.Progressbar(self.loading_frame, length=200, mode="indeterminate")
        self.progress.pack(side=tk.LEFT, padx=10)
        
        # Поле ввода
        input_frame = tk.Frame(main, bg=COLORS["bg_input"], bd=2, relief=tk.SUNKEN)
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.entry = tk.Entry(
            input_frame,
            font=FONTS["text"],
            relief=tk.FLAT,
            bd=3,
            bg="white",
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        self.entry.bind("<Return>", lambda e: self.send_message())
        
        ttk.Button(
            input_frame,
            text="Отправить 🍕",
            command=self.send_message,
        ).pack(side=tk.RIGHT, padx=5, pady=5)
        
        # Нижняя панель
        footer = tk.Frame(self.root, bg=COLORS["bg_header"], bd=2, relief=tk.RAISED, height=50)
        footer.pack(fill=tk.X, padx=15, pady=10)
        footer.pack_propagate(False)
        
        tk.Label(
            footer,
            text="🍕 Pizza GPT — спроси про рецепты, калории, историю пиццы или поищи в интернете!",
            font=FONTS["text"],
            bg=COLORS["bg_header"],
            fg=COLORS["text_light"],
        ).pack(expand=True)
    
    def display_message(self, sender, message, tag="system"):
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.insert(tk.END, f"{sender}: {message}\n\n", tag)
        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)
    
    def show_welcome(self):
        welcome = (
            "Привет! Я Pizza GPT, твой кулинарный помощник!\n\n"
            "Я могу:\n"
            "- Найти рецепты пиццы по ингредиентам\n"
            "- Рассчитать калорийность\n"
            "- Поискать в интернете актуальные рецепты\n"
            "- Рассказать историю пицц\n\n"
            "Попробуй: \"Рецепт с грибами и сыром\" или \"Сколько калорий в пепперони?\""
        )
        self.display_message("Pizza GPT", welcome, "bot")
        self.entry.focus()
    
    def show_loading(self):
        self.loading_frame.pack(fill=tk.X, padx=10, pady=5)
        self.progress.start(10)
        self._animate_dots()
    
    def hide_loading(self):
        self.loading_frame.pack_forget()
        self.progress.stop()
        self.loading_dots.config(text="")
    
    def _animate_dots(self):
        current = self.loading_dots.cget("text")
        new_dots = "." if len(current) >= 3 else current + "."
        self.loading_dots.config(text=new_dots)
        if self.loading_frame.winfo_ismapped():
            self.root.after(300, self._animate_dots)
    
    def set_graph(self, graph):
        self.graph = graph
    
    def send_message(self):
        user_input = self.entry.get().strip()
        if not user_input:
            return
        
        self.entry.delete(0, tk.END)
        self.display_message("Ты", user_input, "user")
        
        if user_input.lower() in ["выход", "exit", "quit"]:
            self.display_message("Pizza GPT", "До встречи! Приятного аппетита! 🍕", "bot")
            self.root.after(2000, self.root.quit)
            return
        
        if not self.graph:
            self.display_message("Pizza GPT", "Загружаюсь, подожди немного...", "system")
            return
        
        self.show_loading()
        threading.Thread(target=self._process, args=(user_input,), daemon=True).start()
    
    def _process(self, user_input):
        try:
            from langchain_core.messages import HumanMessage
            
            result = self.graph.invoke(
                {"messages": [HumanMessage(content=user_input)]},
                config=self.config,
            )
            
            # Ищем последнее текстовое сообщение от бота
            for msg in reversed(result["messages"]):
                from langchain_core.messages import AIMessage
                if isinstance(msg, AIMessage) and msg.content:
                    tool_calls = getattr(msg, "tool_calls", None)
                    if not tool_calls:
                        reply = msg.content.replace("*", "").replace("#", "").replace("`", "")
                        self.root.after(0, self._update_chat, reply)
                        return
            
            self.root.after(0, self._update_chat, "Обрабатываю...", "system")
        except Exception as e:
            self.root.after(0, self._update_chat, f"Ошибка: {e}", "system")
    
    def _update_chat(self, message, tag="bot"):
        self.hide_loading()
        self.display_message("Pizza GPT", message, tag)