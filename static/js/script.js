const state = {
  device:'pc', purpose:'gaming', color:'black', style:'minimal',
  budget:100000, custom_cpu:'', custom_gpu:'',
  buildsUsed: parseInt(localStorage.getItem('buildsUsed') || '0'),
  subscription: localStorage.getItem('sub') || 'vip',
  subPlan: localStorage.getItem('subPlan') || 'ВИП Тест',
  chatMode: 'free',
  chatHistory: []
};

let chatContext = { purpose: '', theme: '', color: '' };

function showScreen(id){
  document.querySelectorAll('.screen').forEach(s=>s.classList.remove('active'));
  const screen = document.getElementById('screen-'+id);
  if(screen) screen.classList.add('active');
  window.scrollTo({top:0,behavior:'smooth'});
  updateBuildsCounter();
  updateSubBadge();
}

function updateSubBadge(){
  const badge = document.getElementById('subBadge');
  if(!badge) return;
  const sub = state.subscription;
  const icons = {'vip':'💎','премиум':'👑','плюс':'⭐','free':'🆓'};
  const names = {'vip':'VIP','премиум':'Премиум','плюс':'Плюс','free':'Free'};
  badge.querySelector('.badge-icon').textContent = icons[sub] || '🆓';
  badge.querySelector('.badge-text').textContent = names[sub] || 'Free';
  badge.className = 'sub-badge sub-' + sub;
}

function selOpt(btn){
  const g = btn.dataset.g;
  document.querySelectorAll(`.opt[data-g="${g}"]`).forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  state[g] = btn.dataset.v;
}

function updBudget(v){
  state.budget = parseInt(v);
  document.getElementById('bVal').textContent = Number(v).toLocaleString('ru-RU') + ' ₽';
}

function fmtP(n){ return Number(n).toLocaleString('ru-RU') + ' ₽'; }

function updateBuildsCounter(){
  const el = document.getElementById('buildsLeft');
  const hint = document.getElementById('subHint');
  if(!el) return;
  if(state.subscription !== 'free'){
    el.textContent = '∞';
    if(hint) hint.textContent = '(безлимит)';
  } else {
    el.textContent = Math.max(0, 3 - state.buildsUsed);
    if(hint) hint.textContent = '(без подписки)';
  }
}

async function doBuild(){
  if(state.subscription === 'free' && state.buildsUsed >= 3){
    showModal('<h3>⚠️ Лимит сборок</h3><p>Оформите подписку</p><button class="btn-modal" onclick="document.getElementById(\'modal\').style.display=\'none\';showScreen(\'sub\')">Оформить</button>');
    return;
  }

  state.custom_cpu = document.getElementById('cCpu')?.value.trim() || '';
  state.custom_gpu = document.getElementById('cGpu')?.value.trim() || '';

  const loader = document.getElementById('loader');
  loader.classList.add('active');

  try {
    const res = await fetch('/api/build',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(state)});
    const data = await res.json();
    setTimeout(()=>{
      loader.classList.remove('active');
      renderBuild(data);
      if(state.subscription === 'free'){
        state.buildsUsed++;
        localStorage.setItem('buildsUsed', state.buildsUsed);
        updateBuildsCounter();
      }
    }, 1000);
  } catch(e){
    loader.classList.remove('active');
    alert('Ошибка: '+e.message);
  }
}

