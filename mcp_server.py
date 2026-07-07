"""
MCP СЕРВЕР для Pizza GPT
"""
import asyncio
import json
import sys
import os

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

app = Server("pizza-gpt-mcp-server")

PIZZA_RECIPES = {
    "маргарита": {
        "ingredients": ["томатный соус", "моцарелла", "базилик", "оливковое масло"],
        "description": "Классическая итальянская пицца",
        "origin": "Неаполь, 1889"
    },
    "пепперони": {
        "ingredients": ["томатный соус", "моцарелла", "пепперони"],
        "description": "Американская классика с острой колбасой",
        "origin": "США"
    },
    "четыре сыра": {
        "ingredients": ["моцарелла", "пармезан", "чеддер", "горгонзола"],
        "description": "Пицца для любителей сыра",
        "origin": "Италия"
    },
    "вегетарианская": {
        "ingredients": ["томатный соус", "моцарелла", "грибы", "перец", "оливки", "лук"],
        "description": "Пицца с овощами",
        "origin": "Современная"
    },
    "гавайская": {
        "ingredients": ["томатный соус", "моцарелла", "ветчина", "ананас"],
        "description": "Спорная, но популярная",
        "origin": "Канада, 1962"
    },
}

CALORIE_DB = {
    "тесто": 250, "сыр": 400, "моцарелла": 280, "пармезан": 430,
    "чеддер": 400, "томатный соус": 30, "пепперони": 500,
    "ветчина": 150, "бекон": 540, "помидоры": 20, "грибы": 22,
    "оливки": 115, "ананас": 50, "базилик": 5,
}


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_pizza_recipes",
            description="Ищет рецепты пиццы по ингредиентам",
            inputSchema={
                "type": "object",
                "properties": {
                    "ingredients": {"type": "string"}
                },
                "required": ["ingredients"]
            }
        ),
        Tool(
            name="calculate_pizza_calories",
            description="Рассчитывает калорийность пиццы",
            inputSchema={
                "type": "object",
                "properties": {
                    "ingredients": {"type": "string"}
                },
                "required": ["ingredients"]
            }
        ),
        Tool(
            name="search_internet",
            description="Ищет информацию в интернете. ОБЯЗАТЕЛЬНО используй этот инструмент когда пользователь спрашивает что-то актуальное: цены, рестораны, новые рецепты, новости, рецепты в интернете, что популярно сейчас. Также используй для общих вопросов типа 'какая погода', 'что нового', 'новости'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Поисковый запрос"}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_pizza_history",
            description="История происхождения пицц",
            inputSchema={
                "type": "object",
                "properties": {
                    "pizza_name": {"type": "string"}
                },
                "required": []
            }
        ),
        Tool(
            name="get_all_recipes",
            description="Все рецепты пиццы из базы",
            inputSchema={"type": "object", "properties": {}, "required": []}
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    
    if name == "search_pizza_recipes":
        ingredients = arguments.get("ingredients", "").lower()
        found = []
        for pizza_name, data in PIZZA_RECIPES.items():
            if any(ing.strip() in " ".join(data["ingredients"]).lower() 
                   for ing in ingredients.split(",") if ing.strip()):
                found.append(pizza_name)
        
        if not found:
            result = "По таким ингредиентам ничего не нашлось. Попробуй: маргарита, пепперони, вегетарианская."
        else:
            result = f"Нашёл рецепты: {', '.join(found)}\n\n"
            for name in found:
                data = PIZZA_RECIPES[name]
                result += f"- {name.capitalize()}: {', '.join(data['ingredients'])}\n"
        
        return [TextContent(type="text", text=result)]
    
    elif name == "calculate_pizza_calories":
        ingredients = arguments.get("ingredients", "").lower()
        total = 250
        found = []
        for ing, cal in CALORIE_DB.items():
            if ing in ingredients:
                total += cal
                found.append(f"{ing} (+{cal})")
        result = f"Калорийность: {total} ккал/100г. Учтено: {', '.join(found) if found else 'только тесто'}"
        return [TextContent(type="text", text=result)]
    
    elif name == "search_internet":
        query = arguments.get("query", "")
        try:
            from duckduckgo_search import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, region="ru-ru", max_results=5):
                    results.append(r)
            
            if not results:
                return [TextContent(type="text", text=f"По запросу '{query}' ничего не найдено.")]
            
            text = f"Результаты поиска по запросу '{query}':\n\n"
            for r in results:
                text += f"{r.get('title', 'Без названия')}\n"
                text += f"{r.get('body', '')}\n"
                text += f"Источник: {r.get('href', '')}\n\n"
            return [TextContent(type="text", text=text)]
        
        except ImportError:
            return [TextContent(type="text", text="Библиотека duckduckgo-search не установлена.")]
        except Exception as e:
            return [TextContent(type="text", text=f"Ошибка поиска в интернете: {str(e)}")]
    
    elif name == "get_pizza_history":
        pizza_name = arguments.get("pizza_name", "").lower()
        if pizza_name:
            for key, data in PIZZA_RECIPES.items():
                if key in pizza_name:
                    text = f"История {key.capitalize()}:\nПроисхождение: {data['origin']}\n{data['description']}"
                    return [TextContent(type="text", text=text)]
            return [TextContent(type="text", text=f"История '{pizza_name}' не найдена.")]
        else:
            text = "Все пиццы:\n"
            for name in PIZZA_RECIPES:
                text += f"- {name.capitalize()}\n"
            return [TextContent(type="text", text=text)]
    
    elif name == "get_all_recipes":
        text = "Все рецепты:\n\n"
        for name, data in PIZZA_RECIPES.items():
            text += f"{name.capitalize()}: {', '.join(data['ingredients'])}\n"
        return [TextContent(type="text", text=text)]
    
    return [TextContent(type="text", text="Неизвестный инструмент")]


async def main():
    print("MCP сервер Pizza GPT запущен", file=sys.stderr)
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())