import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# ИМПОРТ В САМОМ НАЧАЛЕ ФАЙЛА!
from pizza_state import PizzaState
from config import API_URL, API_KEY, MODEL, SYSTEM_PROMPT


# Слова-триггеры: когда пользователь РЕАЛЬНО заказывает пиццу
ORDER_TRIGGERS = [
    "пицца", "пиццу", "пиццы", "пиццей", "пицце",
    "заказать", "заказ", "закажу", "хочу пицц", "давай пицц",
    "сделай пицц", "приготовь пицц", "мне пицц",
]

# Явно опасные/несъедобные вещи
DANGEROUS_KEYWORDS = {
    "лаванда": "лаванда и цветы не подходят для еды",
    "трава": "обычную траву не кладут в пиццу",
    "цветы": "цветы не являются ингредиентом для пиццы",
    "химия": "химические вещества недопустимы в пище",
    "яд": "яд нельзя класть в еду",
    "отрава": "отрава недопустима в пище",
    "пластмасса": "пластмасса несъедобна",
    "металл": "металл несъедобен",
    "стекло": "стекло опасно для здоровья",
    "гвозди": "гвозди несъедобны",
    "камни": "камни нельзя есть",
}


def is_order_request(text: str) -> bool:
    """Проверяет, является ли сообщение запросом на заказ пиццы"""
    text_lower = text.lower()
    return any(trigger in text_lower for trigger in ORDER_TRIGGERS)


def check_dangerous_ingredients(text: str) -> str | None:
    """Проверяет только ЯВНО опасные ингредиенты. Возвращает причину или None."""
    text_lower = text.lower()
    for keyword, reason in DANGEROUS_KEYWORDS.items():
        if keyword in text_lower:
            return reason
    return None


def create_chatbot_node(llm_with_tools):
    """Создаёт узел чат-бота"""
    def chatbot_node(state: PizzaState) -> dict:
        profile = state.get("user_profile", {})
        profile_context = ""
        if profile:
            profile_context = f"\n\nИнформация о пользователе:\n{json.dumps(profile, ensure_ascii=False, indent=2)}"
        
        sys_msg = SystemMessage(content=SYSTEM_PROMPT + profile_context)
        
        if state["messages"]:
            last_human = state["messages"][-1]
            if isinstance(last_human, HumanMessage):
                text = last_human.content
                
                # Проверяем только ОПАСНЫЕ ингредиенты
                danger_reason = check_dangerous_ingredients(text)
                if danger_reason:
                    return {"messages": [AIMessage(
                        content=f"Извини, но {danger_reason}. "
                                "Давай выберем что-нибудь безопасное и вкусное!\n\n"
                                "Могу предложить:\n"
                                "- Пицца Маргарита с моцареллой и базиликом\n"
                                "- Пицца Пепперони с колбасой и томатным соусом\n"
                                "- Вегетарианская с грибами и овощами\n\n"
                                "Что скажешь?"
                    )]}
        
        # Передаём в LLM для обычной обработки
        response = llm_with_tools.invoke([sys_msg] + list(state["messages"]))
        return {"messages": [response]}
    
    return chatbot_node


def profile_node(state: PizzaState) -> dict:
    """Узел обновления профиля"""
    messages = state["messages"]
    profile = state.get("user_profile", {}).copy()
    
    last_human = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_human = msg
            break
    
    if not last_human:
        return {"user_profile": profile}
    
    extraction_prompt = SystemMessage(content="""Извлеки информацию из сообщения:
- Любимые блюда и напитки
- Пищевые предпочтения
- Нелюбимые продукты
- Диетические ограничения

Верни ТОЛЬКО JSON (без markdown):
{
    "favorite_foods": [],
    "favorite_drinks": [],
    "dietary_preferences": [],
    "disliked_foods": [],
    "other_info": ""
}

Если информации нет, верни {}""")
    
    llm = ChatOpenAI(model=MODEL, api_key=API_KEY, base_url=API_URL, temperature=0.3, max_tokens=512)
    response = llm.invoke([extraction_prompt, last_human])
    
    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        new_info = json.loads(content.strip())
        
        for key, value in new_info.items():
            if isinstance(value, list):
                if key in profile:
                    profile[key] = list(set(profile[key] + value))
                else:
                    profile[key] = value
            elif isinstance(value, str) and value:
                profile[key] = value
    except Exception:
        pass
    
    return {"user_profile": profile}