function renderBuild(d){
  const box = document.getElementById('resBox');
  if(!box) return;
  
  let h = `<div class="res-head"><h2>🎉 ${d.type === 'ПК' ? 'Ваша сборка' : 'Рекомендация'}</h2></div>`;
  
  if(d.reasoning){
    h += `<div class="ai-thinking"><b>💡 Почему эта сборка:</b><br>${esc(d.reasoning)}</div>`;
  }

  const hasSub = state.subscription !== 'free';

  h += '<div class="comp-list">';
  d.components.forEach(c=>{
    let shops = '';
    for(const [s,u] of Object.entries(c.shops)){
      shops += `<a href="${u}" target="_blank" class="shop-lnk">${s}</a>`;
    }
    const compareBtn = hasSub 
      ? `<button class="btn-compare" onclick="comparePrices('${esc(c.name).replace(/'/g,"\\'")}',${c.price})">💹 Сравнить цены</button>`
      : `<button class="btn-compare locked" onclick="needSub('Сравнение цен')">🔒 Сравнить</button>`;
    
    h += `<div class="comp-it">
      <div class="comp-ico">${c.icon}</div>
      <div class="comp-info">
        <div class="comp-lbl">${c.label}</div>
        <div class="comp-nm">${esc(c.name)}</div>
        <div class="comp-shops">🛒 ${shops}${compareBtn}</div>
      </div>
      <div class="comp-pr">${c.price>0?fmtP(c.price):'—'}</div>
    </div>`;
  });
  h += '</div>';

  h += `<div class="total-box"><div class="tot-lbl">Итого</div><div class="tot-pr">${fmtP(d.total_price)}</div></div>`;
  h += `<button class="btn-again" onclick="doBuild()">🔄 Другая сборка</button>`;
  
  box.innerHTML = h;
  box.style.display = 'block';
  box.scrollIntoView({behavior:'smooth'});
}

async function comparePrices(name, basePrice){
  const m = document.getElementById('modal');
  document.getElementById('modalBody').innerHTML = '<div class="spinner" style="margin:20px auto;"></div><p>🔍 Ищем цены в интернете...</p>';
  m.style.display = 'flex';
  try{
    const r = await fetch('/api/compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({component:name,base_price:basePrice,subscription:state.subscription})});
    const d = await r.json();
    if(d.error){
      document.getElementById('modalBody').innerHTML = `<h3>🔒 ${d.error}</h3><button class="btn-modal" onclick="document.getElementById('modal').style.display='none';showScreen('sub')">Оформить</button>`;
      return;
    }
    let rows = `<div class="price-row base"><span class="shop">Базовая цена</span><span class="pr">${fmtP(basePrice)}</span></div>`;
    if(d.prices && d.prices.length){
      d.prices.forEach(p => {
        rows += `<div class="price-row">
          <div>
            <span class="shop">${esc(p.shop)}</span>
            ${p.url?`<a href="${p.url}" target="_blank" class="shop-lnk">→ Открыть</a>`:''}
            <span class="note">${esc(p.price)}</span>
          </div>
        </div>`;
      });
    }
    document.getElementById('modalBody').innerHTML = `
      <h3>💹 ${esc(name)}</h3>
      <p>Цены из интернета:</p>
      <div class="prices-list">${rows}</div>
      <button class="btn-modal" onclick="document.getElementById('modal').style.display='none'">OK</button>`;
  }catch(e){ document.getElementById('modalBody').innerHTML = '<p>Ошибка</p>'; }
}

function buySub(plan, period, price){
  const key = plan.toLowerCase();
  state.subscription = key;
  state.subPlan = plan+' '+period;
  localStorage.setItem('sub', key);
  localStorage.setItem('subPlan', state.subPlan);
  localStorage.setItem('buildsUsed','0');
  state.buildsUsed = 0;
  showModal(`<h3>🎉 Подписка активна!</h3><p><b>${plan} ${period}</b></p><div class="modal-pr">${fmtP(price)}</div><p>Перейдите в <b>🎁 Функции подписки</b></p><button class="btn-modal" onclick="document.getElementById('modal').style.display='none';showScreen('features')">К функциям</button>`);
  updateBuildsCounter();
  updateSubBadge();
}

function useFeature(label){
  showModal(`<h3>✅ ${label}</h3><p>Функция активирована!</p><button class="btn-modal" onclick="document.getElementById('modal').style.display='none'">OK</button>`);
}

function needSub(feature){
  showModal(`<h3>🔒 Нужна подписка</h3><p><b>${feature}</b> доступно только с подпиской.</p><button class="btn-modal" onclick="document.getElementById('modal').style.display='none';showScreen('sub')">Оформить</button>`);
}

// ========== ЧАТ ==========
function openChat(){
  document.getElementById('chatFull').classList.add('open');
  setMode('free');
}

function openChatPro(){
  document.getElementById('chatFull').classList.add('open');
  setMode('pro');
}

function openChatManager(){
  document.getElementById('chatFull').classList.add('open');
  setMode('manager');
}

function closeChat(){
  document.getElementById('chatFull').classList.remove('open');
}

function setMode(m){
  state.chatMode = m;
  document.getElementById('mFree').classList.toggle('active', m==='free');
  document.getElementById('mPro').classList.toggle('active', m==='pro');
  document.getElementById('mManager').classList.toggle('active', m==='manager');
  document.getElementById('mSupport').classList.toggle('active', m==='support');
}

function updateContext(){
  chatContext.purpose = document.getElementById('ctxPurpose')?.value || '';
  chatContext.theme = document.getElementById('ctxTheme')?.value || '';
  chatContext.color = document.getElementById('ctxColor')?.value || '';
  
  const chatFull = document.getElementById('chatFull');
  if(chatFull){
    // Убираем все старые темы и цвета
    chatFull.classList.remove('theme-minimal', 'theme-rgb', 'theme-anime', 'theme-glass', 'theme-retro');
    chatFull.classList.remove('color-black', 'color-white', 'color-pink', 'color-rgb');
    
    // Применяем новую тему
    if(chatContext.theme) {
      chatFull.classList.add('theme-' + chatContext.theme);
    }
    if(chatContext.color) {
      chatFull.classList.add('color-' + chatContext.color);
    }
  }
}
  
  // Применяем тему к чату
  const chatFull = document.getElementById('chatFull');
  if(chatFull){
    chatFull.classList.remove('theme-minimal', 'theme-rgb', 'theme-anime', 'theme-glass', 'theme-retro');
    chatFull.classList.remove('color-black', 'color-white', 'color-pink', 'color-rgb');
    
    if(chatContext.theme) chatFull.classList.add('theme-' + chatContext.theme);
    if(chatContext.color) chatFull.classList.add('color-' + chatContext.color);
  }
}

