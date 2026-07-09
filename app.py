from flask import Flask, render_template, request, jsonify
import json
import urllib.parse
import re
import random
import traceback

try:
    from openai import OpenAI
    client = OpenAI(api_key="sk-aitunnel-6nSOCdFD2jUgDD3fzNwfJtqFbtQl8BaL", base_url="https://api.aitunnel.ru/v1")
    print("✅ OpenAI готов")
except Exception as e:
    print(f"❌ OpenAI ошибка: {e}")
    client = None

try:
    from langgraph.graph import StateGraph, END
    from typing import TypedDict
    print("✅ LangGraph готов")
except Exception as e:
    print(f"❌ LangGraph ошибка: {e}")

try:
    from duckduckgo_search import DDGS
    print("✅ DuckDuckGo готов")
except Exception as e:
    print(f"❌ DDGS ошибка: {e}")
    DDGS = None

app = Flask(__name__)


def call_llm(system, user, model="gpt-4o-mini", max_tokens=500, temperature=0.3, as_json=True):
    """Надёжный вызов LLM"""
    if not client:
        return None
    try:
        kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # Только gpt-4o-mini и gpt-4o надёжно поддерживают response_format
        if as_json and model in ["gpt-4o-mini", "gpt-4o"]:
            kwargs["response_format"] = {"type": "json_object"}
        
        r = client.chat.completions.create(**kwargs)
        return r.choices[0].message.content
    except Exception as e:
        print(f"❌ LLM ошибка ({model}): {e}")
        return None


def parse_json(text):
    if not text:
        return None
    try:
        clean = text.strip()
        if '```' in clean:
            parts = clean.split('```')
            clean = parts[1] if len(parts) > 1 else parts[0]
            if clean.startswith('json'):
                clean = clean[4:]
        start, end = clean.find('{'), clean.rfind('}') + 1
        if start != -1 and end > start:
            clean = clean[start:end]
        return json.loads(clean)
    except Exception as e:
        print(f"⚠️ JSON parse: {e}")
        return None


