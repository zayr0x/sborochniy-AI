from flask import Flask, render_template, request, jsonify
import json
import urllib.parse
import re
import random
import traceback
import hashlib
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from openai import OpenAI
    client = OpenAI(api_key="sk-aitunnel-6nSOCdFD2jUgDD3fzNwfJtqFbtQl8BaL", base_url="https://api.aitunnel.ru/v1")
    print("✅ OpenAI готов")
except Exception as e:
    print(f"❌ OpenAI: {e}")
    client = None

try:
    from langgraph.graph import StateGraph, END
    from typing import TypedDict
except: pass

try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except:
    DDGS_AVAILABLE = False
    DDGS = None

app = Flask(__name__)

# ============================================================
#  📧 НАСТРОЙКИ EMAIL (Gmail SMTP)
# ============================================================
SMTP_EMAIL = "sborochniy.ai.verify@gmail.com"
SMTP_PASSWORD = "YOUR_APP_PASSWORD_HERE"  # Замени на свой 16-значный пароль
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

def send_email(to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"✅ Email отправлен на {to_email}")
        return True
    except Exception as e:
        print(f"❌ Ошибка отправки email: {e}")
        return False

USERS_DB = {}
VERIFICATION_CODES = {}

def call_llm(system, user, model="gpt-4o-mini", max_tokens=500, temperature=0.3, as_json=True):
    if not client: return None
    try:
        kwargs = {"model": model, "messages": [{"role":"system","content":system},{"role":"user","content":user}], "temperature": temperature, "max_tokens": max_tokens}
        if as_json and model in ["gpt-4o-mini", "gpt-4o"]:
            kwargs["response_format"] = {"type": "json_object"}
        r = client.chat.completions.create(**kwargs)
        return r.choices[0].message.content
    except Exception as e:
        print(f"❌ LLM: {e}")
        return None

def parse_json(text):
    if not text: return None
    try:
        clean = text.strip()
        if '```' in clean:
            parts = clean.split('```')
            clean = parts[1] if len(parts) > 1 else parts[0]
            if clean.startswith('json'): clean = clean[4:]
        start, end = clean.find('{'), clean.rfind('}') + 1
        if start != -1 and end > start:
            clean = clean[start:end]
        return json.loads(clean)
    except:
        return None