async function sendMsg(){
  const inp = document.getElementById('chatInp');
  const msg = inp.value.trim();
  if(!msg) return;
  inp.value = '';
  const msgs = document.getElementById('chatMsgs');
  msgs.innerHTML += `<div class="msg user">${esc(msg)}</div>`;
  
  const modeLabels = {'free':'Думаю','pro':'👑 Глубокий анализ','manager':'Менеджер','support':'Поддержка'};
  msgs.innerHTML += `<div class="msg bot" id="typing">⏳ ${modeLabels[state.chatMode] || 'Думаю'}...</div>`;
  msgs.scrollTop = msgs.scrollHeight;
  state.chatHistory.push({role:'user',content:msg});
  
  try{
    const r = await fetch('/api/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:msg,mode:state.chatMode,history:state.chatHistory,context:chatContext})
    });
    const d = await r.json();
    const t = document.getElementById('typing');
    if(t){
      t.removeAttribute('id');
      let badges = '';
      if(d.used_search) badges += '<span class="search-badge">🔍 Веб-поиск</span>';
      if(d.in_dev) badges += '<span class="dev-badge">🚧 В разработке</span>';
      if(d.mode === 'pro') badges += '<span class="pro-badge">👑 PRO</span>';
      t.innerHTML = formatMsg(d.response) + badges;
    }
    state.chatHistory.push({role:'assistant',content:d.response});
  }catch(e){
    const t = document.getElementById('typing');
    if(t){t.removeAttribute('id');t.textContent='❌ Ошибка';}
  }
  msgs.scrollTop = msgs.scrollHeight;
}

function esc(s){ const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
function formatMsg(t){ return esc(t).replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br>'); }
function showModal(h){ document.getElementById('modalBody').innerHTML=h; document.getElementById('modal').style.display='flex'; }

updateBuildsCounter();
updateSubBadge();