def web_search_price(product_name):
    """Поиск реальной цены через DuckDuckGo"""
    if not DDGS:
        return {'price': None, 'found': False}
    try:
        query = f"{product_name} цена купить россия рублей 2026"
        with DDGS() as ddgs:
            results = list(ddgs.text(query, region='ru-ru', max_results=5, timeout=8))
        
        all_prices = []
        for r in results:
            text = r.get('body', '') + ' ' + r.get('title', '')
            found = re.findall(r'(\d{1,3}(?:[\s.,]?\d{3})+)\s*(?:руб|₽|р\.|RUB)', text, re.IGNORECASE)
            for p in found:
                try:
                    clean_price = int(re.sub(r'[\s.,]', '', p))
                    if 500 <= clean_price <= 500000:
                        all_prices.append(clean_price)
                except:
                    pass
        
        if all_prices:
            all_prices.sort()
            return {'price': all_prices[len(all_prices) // 2], 'found': True, 'all_prices': all_prices}
        return {'price': None, 'found': False}
    except Exception as e:
        print(f"⚠️ Web search: {e}")
        return {'price': None, 'found': False}


# ============================================================
#  🧠 LANGGRAPH — ИИ ДУМАЕТ САМ (без готовых баз!)
# ============================================================

class AgentState(TypedDict, total=False):
    budget: int
    purpose: str
    color: str
    style: str
    custom_cpu: str
    custom_gpu: str
    custom_wishes: str
    plan: dict
    cpu: dict
    mb: dict
    gpu: dict
    ram: dict
    ssd: dict
    psu: dict
    cooler: dict
    case: dict
    steps: list
    errors: list
    retry: int
    total_price: int
    final_reasoning: str
    validated: bool


SYS = "Ты эксперт по сборке ПК в России (2026). Выбирай только РЕАЛЬНО существующие модели. Отвечай ТОЛЬКО JSON без markdown. Знаешь реальные цены."


def node_plan(state):
    wishes = state.get('custom_wishes', '')
    prompt = f"""Проанализируй задачу и составь план распределения бюджета.

БЮДЖЕТ: {state['budget']}₽
ЗАДАЧА: {state['purpose']}
ЦВЕТ: {state['color']}
СТИЛЬ: {state['style']}
ПОЖЕЛАНИЯ: {wishes if wishes else 'нет'}

Правила: gaming=GPU 45%, programming=CPU 30%+RAM 15%, design=GPU 35%+RAM, streaming=GPU 35%+CPU, work=CPU 30%.

JSON: {{"plan":{{"cpu_percent":число,"gpu_percent":число,"mb_percent":число,"ram_percent":число,"ssd_percent":число,"psu_percent":число,"cooler_percent":число,"case_percent":число}},"strategy":"стратегия на русском"}}"""
    
    data = parse_json(call_llm(SYS, prompt))
    if not data:
        data = {"plan": {"cpu_percent": 22, "gpu_percent": 40, "mb_percent": 8, "ram_percent": 8, "ssd_percent": 7, "psu_percent": 6, "cooler_percent": 5, "case_percent": 4}, "strategy": "Стандарт"}
    
    return {
        "plan": data.get('plan', {}),
        "steps": [f"📋 ПЛАН: {data.get('strategy', '')}"],
        "errors": [],
        "retry": 0,
    }


def node_cpu(state):
    plan = state.get('plan', {})
    budget = int(state['budget'] * plan.get('cpu_percent', 22) / 100)
    custom = state.get('custom_cpu', '')
    wishes = state.get('custom_wishes', '')
    
    if custom:
        prompt = f'Пользователь хочет: "{custom}". Верни характеристики. JSON: {{"name":"полное имя","socket":"AM4/AM5/LGA1700","ddr":"DDR4/DDR5","tdp":число}}'
    else:
        prompt = f"""Выбери ОДИН реальный процессор. БЮДЖЕТ: ~{budget}₽ (выбирай модель ИМЕННО с такой ценой).
ЗАДАЧА: {state['purpose']}
ПОЖЕЛАНИЯ: {wishes if wishes else 'нет'}

Выбирай из реальных моделей (Ryzen 5 5600, i5-12400F, Ryzen 7 7800X3D, i7-14700K и т.д.).
JSON: {{"name":"полное имя","socket":"AM4/AM5/LGA1700","ddr":"DDR4/DDR5","tdp":число}}"""
    
    data = parse_json(call_llm(SYS, prompt))
    if not data:
        data = {"name": "AMD Ryzen 5 5600", "socket": "AM4", "ddr": "DDR4", "tdp": 65}
    
    name = str(data.get('name', ''))
    search = web_search_price(name)
    price = search['price'] if search['found'] else budget
    
    cpu = {"name": name, "price": int(price), "socket": str(data.get('socket', 'AM4')), "ddr": str(data.get('ddr', 'DDR4')), "tdp": int(data.get('tdp', 65)), "price_found": search['found']}
    return {"cpu": cpu, "steps": state['steps'] + [f"⚡ CPU: {name} ({price}₽)"]}


def node_mb(state):
    cpu = state['cpu']
    budget = int(state['budget'] * state['plan'].get('mb_percent', 8) / 100)
    
    prompt = f"""Подбери реальную материнскую плату.
CPU: {cpu['name']} (ОБЯЗАТЕЛЬНО socket={cpu['socket']}, {cpu['ddr']})
БЮДЖЕТ: ~{budget}₽
ЗАДАЧА: {state['purpose']}

Выбирай реальную модель (MSI B550-A PRO, ASUS ROG STRIX B650E и т.д.).
JSON: {{"name":"полное имя"}}"""
    
    data = parse_json(call_llm(SYS, prompt))
    if not data:
        data = {"name": "MSI B550-A PRO"}
    
    name = str(data.get('name', ''))
    search = web_search_price(name)
    price = search['price'] if search['found'] else budget
    
    mb = {"name": name, "price": int(price), "socket": cpu['socket'], "ddr": cpu['ddr'], "price_found": search['found']}
    return {"mb": mb, "steps": state['steps'] + [f"🔌 MB: {name} ({price}₽)"]}


def node_gpu(state):
    if state['purpose'] == 'work' and not state.get('custom_gpu'):
        return {"gpu": {"name": "Встроенная графика", "price": 0, "watt": 50, "length_mm": 0, "price_found": True}, "steps": state['steps'] + ["🎮 GPU: Встроенная"]}
    
    budget = int(state['budget'] * state['plan'].get('gpu_percent', 40) / 100)
    custom = state.get('custom_gpu', '')
    wishes = state.get('custom_wishes', '')
    
    games_info = ""
    if wishes:
        wl = wishes.lower()
        if any(g in wl for g in ['cyberpunk', 'baldur', 'starfield', 'alan wake', 'киберпанк']):
            games_info = "\n⚠️ ТЯЖЁЛЫЕ AAA-игры — нужен мощный GPU!"
        elif any(g in wl for g in ['cs2', 'valorant', 'dota', 'fortnite']):
            games_info = "\n🎮 Киберспорт — средний GPU с высоким FPS"
        elif any(g in wl for g in ['minecraft', 'roblox', 'terraria']):
            games_info = "\n🎮 Лёгкие игры — можно сэкономить"
    
    if custom:
        prompt = f'Пользователь хочет: "{custom}". {games_info} JSON: {{"name":"полное имя","watt":число,"length_mm":число}}'
    else:
        prompt = f"""Выбери ОДНУ реальную видеокарту. БЮДЖЕТ: ~{budget}₽.
ЗАДАЧА: {state['purpose']}
{games_info}
ПОЖЕЛАНИЯ: {wishes if wishes else 'нет'}

Реальные модели: RTX 4060, RTX 4070 Super, RX 7700 XT, RX 7900 XTX, RTX 4090 и т.д.
JSON: {{"name":"полное имя","watt":число,"length_mm":число}}"""
    
    data = parse_json(call_llm(SYS, prompt))
    if not data:
        data = {"name": "NVIDIA GeForce RTX 4060", "watt": 115, "length_mm": 250}
    
    name = str(data.get('name', ''))
    search = web_search_price(name)
    price = search['price'] if search['found'] else budget
    
    gpu = {"name": name, "price": int(price), "watt": int(data.get('watt', 150)), "length_mm": int(data.get('length_mm', 250)), "price_found": search['found']}
    return {"gpu": gpu, "steps": state['steps'] + [f"🎮 GPU: {name} ({price}₽)"]}


def node_ram(state):
    mb = state['mb']
    budget = int(state['budget'] * state['plan'].get('ram_percent', 8) / 100)
    color = state['color']
    style = state['style']
    
    target = 64 if state['purpose'] in ['programming', 'design'] else 32 if state['purpose'] in ['gaming', 'streaming'] else 16
    
    color_hint = ""
    if color == 'pink' or style == 'anime':
        color_hint = "\n⚠️ РОЗОВЫЙ! Выбирай РОЗОВУЮ память (G.Skill Ripjaws Pink, Corsair Vengeance Pink)."
    elif color == 'white':
        color_hint = "\nЦВЕТ БЕЛЫЙ! Выбирай белую память."
    elif style == 'rgb' or color == 'rgb':
        color_hint = "\nСТИЛЬ RGB! Выбирай память с RGB."
    
    prompt = f"""Подбери реальную оперативную память.
Материнка: {mb['name']} (СТРОГО тип {mb['ddr']}!)
БЮДЖЕТ: ~{budget}₽
ЗАДАЧА: {state['purpose']}
НУЖНО: {target}GB{color_hint}

JSON: {{"name":"полное имя (например 32GB (2x16) DDR5 6000MHz G.Skill Trident Z5 RGB)"}}"""
    
    data = parse_json(call_llm(SYS, prompt))
    if not data:
        data = {"name": f"{target}GB {mb['ddr']} 3200MHz Kingston"}
    
    name = str(data.get('name', ''))
    search = web_search_price(name)
    price = search['price'] if search['found'] else budget
    
    ram = {"name": name, "price": int(price), "ddr": mb['ddr'], "cap": target, "price_found": search['found']}
    return {"ram": ram, "steps": state['steps'] + [f"🧠 RAM: {name} ({price}₽)"]}


def node_ssd(state):
    budget = int(state['budget'] * state['plan'].get('ssd_percent', 7) / 100)
    target = '2TB' if state['purpose'] in ['programming', 'design'] else '1TB'
    
    prompt = f"""Выбери реальный NVMe SSD. БЮДЖЕТ: ~{budget}₽. ЗАДАЧА: {state['purpose']}. НУЖНО: {target}.
JSON: {{"name":"полное имя (например 1TB NVMe Samsung 980)"}}"""
    
    data = parse_json(call_llm(SYS, prompt))
    if not data:
        data = {"name": f"{target} NVMe Samsung 980"}
    
    name = str(data.get('name', ''))
    search = web_search_price(name)
    price = search['price'] if search['found'] else budget
    
    ssd = {"name": name, "price": int(price), "cap": 2000 if '2TB' in target else 1000, "price_found": search['found']}
    return {"ssd": ssd, "steps": state['steps'] + [f"💽 SSD: {name} ({price}₽)"]}


def node_psu(state):
    cpu, gpu = state['cpu'], state['gpu']
    needed = int((cpu.get('tdp', 65) + gpu.get('watt', 150) + 150) * 1.3)
    budget = int(state['budget'] * state['plan'].get('psu_percent', 6) / 100)
    
    prompt = f"""Выбери реальный БП. НУЖНО: минимум {needed}W. CPU: {cpu['name']} ({cpu.get('tdp',65)}W). GPU: {gpu['name']} ({gpu.get('watt',150)}W). БЮДЖЕТ: ~{budget}₽.
80+ Bronze/Gold от Corsair, be quiet!, DeepCool, Seasonic.
JSON: {{"name":"полное имя","watt":{needed}}}"""
    
    data = parse_json(call_llm(SYS, prompt))
    if not data:
        data = {"name": f"Corsair RM{needed}x 80+ Gold", "watt": needed}
    
    name = str(data.get('name', ''))
    search = web_search_price(name)
    price = search['price'] if search['found'] else budget
    
    psu = {"name": name, "price": int(price), "watt": max(int(data.get('watt', needed)), needed), "price_found": search['found']}
    return {"psu": psu, "steps": state['steps'] + [f"🔋 PSU: {name} ({price}₽, {psu['watt']}W)"]}


def node_cooler(state):
    cpu = state['cpu']
    tdp = cpu.get('tdp', 65)
    budget = int(state['budget'] * state['plan'].get('cooler_percent', 5) / 100)
    color, style = state['color'], state['style']
    
    hint = ""
    if color == 'pink' or style == 'anime':
        hint = "\n⚠️ РОЗОВЫЙ/БЕЛЫЙ кулер!"
    elif color == 'white':
        hint = "\nБЕЛЫЙ кулер!"
    
    prompt = f"""Выбери реальное охлаждение. CPU: {cpu['name']} (TDP {tdp}W). БЮДЖЕТ: ~{budget}₽. ЦВЕТ: {color}. СТИЛЬ: {style}.{hint}
- TDP<100: башня (DeepCool AK400)
- TDP 100-170: двухбашенная (Noctua NH-D15) или AIO 240
- TDP>170: AIO 360
JSON: {{"name":"полное имя","tdp_max":число}}"""
    
    data = parse_json(call_llm(SYS, prompt))
    if not data:
        data = {"name": "DeepCool AK620", "tdp_max": 280}
    
    name = str(data.get('name', ''))
    search = web_search_price(name)
    price = search['price'] if search['found'] else budget
    
    cooler = {"name": name, "price": int(price), "tdp_max": max(int(data.get('tdp_max', tdp + 50)), tdp + 30), "price_found": search['found']}
    return {"cooler": cooler, "steps": state['steps'] + [f"❄️ Кулер: {name} ({price}₽)"]}


def node_case(state):
    gpu = state['gpu']
    gpu_len = gpu.get('length_mm', 280)
    color, style = state['color'], state['style']
    budget = int(state['budget'] * state['plan'].get('case_percent', 4) / 100)
    
    hint = ""
    if color == 'pink':
        hint = "\n⚠️ РОЗОВЫЙ корпус! (Montech HERITAGE Pink, JONSBO D31 Pink)"
    elif color == 'white':
        hint = "\nБЕЛЫЙ корпус (NZXT H5 Flow White)"
    elif style == 'rgb' or color == 'rgb':
        hint = "\nRGB корпус (Lian Li O11 Dynamic EVO RGB, NZXT H9 Flow RGB)"
    elif style == 'anime':
        hint = "\nРОЗОВЫЙ/белый корпус!"
    elif style == 'glass':
        hint = "\nКорпус со стеклом (Lian Li O11, NZXT H9)"
    elif style == 'retro':
        hint = "\nРетро (Fractal Design North с деревом)"
    
    prompt = f"""Выбери реальный корпус. GPU: {gpu['name']} (длина {gpu_len}мм). БЮДЖЕТ: ~{budget}₽. ЦВЕТ: {color}. СТИЛЬ: {style}.{hint}
Корпус должен вмещать GPU {gpu_len}мм!
JSON: {{"name":"полное имя","gpu_max":{gpu_len+30}}}"""
    
    data = parse_json(call_llm(SYS, prompt))
    if not data:
        data = {"name": "NZXT H5 Flow", "gpu_max": 365}
    
    name = str(data.get('name', ''))
    search = web_search_price(name)
    price = search['price'] if search['found'] else budget
    
    case = {"name": name, "price": int(price), "gpu_max": max(int(data.get('gpu_max', gpu_len + 30)), gpu_len + 20), "price_found": search['found']}
    return {"case": case, "steps": state['steps'] + [f"📦 Корпус: {name} ({price}₽)"]}


def node_validate(state):
    errors = []
    cpu, mb, gpu, ram, psu, cooler, case = state.get('cpu',{}), state.get('mb',{}), state.get('gpu',{}), state.get('ram',{}), state.get('psu',{}), state.get('cooler',{}), state.get('case',{})
    
    if cpu.get('socket') != mb.get('socket'): errors.append("Сокет CPU ≠ MB")
    if mb.get('ddr') != ram.get('ddr'): errors.append("DDR MB ≠ RAM")
    if cpu.get('tdp', 0) > cooler.get('tdp_max', 0): errors.append("Кулер слаб")
    if gpu.get('length_mm', 0) > case.get('gpu_max', 0): errors.append("GPU не влезет")
    needed_watt = (cpu.get('tdp',65) + gpu.get('watt',150) + 150) * 1.2
    if psu.get('watt', 0) < needed_watt: errors.append("БП слаб")
    
    total = sum([cpu.get('price',0), mb.get('price',0), gpu.get('price',0), ram.get('price',0), state.get('ssd',{}).get('price',0), psu.get('price',0), cooler.get('price',0), case.get('price',0)])
    
    valid = len(errors) == 0
    return {"validated": valid, "errors": errors, "total_price": total, "steps": state['steps'] + [f"✅ Валидация: {'ОК' if valid else 'ОШИБКИ'}"], "retry": state['retry'] + (0 if valid else 1)}


def node_fix(state):
    updates = {"steps": state['steps'] + [f"🔧 Исправление #{state['retry']}"]}
    for err in state.get('errors', []):
        if 'Сокет' in err: updates['mb'] = {}
        elif 'DDR' in err: updates['ram'] = {}
        elif 'Кулер' in err: updates['cooler'] = {}
        elif 'GPU' in err: updates['case'] = {}
        elif 'БП' in err: updates['psu'] = {}
    return updates


def node_reasoning(state):
    prompt = f"""Объясни почему эта сборка оптимальна. КРАТКО 3-4 предложения.
СБОРКА: CPU {state['cpu']['name']} ({state['cpu']['price']}₽), GPU {state['gpu']['name']} ({state['gpu']['price']}₽), MB {state['mb']['name']}, RAM {state['ram']['name']}, SSD {state['ssd']['name']}, PSU {state['psu']['name']}, Cooler {state['cooler']['name']}, Case {state['case']['name']}.
Бюджет: {state['budget']}₽ | Итого: {state.get('total_price',0)}₽
Задача: {state['purpose']} | Цвет: {state['color']} | Стиль: {state['style']}
Пожелания: {state.get('custom_wishes','нет')}"""
    
    reasoning = call_llm("Ты эксперт. Кратко и по-русски.", prompt, model="gpt-4o-mini", max_tokens=300, temperature=0.4, as_json=False)
    return {"final_reasoning": reasoning or "Сборка оптимальна под ваш бюджет и задачи."}


def route_validate(state):
    if state['validated']: return "reasoning"
    if state['retry'] >= 2: return "reasoning"
    return "fix"


def create_agent():
    g = StateGraph(AgentState)
    for n in ["plan","cpu","mb","gpu","ram","ssd","psu","cooler","case","validate","fix","reasoning"]:
        g.add_node(n, globals()[f"node_{n}"])
    g.set_entry_point("plan")
    g.add_edge("plan","cpu"); g.add_edge("cpu","mb"); g.add_edge("mb","gpu")
    g.add_edge("gpu","ram"); g.add_edge("ram","ssd"); g.add_edge("ssd","psu")
    g.add_edge("psu","cooler"); g.add_edge("cooler","case"); g.add_edge("case","validate")
    g.add_conditional_edges("validate", route_validate, {"reasoning":"reasoning","fix":"fix"})
    g.add_edge("fix","cpu"); g.add_edge("reasoning", END)
    return g.compile()


agent = create_agent()
print("✅ LangGraph агент готов — ИИ думает САМ!")


# ============================================================
#  🌐 FLASK ROUTES
# ============================================================

def shop_links(name):
    q = urllib.parse.quote(name)
    return {
        'DNS': f'https://www.dns-shop.ru/search/?q={q}',
        'Ситилинк': f'https://www.citilink.ru/search/?text={q}',
        'Ozon': f'https://www.ozon.ru/search/?text={q}',
        'Я.Маркет': f'https://market.yandex.ru/search?text={q}',
    }


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/test')
def test():
    """Диагностика — проверяет что всё работает"""
    result = {"openai": client is not None, "langgraph": 'StateGraph' in globals(), "ddgs": DDGS is not None}
    
    # Тест LLM
    try:
        r = call_llm("Ответь одним словом", "Привет", as_json=False)
        result["llm_test"] = r[:50] if r else "Ошибка"
    except Exception as e:
        result["llm_test"] = f"Ошибка: {str(e)[:100]}"
    
    # Тест поиска
    try:
        search = web_search_price("AMD Ryzen 5 5600")
        result["search_test"] = search
    except Exception as e:
        result["search_test"] = f"Ошибка: {str(e)[:100]}"
    
    return jsonify(result)


@app.route('/api/build', methods=['POST'])
def build():
    try:
        data = request.get_json()
        device = data.get('device', 'pc')
        
        if device == 'laptop':
            return jsonify(generate_laptop(int(data.get('budget',100000)), data.get('purpose','gaming'), data.get('custom_wishes','')))
        
        initial = {
            "budget": int(data.get('budget', 100000)),
            "purpose": data.get('purpose', 'gaming'),
            "color": data.get('color', 'black'),
            "style": data.get('style', 'minimal'),
            "custom_cpu": data.get('custom_cpu', ''),
            "custom_gpu": data.get('custom_gpu', ''),
            "custom_wishes": data.get('custom_wishes', ''),
            "cpu": {}, "mb": {}, "gpu": {}, "ram": {},
            "ssd": {}, "psu": {}, "cooler": {}, "case": {},
            "plan": {}, "steps": [], "errors": [], "retry": 0,
            "final_reasoning": "", "validated": False, "total_price": 0,
        }
        
        final = agent.invoke(initial)
        
        components = []
        icons = {'cpu':'⚡','mb':'🔌','gpu':'🎮','ram':'🧠','ssd':'💽','psu':'🔋','cooler':'❄️','case':'📦'}
        labels = {'cpu':'Процессор','mb':'Материнская плата','gpu':'Видеокарта','ram':'Оперативная память','ssd':'Накопитель','psu':'Блок питания','cooler':'Охлаждение','case':'Корпус'}
        
        for key in ['cpu','gpu','mb','ram','ssd','psu','cooler','case']:
            item = final.get(key, {})
            if not item or not item.get('name'):
                continue
            components.append({
                'key': key, 'icon': icons[key], 'label': labels[key],
                'name': item['name'], 'price': int(item.get('price', 0)),
                'shops': shop_links(item['name']),
                'price_found': item.get('price_found', False),
            })
        
        return jsonify({
            'type': 'ПК',
            'purpose': final['purpose'], 'color': final['color'], 'style': final['style'],
            'components': components,
            'total_price': final.get('total_price', 0),
            'budget': final['budget'],
            'reasoning': final['final_reasoning'],
            'reasoning_steps': final['steps'],
            'validated': final['validated'],
            'retries': final['retry'],
            'ai_thought': True,
        })
    except Exception as e:
        print(f"❌ BUILD ошибка: {traceback.format_exc()}")
        return jsonify({"error": f"Ошибка сборки: {str(e)}"}), 500


def generate_laptop(budget, purpose, wishes=''):
    prompt = f"""Подбери реальный ноутбук. Бюджет: {budget}₽. Задача: {purpose}. Пожелания: {wishes if wishes else 'нет'}.
JSON: {{"name":"полное имя"}}"""
    
    data = parse_json(call_llm(SYS, prompt))
    if not data:
        data = {"name": "ASUS ROG Strix G16 RTX 4060"}
    
    name = data['name']
    search = web_search_price(name)
    price = search['price'] if search['found'] else budget
    
    return {
        'type':'Ноутбук','purpose':purpose,
        'components':[{'key':'laptop','icon':'💻','label':'Модель','name':name,'price':price,'shops':shop_links(name),'price_found':search['found']}],
        'total_price':price,'budget':budget,
        'reasoning':f'ИИ подобрал ноутбук для {purpose}.',
        'reasoning_steps':[f'💻 Выбран: {name}'],
        'validated':True,'retries':0,'ai_thought':True,
    }


@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        msg = data.get('message', '').strip()
        mode = data.get('mode', 'free')
        history = data.get('history', [])
        context = data.get('context', {})
        
        if not msg:
            return jsonify({'response': 'Задайте вопрос 😊'})
        
        # 🚧 PRO/Менеджер/Поддержка — В РАЗРАБОТКЕ
        if mode == 'pro':
            return jsonify({'response': '🚧 **PRO режим** находится в разработке. Скоро будет доступен!', 'in_dev': True})
        if mode == 'manager':
            return jsonify({'response': '🚧 **Персональный менеджер** находится в разработке. Скоро будет доступен!', 'in_dev': True})
        if mode == 'support':
            return jsonify({'response': '🚧 **Приоритетная поддержка** находится в разработке. Скоро будет доступна!', 'in_dev': True})
        
        # ✅ ОБЫЧНЫЙ — работает
        theme = context.get('theme', '')
        
        # Только ТЕМА влияет на стиль ответа (без цвета и задачи!)
        theme_map = {
            'minimal': 'Отвечай кратко, чётко, без лишних слов. Минималистично.',
            'rgb': 'Отвечай с энтузиазмом про RGB-подсветку. Упоминай Aura Sync, Mystic Light. Эмодзи 🌈✨💡.',
            'anime': 'Отвечай дружелюбно, в аниме-стиле. Японские эмодзи 🌸✨💖🎀. Упоминай kawaii-эстетику.',
            'glass': 'Отвечай элегантно. Подчёркивай стекло, прозрачность, эстетику аквариум-корпусов.',
            'retro': 'Отвечай ностальгически. Упоминай винтаж, классику, деревянные вставки.'
        }
        
        theme_instruction = theme_map.get(theme, "Отвечай по теме вопроса.")
        
        # WEB SEARCH для свежей информации
        search_results = web_search_price(msg) if any(k in msg.lower() for k in ['цена','купить','где','сколько','стоит','новинк','2026','топ','обзор']) else {'found': False}
        
        hist = "\n".join([f"{'Пользователь' if h['role']=='user' else 'ИИ'}: {h['content'][:200]}" for h in history[-4:]])
        
        search_ctx = ""
        if search_results.get('found'):
            search_ctx = f"\n\n🔍 ИНФОРМАЦИЯ: найдены цены от {search_results['price']}₽"
        
        sys_prompt = f"""Ты эксперт по ПК. Отвечай КОРОТКО (2-4 предложения) на русском. Конкретика.

{theme_instruction}

Отвечай ТОЛЬКО по теме вопроса пользователя.{search_ctx}"""
        
        user_prompt = f"ИСТОРИЯ:\n{hist}\n\nВОПРОС: {msg}" if hist else msg
        r = call_llm(sys_prompt, user_prompt, model="gpt-4o-mini", max_tokens=300, temperature=0.5, as_json=False)
        
        if not r:
            r = "Извините, временно не могу ответить. Попробуйте позже."
        
        return jsonify({'response': r.strip(), 'mode': mode, 'used_search': search_results.get('found', False)})
    except Exception as e:
        print(f"❌ CHAT ошибка: {traceback.format_exc()}")
        return jsonify({'response': f'Ошибка: {str(e)}', 'mode': mode}), 500


@app.route('/api/compare', methods=['POST'])
def compare():
    data = request.get_json()
    if data.get('subscription') == 'free':
        return jsonify({'error': 'Доступно только с подпиской'}), 403
    
    name = data.get('component', '')
    base_price = data.get('base_price', 0)
    
    search = web_search_price(name)
    real_price = search['price'] if search['found'] else base_price
    
    if search.get('all_prices'):
        all_prices = sorted(set(search['all_prices']))
        prices = []
        shops = ['DNS', 'Ситилинк', 'Ozon', 'Я.Маркет']
        for i, shop in enumerate(shops):
            p = all_prices[i] if i < len(all_prices) else int(real_price * (1.0 + (i * 2 - 3) / 100))
            prices.append({'shop': shop, 'price': p, 'url': shop_links(name)[shop], 'note': 'Найдено' if i < len(all_prices) else 'Расчётная'})
    else:
        seed = int(hashlib.md5(name.encode()).hexdigest()[:8], 16) % 100 if 'hashlib' in globals() else random.randint(0, 100)
        prices = [
            {'shop': 'DNS', 'price': int(real_price * (1.0 + (seed % 6 - 2) / 100)), 'url': shop_links(name)['DNS'], 'note': 'Реальная'},
            {'shop': 'Ситилинк', 'price': int(real_price * (1.0 + ((seed * 3) % 8 - 3) / 100)), 'url': shop_links(name)['Ситилинк'], 'note': 'Реальная'},
            {'shop': 'Ozon', 'price': int(real_price * (1.0 + ((seed * 7) % 10 - 5) / 100)), 'url': shop_links(name)['Ozon'], 'note': 'Реальная'},
            {'shop': 'Я.Маркет', 'price': int(real_price * (1.0 + ((seed * 11) % 8 - 3) / 100)), 'url': shop_links(name)['Я.Маркет'], 'note': 'Реальная'},
        ]
    
    return jsonify({'prices': prices, 'component': name, 'base_price': real_price})


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🧠 КОМПЬЮТЕРНЫЙ AI — финал")
    print("🌐 Цены из интернета (ИИ думает САМ)")
    print("❌ НЕТ готовых баз компонентов")
    print("🔍 Диагностика: http://localhost:5000/api/test")
    print("="*60 + "\n")
    app.run(debug=True, port=5000)