"""Главный файл — подключается к MCP серверу и запускает GUI"""
import os
import sys
import asyncio
import threading
import tkinter as tk

if os.name == "nt":
    os.system("chcp 65001 >nul")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient

from config import API_URL, API_KEY, MODEL, MCP_SERVER_SCRIPT
from graph import build_graph, FALLBACK_TOOLS
from gui import PizzaGUI


class PizzaGPTApp:
    def __init__(self):
        self.root = tk.Tk()
        self.gui = PizzaGUI(self.root)
        self.graph = None
        self.mcp_client = None
    
    async def init_mcp_and_graph(self):
        """Инициализирует MCP клиент и граф"""
        try:
            print("🔌 Подключение к MCP серверу...")
            
            self.mcp_client = MultiServerMCPClient({
                "pizza-mcp": {
                    "command": sys.executable,
                    "args": [MCP_SERVER_SCRIPT],
                    "transport": "stdio",
                }
            })
            
            # НОВЫЙ API 0.1.0+
            tools = await self.mcp_client.get_tools()
            print(f"✅ MCP инструменты: {[t.name for t in tools]}")
            
            llm = ChatOpenAI(
                model=MODEL,
                api_key=API_KEY,
                base_url=API_URL,
                temperature=0.7,
                max_tokens=1024,
            )
            llm_with_tools = llm.bind_tools(tools)
            
            self.graph = build_graph(llm_with_tools, tools)
            print("✅ Граф с MCP готов!")
            
            self.root.after(0, self.gui.set_graph, self.graph)
            self.root.after(0, self.gui.show_welcome)
            
            # Держим соединение
            while self.graph and self.root.winfo_exists():
                await asyncio.sleep(1)
        
        except Exception as e:
            print(f"⚠️ MCP не подключился: {e}")
            print("🔄 Использую fallback инструменты (включая интернет)...")
            
            # FALLBACK — без MCP, но с интернетом!
            llm = ChatOpenAI(
                model=MODEL,
                api_key=API_KEY,
                base_url=API_URL,
                temperature=0.7,
                max_tokens=1024,
            )
            llm_with_tools = llm.bind_tools(FALLBACK_TOOLS)
            
            self.graph = build_graph(llm_with_tools, FALLBACK_TOOLS)
            print(f"✅ Граф с fallback готов! Инструменты: {[t.name for t in FALLBACK_TOOLS]}")
            
            self.root.after(0, self.gui.set_graph, self.graph)
            self.root.after(0, self.gui.show_welcome)
    
    def run(self):
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.init_mcp_and_graph())
            except Exception as e:
                print(f"❌ Критическая ошибка: {e}")
                import traceback
                traceback.print_exc()
        
        threading.Thread(target=run_async, daemon=True).start()
        self.root.mainloop()


def main():
    app = PizzaGPTApp()
    app.run()


if __name__ == "__main__":
    main()