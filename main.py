from openai import OpenAI

# Конфигурация API (AITUNNEL)
client = OpenAI(
    api_key="sk-aitunnel-6nSOCdFD2jUgDD3fzNwfJtqFbtQl8BaL",
    base_url="https://api.aitunnel.ru/v1/"
)

# Системный промпт: задает тему (CS2) и сбалансированный характер
system_prompt = (
    "Ты — опытный игрок и собеседник, специализирующийся на Counter-Strike 2 (CS2). "
    "Ты отлично разбираешься в раскидках, тактиках, экономике, оружии и про-сцене CS2. "
    "Твой характер: сбалансированный. Ты не слишком добрый и не слишком грубый. "
    "Отвечаешь по делу, иногда можешь слегка подкалывать собеседника, если он спрашивает очевидные вещи, но без откровенного хамства. "
    "Общайся на русском языке, используй игровой сленг, где это уместно, и никогда не уходи от темы CS2."
)

# История диалога
messages = [
    {"role": "system", "content": system_prompt}
]

def main():
    print("=" * 50)
    print("🎮 CS2 Chatbot запущен!")
    print("Напиши 'выход', чтобы закрыть консоль.")
    print("=" * 50)
    print("Бот: Ну привет. Давай про КС2. Че хотел узнать? Раски на Мираж или как перестать быть серебром?")

    while True:
        try:
            user_input = input("\nТы: ").strip()
            
            # Проверка на выход
            if user_input.lower() in ["выход", "exit", "quit", "q", ""]:
                if user_input.lower() in ["выход", "exit", "quit", "q"]:
                    print("\nБот: Давай, не пропадай. Увидимся на мажоре.")
                break
                
            messages.append({"role": "user", "content": user_input})
            
            # Запрос к модели qwen3.7-plus
            response = client.chat.completions.create(
                model="qwen3.7-plus",
                messages=messages
            )
            
            bot_reply = response.choices[0].message.content
            print(f"\nБот: {bot_reply}")
            messages.append({"role": "assistant", "content": bot_reply})
            
        except Exception as e:
            print(f"\n[Ошибка API]: {e}")
            # Если произошла ошибка, удаляем последнее сообщение, чтобы не ломать контекст диалога
            if messages and messages[-1]["role"] == "user":
                messages.pop()

if __name__ == "__main__":
    main()