def search_prices_for_component(product_name):
    if not DDGS_AVAILABLE:
        return {'price': None, 'found': False, 'real_prices': {}}
    
    print(f"\n🔍 Поиск цен для: {product_name}")
    results = {}
    
    shops_queries = [
        ('DNS', [f'site:dns-shop.ru {product_name} цена', f'dns-shop.ru {product_name} купить']),
        ('Ситилинк', [f'site:citilink.ru {product_name} цена', f'citilink.ru {product_name} купить']),
        ('Ozon', [f'site:ozon.ru {product_name}', f'ozon.ru {product_name} цена']),
        ('Я.Маркет', [f'site:market.yandex.ru {product_name}', f'яндекс маркет {product_name} цена']),
    ]
    
    for shop_name, queries in shops_queries:
        prices = []
        best_url = ''
        
        for query in queries:
            try:
                with DDGS() as ddgs:
                    search_results = list(ddgs.text(query, region='ru-ru', max_results=5, timeout=10))
                
                for r in search_results:
                    text = r.get('body', '') + ' ' + r.get('title', '')
                    patterns = [
                        r'(\d{1,3}(?:[\s.,]?\d{3})+)\s*(?:руб|₽|р\.|RUB)',
                        r'(?:цена|стоит|ценник)\s*:?\s*(\d{1,3}(?:[\s.,]?\d{3})+)',
                        r'(\d{4,6})\s*(?:руб|₽)',
                    ]
                    for pattern in patterns:
                        found = re.findall(pattern, text, re.IGNORECASE)
                        for p in found:
                            try:
                                clean = int(re.sub(r'[\s.,]', '', p))
                                if 500 <= clean <= 500000:
                                    prices.append(clean)
                            except: pass
                    if not best_url and r.get('href'):
                        best_url = r['href']
                if prices:
                    break
            except Exception as e:
                print(f"  ⚠️ {shop_name} query failed: {e}")
                continue
        
        if prices:
            prices = sorted(set(prices))
            if len(prices) > 4:
                trim = len(prices) // 5
                prices = prices[trim:-trim]
            results[shop_name] = {
                'shop': shop_name,
                'prices': prices[:5],
                'min': min(prices),
                'median': prices[len(prices)//2],
                'url': best_url or f"https://www.google.com/search?q={urllib.parse.quote(product_name + ' ' + shop_name)}"
            }
            print(f"  ✅ {shop_name}: {results[shop_name]['median']}₽ ({len(prices)} цен)")
    
    if not results:
        try:
            query = f"{product_name} цена купить россия рублей 2026"
            with DDGS() as ddgs:
                search_results = list(ddgs.text(query, region='ru-ru', max_results=8, timeout=10))
            all_prices = []
            for r in search_results:
                text = r.get('body', '') + ' ' + r.get('title', '')
                found = re.findall(r'(\d{1,3}(?:[\s.,]?\d{3})+)\s*(?:руб|₽|р\.|RUB)', text, re.IGNORECASE)
                for p in found:
                    try:
                        clean = int(re.sub(r'[\s.,]', '', p))
                        if 500 <= clean <= 500000:
                            all_prices.append(clean)
                    except: pass
            if all_prices:
                all_prices = sorted(set(all_prices))
                if len(all_prices) > 4:
                    trim = len(all_prices) // 5
                    all_prices = all_prices[trim:-trim]
                median = all_prices[len(all_prices)//2]
                results['Общая цена'] = {
                    'shop': 'Средняя цена',
                    'prices': all_prices[:5],
                    'min': min(all_prices),
                    'median': median,
                    'url': f"https://www.google.com/search?q={urllib.parse.quote(product_name)}"
                }
        except: pass
    
    return {'price': None, 'found': len(results) > 0, 'real_prices': results}

def web_search_price(product_name):
    search = search_prices_for_component(product_name)
    if search['found']:
        all_medians = [data['median'] for data in search['real_prices'].values()]
        all_medians.sort()
        median = all_medians[len(all_medians)//2]
        return {'price': median, 'found': True, 'real_prices': search['real_prices'], 'all_medians': all_medians}
    
    fallback_prices = {
        'AMD Ryzen 5 5600': 11500, 'AMD Ryzen 5 5500': 8500, 'AMD Ryzen 7 5700X': 15000,
        'AMD Ryzen 5 7600': 18500, 'AMD Ryzen 7 7700X': 27000, 'AMD Ryzen 7 7800X3D': 34000,
        'AMD Ryzen 9 7900X': 41000, 'AMD Ryzen 9 7950X': 52000, 'Intel Core i5-12400F': 12000,
        'Intel Core i5-13600KF': 22000, 'Intel Core i7-14700KF': 39000, 'Intel Core i9-14900KF': 53000,
        'NVIDIA GeForce RTX 4060': 32000, 'NVIDIA GeForce RTX 4060 Ti': 41000,
        'NVIDIA GeForce RTX 4070 Super': 57000, 'NVIDIA GeForce RTX 4070 Ti Super': 74000,
        'NVIDIA GeForce RTX 4080 Super': 103000, 'NVIDIA GeForce RTX 4090': 158000,
        'AMD Radeon RX 6600': 19000, 'AMD Radeon RX 7600': 28000, 'AMD Radeon RX 7700 XT': 43000,
    }
    for key, price in fallback_prices.items():
        if key.lower() in product_name.lower():
            return {'price': price, 'found': True, 'real_prices': {'Fallback': {'shop': 'Ориентировочная', 'prices': [price], 'min': price, 'median': price, 'url': '#'}}, 'all_medians': [price]}
    return {'price': None, 'found': False, 'real_prices': {}}

# ============================================================
#  🧠 LANGGRAPH
# ============================================================

class AgentState(TypedDict, total=False):
    budget: int; purpose: str; color: str; style: str
    custom_cpu: str; custom_gpu: str; custom_wishes: str
    plan: dict; cpu: dict; mb: dict; gpu: dict; ram: dict
    ssd: dict; psu: dict; cooler: dict; case: dict
    steps: list; errors: list; retry: int
    total_price: int; final_reasoning: str; validated: bool

SYS = "Ты эксперт по сборке ПК в России. Выбирай ТОЛЬКО реально существующие модели. Отвечай ТОЛЬКО JSON."

def node_planning(state):
    prompt = f"""Составь план распределения бюджета. Бюджет: {state['budget']}₽. Задача: {state['purpose']}.
gaming=GPU 45%, programming=CPU 30%+RAM 15%, design=GPU 35%+RAM, streaming=GPU 35%+CPU, work=CPU 30%.
JSON: {{"plan":{{"cpu_percent":число,"gpu_percent":число,"mb_percent":число,"ram_percent":число,"ssd_percent":число,"psu_percent":число,"cooler_percent":число,"case_percent":число}},"strategy":"стратегия"}}"""
    data = parse_json(call_llm(SYS, prompt))
    if not data:
        data = {"plan":{"cpu_percent":22,"gpu_percent":40,"mb_percent":8,"ram_percent":8,"ssd_percent":7,"psu_percent":6,"cooler_percent":5,"case_percent":4},"strategy":"Стандарт"}
    return {"plan":data.get('plan',{}), "steps":[f"📋 ПЛАН: {data.get('strategy','')}"], "errors":[], "retry":0}

def node_cpu(state):
    budget = int(state['budget'] * state['plan'].get('cpu_percent', 22) / 100)
    custom = state.get('custom_cpu', '')
    wishes = state.get('custom_wishes', '')
    if custom:
        prompt = f'Пользователь хочет: "{custom}". JSON: {{"name":"полное имя","socket":"AM4/AM5/LGA1700","ddr":"DDR4/DDR5","tdp":число}}'
    else:
        prompt = f"""Выбери ОДИН реальный процессор. БЮДЖЕТ НА CPU: {budget}₽. ЗАДАЧА: {state['purpose']}. ПОЖЕЛАНИЯ: {wishes if wishes else 'нет'}.
JSON: {{"name":"полное имя","socket":"AM4/AM5/LGA1700","ddr":"DDR4/DDR5","tdp":число}}"""
    data = parse_json(call_llm(SYS, prompt))
    if not data: data = {"name":"AMD Ryzen 5 5600","socket":"AM4","ddr":"DDR4","tdp":65}
    name = str(data.get('name', ''))
    search = web_search_price(name)
    price = search['price'] if search['found'] else budget
    cpu = {"name":name,"price":int(price),"socket":str(data.get('socket','AM4')),"ddr":str(data.get('ddr','DDR4')),"tdp":int(data.get('tdp',65)),"price_found":search['found']}
    return {"cpu":cpu,"steps":state['steps']+[f"⚡ CPU: {name} ({price}₽)"]}

def node_mb(state):
    cpu = state['cpu']
    budget = int(state['budget'] * state['plan'].get('mb_percent', 8) / 100)
    prompt = f"""Материнская плата под {cpu['name']} (socket={cpu['socket']}, {cpu['ddr']}). Бюджет: {budget}₽. JSON: {{"name":"полное имя"}}"""
    data = parse_json(call_llm(SYS, prompt))
    if not data: data = {"name":"MSI B550-A PRO"}
    name = str(data.get('name', ''))
    search = web_search_price(name)
    price = search['price'] if search['found'] else budget
    mb = {"name":name,"price":int(price),"socket":cpu['socket'],"ddr":cpu['ddr'],"price_found":search['found']}
    return {"mb":mb,"steps":state['steps']+[f"🔌 MB: {name} ({price}₽)"]}

def node_gpu(state):
    if state['purpose'] == 'work' and not state.get('custom_gpu'):
        return {"gpu":{"name":"Встроенная графика","price":0,"watt":50,"length_mm":0,"price_found":True},"steps":state['steps']+["🎮 GPU: Встроенная"]}
    budget = int(state['budget'] * state['plan'].get('gpu_percent', 40) / 100)
    custom = state.get('custom_gpu', '')
    if custom:
        prompt = f'GPU: "{custom}". JSON: {{"name":"полное имя","watt":число,"length_mm":число}}'
    else:
        prompt = f"""Видеокарта. Бюджет: {budget}₽. Задача: {state['purpose']}. JSON: {{"name":"полное имя","watt":число,"length_mm":число}}"""
    data = parse_json(call_llm(SYS, prompt))
    if not data: data = {"name":"NVIDIA GeForce RTX 4060 8GB","watt":115,"length_mm":250}
    name = str(data.get('name',''))
    search = web_search_price(name)
    price = search['price'] if search['found'] else budget
    gpu = {"name":name,"price":int(price),"watt":int(data.get('watt',150)),"length_mm":int(data.get('length_mm',250)),"price_found":search['found']}
    return {"gpu":gpu,"steps":state['steps']+[f"🎮 GPU: {name} ({price}₽)"]}

def node_ram(state):
    mb = state['mb']
    budget = int(state['budget'] * state['plan'].get('ram_percent', 8) / 100)
    color, style = state['color'], state['style']
    target = 64 if state['purpose'] in ['programming','design'] else 32 if state['purpose'] in ['gaming','streaming'] else 16
    color_hint = ""
    if color == 'pink' or style == 'anime': color_hint = "\n⚠️ РОЗОВУЮ память!"
    elif color == 'white': color_hint = "\nБЕЛУЮ память!"
    elif style == 'rgb' or color == 'rgb': color_hint = "\nС RGB подсветкой!"
    prompt = f"""Оперативная память. Материнка: {mb['name']} (СТРОГО {mb['ddr']}!). БЮДЖЕТ: {budget}₽. НУЖНО: {target}GB{color_hint}. JSON: {{"name":"полное имя"}}"""
    data = parse_json(call_llm(SYS, prompt))
    if not data: data = {"name":f"{target}GB (2x{target//2}) {mb['ddr']} 3200MHz Kingston Fury Beast"}
    name = str(data.get('name',''))
    search = web_search_price(name)
    if search['found']:
        price = search['price']
    else:
        ram_prices = {(16,'DDR4'):4500,(32,'DDR4'):8500,(32,'DDR5'):11000,(64,'DDR5'):21000,(128,'DDR5'):42000}
        price = ram_prices.get((target, mb['ddr']), budget)
    ram = {"name":name,"price":int(price),"ddr":mb['ddr'],"cap":target,"price_found":search['found']}
    return {"ram":ram,"steps":state['steps']+[f"🧠 RAM: {name} ({price}₽)"]}

def node_ssd(state):
    budget = int(state['budget'] * state['plan'].get('ssd_percent', 7) / 100)
    target = '2TB' if state['purpose'] in ['programming','design'] else '1TB'
    prompt = f"NVMe SSD. Бюджет: {budget}₽. Нужно: {target}. JSON: {{\"name\":\"полное имя\"}}"
    data = parse_json(call_llm(SYS, prompt))
    if not data: data = {"name":f"{target} NVMe Samsung 980"}
    name = str(data.get('name',''))
    search = web_search_price(name)
    price = search['price'] if search['found'] else budget
    ssd = {"name":name,"price":int(price),"cap":2000 if '2TB' in target else 1000,"price_found":search['found']}
    return {"ssd":ssd,"steps":state['steps']+[f"💽 SSD: {name} ({price}₽)"]}

def node_psu(state):
    cpu, gpu = state['cpu'], state['gpu']
    needed = int((cpu.get('tdp',65) + gpu.get('watt',150) + 150) * 1.3)
    budget = int(state['budget'] * state['plan'].get('psu_percent', 6) / 100)
    prompt = f"БП минимум {needed}W. CPU: {cpu['name']} ({cpu.get('tdp',65)}W). GPU: {gpu['name']} ({gpu.get('watt',150)}W). Бюджет: {budget}₽. JSON: {{\"name\":\"полное имя\",\"watt\":{needed}}}"
    data = parse_json(call_llm(SYS, prompt))
    if not data: data = {"name":f"Corsair RM{needed}x 80+ Gold","watt":needed}
    name = str(data.get('name',''))
    search = web_search_price(name)
    price = search['price'] if search['found'] else budget
    psu = {"name":name,"price":int(price),"watt":max(int(data.get('watt',needed)),needed),"price_found":search['found']}
    return {"psu":psu,"steps":state['steps']+[f"🔋 PSU: {name} ({price}₽, {psu['watt']}W)"]}

def node_cooler(state):
    cpu = state['cpu']
    tdp = cpu.get('tdp', 65)
    budget = int(state['budget'] * state['plan'].get('cooler_percent', 5) / 100)
    color, style = state['color'], state['style']
    hint = ""
    if color == 'pink' or style == 'anime': hint = "\n⚠️ РОЗОВЫЙ/БЕЛЫЙ!"
    elif color == 'white': hint = "\nБЕЛЫЙ!"
    elif style == 'rgb' or color == 'rgb': hint = "\nС RGB!"
    prompt = f"""Охлаждение для {cpu['name']} (TDP {tdp}W). Бюджет: {budget}₽. {hint}. JSON: {{"name":"полное имя","tdp_max":число}}"""
    data = parse_json(call_llm(SYS, prompt))
    if not data: data = {"name":"DeepCool AK620","tdp_max":280}
    name = str(data.get('name',''))
    search = web_search_price(name)
    price = search['price'] if search['found'] else budget
    cooler = {"name":name,"price":int(price),"tdp_max":max(int(data.get('tdp_max',tdp+50)),tdp+30),"price_found":search['found']}
    return {"cooler":cooler,"steps":state['steps']+[f"❄️ Кулер: {name} ({price}₽)"]}

def node_case(state):
    gpu = state['gpu']
    gpu_len = gpu.get('length_mm', 280)
    color, style = state['color'], state['style']
    budget = int(state['budget'] * state['plan'].get('case_percent', 4) / 100)
    hint = ""
    if color == 'pink': hint = "\n⚠️ РОЗОВЫЙ!"
    elif color == 'white': hint = "\nБЕЛЫЙ!"
    elif style == 'rgb' or color == 'rgb': hint = "\nRGB!"
    elif style == 'glass': hint = "\nСо стеклом!"
    elif style == 'retro': hint = "\nРетро!"
    prompt = f"""Корпус. GPU: {gpu['name']} ({gpu_len}мм). Бюджет: {budget}₽. Цвет: {color}, Стиль: {style}.{hint}. JSON: {{"name":"полное имя","gpu_max":{gpu_len+30}}}"""
    data = parse_json(call_llm(SYS, prompt))
    if not data: data = {"name":"NZXT H5 Flow","gpu_max":365}
    name = str(data.get('name',''))
    search = web_search_price(name)
    price = search['price'] if search['found'] else budget
    case = {"name":name,"price":int(price),"gpu_max":max(int(data.get('gpu_max',gpu_len+30)),gpu_len+20),"price_found":search['found']}
    return {"case":case,"steps":state['steps']+[f"📦 Корпус: {name} ({price}₽)"]}

def node_validate(state):
    errors = []
    cpu, mb, gpu, ram, psu, cooler, case = state.get('cpu',{}), state.get('mb',{}), state.get('gpu',{}), state.get('ram',{}), state.get('psu',{}), state.get('cooler',{}), state.get('case',{})
    if cpu.get('socket') != mb.get('socket'): errors.append("Сокет CPU ≠ MB")
    if mb.get('ddr') != ram.get('ddr'): errors.append("DDR MB ≠ RAM")
    if cpu.get('tdp',0) > cooler.get('tdp_max',0): errors.append("Кулер слаб")
    if gpu.get('length_mm',0) > case.get('gpu_max',0): errors.append("GPU не влезет")
    needed_watt = (cpu.get('tdp',65) + gpu.get('watt',150) + 150) * 1.2
    if psu.get('watt',0) < needed_watt: errors.append("БП слаб")
    total = sum([cpu.get('price',0), mb.get('price',0), gpu.get('price',0), ram.get('price',0), state.get('ssd',{}).get('price',0), psu.get('price',0), cooler.get('price',0), case.get('price',0)])
    valid = len(errors) == 0
    return {"validated":valid,"errors":errors,"total_price":total,"steps":state['steps']+[f"✅ Валидация: {'ОК' if valid else 'ОШИБКИ'}"],"retry":state['retry']+(0 if valid else 1)}

def node_fix(state):
    updates = {"steps":state['steps']+[f"🔧 Исправление #{state['retry']}"]}
    for err in state.get('errors',[]):
        if 'Сокет' in err: updates['mb'] = {}
        elif 'DDR' in err: updates['ram'] = {}
        elif 'Кулер' in err: updates['cooler'] = {}
        elif 'GPU' in err: updates['case'] = {}
        elif 'БП' in err: updates['psu'] = {}
    return updates

def node_reasoning(state):
    prompt = f"""Объясни почему сборка оптимальна. 3-4 предложения.
CPU: {state['cpu']['name']} ({state['cpu']['price']}₽), GPU: {state['gpu']['name']} ({state['gpu']['price']}₽), MB: {state['mb']['name']}, RAM: {state['ram']['name']}, SSD: {state['ssd']['name']}, PSU: {state['psu']['name']}, Cooler: {state['cooler']['name']}, Case: {state['case']['name']}.
Бюджет: {state['budget']}₽ | Итого: {state.get('total_price',0)}₽. Задача: {state['purpose']}. Пожелания: {state.get('custom_wishes','нет')}"""
    reasoning = call_llm("Кратко и по-русски.", prompt, model="gpt-4o-mini", max_tokens=300, temperature=0.4, as_json=False)
    return {"final_reasoning": reasoning or "Сборка оптимальна."}

def route_validate(state):
    if state['validated']: return "reasoning"
    if state['retry'] >= 2: return "reasoning"
    return "fix"

def create_agent():
    g = StateGraph(AgentState)
    node_names = {
        "planning": "node_planning", "cpu": "node_cpu", "mb": "node_mb",
        "gpu": "node_gpu", "ram": "node_ram", "ssd": "node_ssd",
        "psu": "node_psu", "cooler": "node_cooler", "case": "node_case",
        "validate": "node_validate", "fix": "node_fix", "reasoning": "node_reasoning",
    }
    for node_name, func_name in node_names.items():
        g.add_node(node_name, globals()[func_name])
    g.set_entry_point("planning")
    g.add_edge("planning", "cpu")
    g.add_edge("cpu", "mb")
    g.add_edge("mb", "gpu")
    g.add_edge("gpu", "ram")
    g.add_edge("ram", "ssd")
    g.add_edge("ssd", "psu")
    g.add_edge("psu", "cooler")
    g.add_edge("cooler", "case")
    g.add_edge("case", "validate")
    g.add_conditional_edges("validate", route_validate, {"reasoning": "reasoning", "fix": "fix"})
    g.add_edge("fix", "cpu")
    g.add_edge("reasoning", END)
    return g.compile()

agent = create_agent()
print("✅ LangGraph агент готов")

# ============================================================
#  🌐 FLASK ROUTES
# ============================================================

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/build', methods=['POST'])
def build():
    try:
        data = request.get_json()
        device = data.get('device','pc')
        if device == 'laptop':
            return jsonify(generate_laptop(int(data.get('budget',100000)), data.get('purpose','gaming'), data.get('custom_wishes','')))
        initial = {
            "budget":int(data.get('budget',100000)), "purpose":data.get('purpose','gaming'),
            "color":data.get('color','black'), "style":data.get('style','minimal'),
            "custom_cpu":data.get('custom_cpu',''), "custom_gpu":data.get('custom_gpu',''),
            "custom_wishes":data.get('custom_wishes',''),
            "cpu":{},"mb":{},"gpu":{},"ram":{},"ssd":{},"psu":{},"cooler":{},"case":{},
            "plan":{},"steps":[],"errors":[],"retry":0,
            "final_reasoning":"","validated":False,"total_price":0,
        }
        final = agent.invoke(initial)
        components = []
        icons = {'cpu':'⚡','mb':'🔌','gpu':'🎮','ram':'🧠','ssd':'💽','psu':'🔋','cooler':'❄️','case':'📦'}
        labels = {'cpu':'Процессор','mb':'Материнская плата','gpu':'Видеокарта','ram':'Оперативная память','ssd':'Накопитель','psu':'Блок питания','cooler':'Охлаждение','case':'Корпус'}
        for key in ['cpu','gpu','mb','ram','ssd','psu','cooler','case']:
            item = final.get(key, {})
            if not item or not item.get('name'): continue
            components.append({
                'key':key,'icon':icons[key],'label':labels[key],
                'name':item['name'],'price':int(item.get('price',0)),
                'price_found':item.get('price_found',False),
            })
        return jsonify({
            'type':'ПК','purpose':final['purpose'],'color':final['color'],'style':final['style'],
            'components':components,'total_price':final.get('total_price',0),
            'budget':final['budget'],'reasoning':final['final_reasoning'],
            'reasoning_steps':final['steps'],'validated':final['validated'],
            'retries':final['retry'],'ai_thought':True,
        })
    except Exception as e:
        print(f"❌ BUILD: {traceback.format_exc()}")
        return jsonify({"error":f"Ошибка: {str(e)}"}), 500

def generate_laptop(budget, purpose, wishes=''):
    prompt = f"""Реальный ноутбук. Бюджет: {budget}₽. Задача: {purpose}. Пожелания: {wishes if wishes else 'нет'}. JSON: {{"name":"полное имя"}}"""
    data = parse_json(call_llm(SYS, prompt))
    if not data: data = {"name":"ASUS ROG Strix G16 RTX 4060"}
    name = data['name']
    search = web_search_price(name)
    price = search['price'] if search['found'] else budget
    return {
        'type':'Ноутбук','purpose':purpose,
        'components':[{'key':'laptop','icon':'💻','label':'Модель','name':name,'price':price,'price_found':search['found']}],
        'total_price':price,'budget':budget,
        'reasoning':f'ИИ подобрал ноутбук для {purpose}.',
        'reasoning_steps':[f'💻 Выбран: {name}'],
        'validated':True,'retries':0,'ai_thought':True,
    }

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        msg = data.get('message','').strip()
        mode = data.get('mode','free')
        subscription = data.get('subscription', 'free')
        history = data.get('history',[])
        context = data.get('context',{})
        if not msg: return jsonify({'response':'Задайте вопрос 😊'})
        if mode == 'manager' and subscription not in ['vip', 'вип']:
            return jsonify({
                'response': '🔒 **ИИ Менеджер** доступен только с подпиской **ВИП**.\n\nОформите подписку ВИП чтобы получить доступ к персональному менеджерю 24/7.',
                'mode': mode, 'locked': True
            })
        theme = context.get('theme','')
        theme_map = {
            'minimal':'Отвечай кратко и чётко.',
            'rgb':'Отвечай с энтузиазмом про RGB. 🌈✨',
            'anime':'Отвечай дружелюбно, в аниме-стиле. 🌸✨💖',
            'glass':'Отвечай элегантно. Про эстетику стекла.',
            'retro':'Отвечай ностальгически. Про классику.'
        }
        theme_inst = theme_map.get(theme, "Отвечай по теме.")
        search = web_search_price(msg) if any(k in msg.lower() for k in ['цена','купить','где','сколько','стоит','топ','обзор']) else {'found':False}
        search_ctx = f"\n\n🔍 НАЙДЕНО В ИНТЕРНЕТЕ: ~{search['price']}₽" if search.get('found') else ""
        hist = "\n".join([f"{'Пользователь' if h['role']=='user' else 'ИИ'}: {h['content'][:200]}" for h in history[-4:]])
        if mode == 'manager':
            sys_prompt = f"""Ты персональный VIP-менеджер сервиса сборки ПК. Помогай с ЛЮБЫМИ вопросами. Отвечай вежливо, профессионально. {theme_inst}{search_ctx}"""
            r = call_llm(sys_prompt, f"ИСТОРИЯ:\n{hist}\n\nВОПРОС: {msg}" if hist else msg, model="gpt-4o", max_tokens=700, temperature=0.5, as_json=False)
        else:
            sys_prompt = f"""Ты эксперт по ПК. Отвечай КОРОТКО (2-4 предложения). {theme_inst}{search_ctx}"""
            r = call_llm(sys_prompt, f"ИСТОРИЯ:\n{hist}\n\nВОПРОС: {msg}" if hist else msg, model="gpt-4o-mini", max_tokens=300, temperature=0.5, as_json=False)
        return jsonify({'response': (r or "Извините, не могу ответить.").strip(), 'mode':mode, 'used_search':search.get('found',False)})
    except Exception as e:
        print(f"❌ CHAT: {traceback.format_exc()}")
        return jsonify({'response': f'Ошибка: {str(e)}'}), 500

@app.route('/api/compare', methods=['POST'])
def compare():
    data = request.get_json()
    sub = data.get('subscription', 'free')
    if sub not in ['плюс','премиум','vip','вип']:
        return jsonify({'error':'Доступно только с подпиской (Плюс и выше)'}), 403
    name = data.get('component','')
    search = web_search_price(name)
    real_prices = search.get('real_prices', {})
    prices = []
    for shop_name, data_shop in real_prices.items():
        prices.append({
            'shop': shop_name, 'price': data_shop['min'],
            'median': data_shop['median'], 'url': data_shop['url'],
            'count': len(data_shop['prices']), 'note': f"Найдено {len(data_shop['prices'])} цен"
        })
    prices.sort(key=lambda x: x['price'])
    base_price = search.get('price', data.get('base_price', 0))
    return jsonify({'prices': prices, 'component': name, 'base_price': int(base_price) if base_price else 0, 'found_online': search['found'], 'shops_count': len(prices)})

@app.route('/api/turnkey', methods=['POST'])
def turnkey():
    try:
        data = request.get_json()
        step = data.get('step', 1)
        answers = data.get('answers', {})
        subscription = data.get('subscription', 'free')
        if subscription not in ['vip', 'вип']:
            return jsonify({"error": True, "message": "🔒 Эта функция доступна только с подпиской **ВИП**.", "action": "subscribe"})
        questions = [
            {"q": "Для чего вам ПК?", "key": "purpose", "options": ["Игры", "Работа", "Код", "Дизайн", "Стриминг"]},
            {"q": "Какой у вас бюджет?", "key": "budget", "options": ["До 80 000₽", "80-150 000₽", "150-250 000₽", "250 000₽+"]},
            {"q": "В какие игры играете?", "key": "usage", "options": ["Cyberpunk, AAA", "CS2, Valorant, Dota 2", "Minecraft, Roblox", "Photoshop, Premiere", "VS Code, Docker"]},
            {"q": "Какой стиль сборки?", "key": "style", "options": ["Минимализм", "RGB", "Аниме", "Белый", "Ретро"]},
        ]
        if step <= len(questions):
            return jsonify({"question": questions[step-1], "step": step, "total": len(questions)})
        sys_prompt = """Ты эксперт по сборке ПК. Сформируй ИДЕАЛЬНУЮ сборку. Ответ должен содержать ТОЛЬКО список компонентов и ИТОГОВУЮ стоимость."""
        user_prompt = f"ОТВЕТЫ КЛИЕНТА:\n{json.dumps(answers, ensure_ascii=False, indent=2)}\n\nПодбери оптимальную сборку. ТОЛЬКО компоненты и итого."
        r = call_llm(sys_prompt, user_prompt, model="gpt-4o", max_tokens=800, temperature=0.4, as_json=False)
        return jsonify({"done": True, "response": r or "Ошибка генерации сборки"})
    except Exception as e:
        return jsonify({"error": True, "message": str(e)}), 500

@app.route('/api/auth', methods=['POST'])
def auth():
    try:
        data = request.get_json()
        action = data.get('action')
        if action == 'send_code':
            email = data.get('email','').strip()
            nickname = data.get('nickname','').strip()
            password = data.get('password','')
            if not email or '@' not in email: return jsonify({'success':False,'error':'Некорректный email'})
            if not nickname: return jsonify({'success':False,'error':'Введите никнейм'})
            if not re.match(r'^[a-zA-Z0-9_]+$', nickname): return jsonify({'success':False,'error':'Никнейм: только английские буквы, цифры и _'})
            if len(nickname) < 3 or len(nickname) > 20: return jsonify({'success':False,'error':'Никнейм: 3-20 символов'})
            if len(password) < 6: return jsonify({'success':False,'error':'Пароль минимум 6 символов'})
            for u in USERS_DB.values():
                if u['nickname'] == nickname: return jsonify({'success':False,'error':'Никнейм уже занят'})
                if u['email'] == email: return jsonify({'success':False,'error':'Email уже зарегистрирован'})
            code = random.randint(100000, 999999)
            VERIFICATION_CODES[email] = {'code': code, 'nickname': nickname, 'password': password}
            subject = "Код подтверждения - Компьютерный AI"
            body = f"""<html><body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2 style="color: #00d4ff;">🖥️ Компьютерный AI</h2>
                <p>Ваш код подтверждения:</p>
                <h1 style="color: #10b981; font-size: 36px; letter-spacing: 5px;">{code}</h1>
                <p>Код действителен 10 минут.</p>
            </body></html>"""
            email_sent = send_email(email, subject, body)
            if email_sent:
                return jsonify({'success':True, 'message': f'Код отправлен на {email}', 'confirm_email': SMTP_EMAIL})
            else:
                return jsonify({'success':True, 'code': code, 'message': f'⚠️ Не удалось отправить email. Код для теста: {code}', 'confirm_email': SMTP_EMAIL})
        if action == 'verify_register':
            email = data.get('email','').strip()
            code = data.get('code','').strip()
            if email not in VERIFICATION_CODES: return jsonify({'success':False,'error':'Сначала отправьте код'})
            if str(VERIFICATION_CODES[email]['code']) != code: return jsonify({'success':False,'error':'Неверный код'})
            user_data = VERIFICATION_CODES[email]
            user = {'email': email, 'nickname': user_data['nickname'], 'password': user_data['password'], 'created': time.time()}
            USERS_DB[email] = user
            del VERIFICATION_CODES[email]
            return jsonify({'success':True, 'user': {'nickname': user['nickname'], 'email': user['email']}})
        if action == 'login':
            login = data.get('login','').strip()
            password = data.get('password','')
            user = None
            for u in USERS_DB.values():
                if u['email'] == login or u['nickname'] == login:
                    user = u
                    break
            if not user: return jsonify({'success':False,'error':'Пользователь не найден'})
            if user['password'] != password: return jsonify({'success':False,'error':'Неверный пароль'})
            return jsonify({'success':True, 'user': {'nickname': user['nickname'], 'email': user['email']}})
        if action == 'change_nickname':
            email = data.get('email','').strip()
            new_nick = data.get('nickname','').strip()
            if not re.match(r'^[a-zA-Z0-9_]+$', new_nick): return jsonify({'success':False,'error':'Только английские буквы, цифры и _'})
            if len(new_nick) < 3 or len(new_nick) > 20: return jsonify({'success':False,'error':'3-20 символов'})
            for u in USERS_DB.values():
                if u['email'] != email and u['nickname'] == new_nick: return jsonify({'success':False,'error':'Никнейм уже занят'})
            if email in USERS_DB:
                USERS_DB[email]['nickname'] = new_nick
                return jsonify({'success':True, 'nickname': new_nick})
            return jsonify({'success':True, 'nickname': new_nick})
        if action == 'send_email_confirmation':
            email = data.get('email','').strip()
            code = random.randint(100000, 999999)
            VERIFICATION_CODES[f"confirm_{email}"] = {'code': code, 'email': email}
            subject = "Подтверждение email - Компьютерный AI"
            body = f"""<html><body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2 style="color: #00d4ff;">🖥️ Подтверждение email</h2>
                <p>Ваш код:</p>
                <h1 style="color: #10b981; font-size: 36px; letter-spacing: 5px;">{code}</h1>
            </body></html>"""
            email_sent = send_email(email, subject, body)
            if email_sent:
                return jsonify({'success':True, 'message': f'Код отправлен на {email}'})
            else:
                return jsonify({'success':True, 'code': code, 'message': f'⚠️ Код для теста: {code}'})
        return jsonify({'success':False,'error':'Неизвестное действие'}), 400
    except Exception as e:
        print(f"❌ AUTH: {traceback.format_exc()}")
        return jsonify({'success':False,'error':str(e)}), 500

if __name__ == '__main__':
    print("\n"+"="*60)
    print("🧠 КОМПЬЮТЕРНЫЙ AI — v7 (финальный)")
    print("⏰ Точный таймер подписки (до секунд)")
    print("📍 Badge в нижнем правом углу")
    print("="*60+"\n")
    app.run(debug=True, port=5000)