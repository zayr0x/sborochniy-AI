from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.tools import tool

from pizza_state import PizzaState
from nodes import create_chatbot_node, profile_node


# 🔥 FALLBACK инструмент — работает если MCP не подключился!
@tool
def search_internet_fallback(query: str) -> str:
    """Ищет информацию в интернете через DuckDuckGo. Используй для любых актуальных вопросов."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, region="ru-ru", max_results=3))
            if not results:
                return f"По запросу '{query}' ничего не найдено."
            text = f"Результаты поиска '{query}':\n\n"
            for r in results:
                text += f"{r.get('title', '')}\n{r.get('body', '')}\n\n"
            return text
    except Exception as e:
        return f"Не удалось выполнить поиск: {str(e)}"


@tool
def search_pizza_recipes_fallback(ingredients: str) -> str:
    """Ищет рецепты пиццы по ингредиентам."""
    recipes = {
        "маргарита": "томатный соус, моцарелла, базилик",
        "пепперони": "томатный соус, моцарелла, пепперони",
        "четыре сыра": "моцарелла, пармезан, чеддер, горгонзола",
        "вегетарианская": "томатный соус, грибы, перец, оливки",
    }
    ingredients_lower = ingredients.lower()
    found = [name for name, ings in recipes.items() if any(i in ings for i in ingredients_lower.split(","))]
    if not found:
        return "Попробуй: маргарита, пепперони, четыре сыра, вегетарианская"
    return "Рецепты: " + ", ".join(found)


FALLBACK_TOOLS = [search_internet_fallback, search_pizza_recipes_fallback]


def build_graph(llm_with_tools, mcp_tools):
    """Собирает граф. Если MCP инструментов нет — использует fallback."""
    builder = StateGraph(PizzaState)
    
    # Используем MCP инструменты если есть, иначе fallback
    tools = mcp_tools if mcp_tools else FALLBACK_TOOLS
    
    builder.add_node("chatbot", create_chatbot_node(llm_with_tools))
    builder.add_node("profile", profile_node)
    builder.add_node("tools", ToolNode(tools))
    
    builder.add_edge(START, "chatbot")
    builder.add_conditional_edges(
        "chatbot",
        tools_condition,
        {"tools": "tools", END: "profile"}
    )
    builder.add_edge("tools", "chatbot")
    builder.add_edge("profile", END)
    
    return builder.compile(checkpointer=MemorySaver())