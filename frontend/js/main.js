/* 应用控制层：状态管理、事件委托、战斗交互 */
const App = {
  meta: null,
  state: null,
  battle: null,
  selectedClass: 'warrior',
  selectedTarget: null,
  picker: null,
  busy: false,
  stateAt: Date.now(),
  lastLevel: 0,
};

const $ = (sel) => document.querySelector(sel);

/* ---------------- 界面设置 ---------------- */
const THEMES = {
  brass: { name: '黄铜', rgb: '200, 162, 74' },
  mithril: { name: '秘银', rgb: '150, 182, 202' },
  ember: { name: '余烬', rgb: '206, 96, 72' },
  jade: { name: '翠玉', rgb: '110, 190, 152' },
  void: { name: '虚空', rgb: '170, 124, 240' },
  frost: { name: '霜蓝', rgb: '116, 168, 220' },
};

const Settings = {
  data: { theme: 'brass', scan: false, grid: false, motion: true, compact: false },
  load() {
    try {
      const raw = JSON.parse(localStorage.getItem('shiyu-ui') || '{}');
      Object.assign(this.data, raw);
    } catch (e) { /* 忽略损坏的设置 */ }
  },
  save() {
    try { localStorage.setItem('shiyu-ui', JSON.stringify(this.data)); } catch (e) { /* 忽略 */ }
  },
  apply() {
    const theme = THEMES[this.data.theme] || THEMES.brass;
    document.documentElement.style.setProperty('--accent-rgb', theme.rgb);
    document.body.classList.toggle('hud-scan-on', !!this.data.scan);
    document.body.classList.toggle('hud-grid-on', !!this.data.grid);
    document.body.classList.toggle('reduce-fx', !this.data.motion);
    document.body.classList.toggle('compact', !!this.data.compact);
  },
  set(key, value) {
    this.data[key] = value;
    this.save();
    this.apply();
  },
};

/* ---------------- 提示与弹窗 ---------------- */
function toast(message, type = '') {
  const root = $('#toast-root');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  root.appendChild(el);
  setTimeout(() => {
    el.style.transition = 'opacity .3s, transform .3s';
    el.style.opacity = '0';
    el.style.transform = 'translateX(12px)';
    setTimeout(() => el.remove(), 320);
  }, 3200);
}

function openModal(html) {
  $('#modal-root').innerHTML = `
    <div class="modal-mask">
      <div class="modal">${html}</div>
    </div>`;
  const mask = $('#modal-root .modal-mask');
  mask.addEventListener('click', (e) => {
    if (e.target === mask) closeModal();
  });
}

function closeModal() {
  $('#modal-root').innerHTML = '';
}

function confirmModal(title, text, onOk) {
  openModal(`
    <h2>${UI.esc(title)}</h2>
    <p class="m-sub">${UI.esc(text)}</p>
    <div style="display:flex;gap:10px;justify-content:flex-end">
      <button class="btn" data-action="close-modal">取消</button>
      <button class="btn btn-danger" id="confirm-ok">确认</button>
    </div>`);
  $('#confirm-ok').onclick = () => { closeModal(); onOk(); };
}

/* ---------------- 渲染 ---------------- */
function renderStart() {
  $('#start-screen').hidden = false;
  $('#game-screen').hidden = true;
  if (window.FX) FX.setMood('village');
  if (!App.meta) return;
  $('#class-list').innerHTML = UI.classList(App.meta.classes, App.selectedClass);
  $('#start-saves').innerHTML = UI.saveList(App.state ? App.state.saves : [], {
    showEmpty: '还没有存档，选择职业开始第一段旅程。',
    actions: false,
  });
  // 开始界面存档卡片改为读取按钮
  $('#start-saves').querySelectorAll('.save-card').forEach((card) => {
    const slot = card.dataset.slot;
    if (!slot) return;
    const row = document.createElement('div');
    row.className = 'sc-actions';
    const btn = document.createElement('button');
    btn.className = 'btn btn-sm btn-primary';
    btn.textContent = '继续这段旅程';
    btn.onclick = () => loadGame(slot);
    row.appendChild(btn);
    card.appendChild(row);
  });
}

function renderTop() {
  const st = App.state;
  const c = st.character;
  $('#top-area').textContent = `${st.area.emoji} ${st.area.name}`;
  $('#top-level').textContent = `Lv.${c.level} ${c.class_name}`;
  $('#top-gold').textContent = c.gold;
  $('#top-time').textContent = UI.fmtTime(st.playtime + (Date.now() - App.stateAt) / 1000);
}

function renderSide() {
  const st = App.state;
  $('#tab-bag').innerHTML = UI.bag(st.character);
  $('#tab-skills').innerHTML = UI.skillList(st.skills);
  $('#tab-saves').innerHTML = `
    <div class="empty-tip" style="padding:0 0 10px;text-align:left">
      自动存档在每次行动后写入；手动存档可保留关键节点。
    </div>
    ${UI.saveList(st.saves)}`;
}

function renderMap() {
  const st = App.state;
  const idx = st.world.areas.findIndex((a) => a.id === st.area.id);
  $('#area-detail').innerHTML = UI.areaDetail(st.area, st.character, idx);
  $('#map-grid').innerHTML = UI.mapGrid(st.world);
  const sub = document.querySelector('#map-view .section-sub');
  if (sub) sub.textContent = `已肃清 ${st.world.bosses.length} 处，共 ${st.world.areas.length} 域`;
}

function renderBattle() {
  const st = App.state;
  const root = $('#battle-root');
  if (!App.battle) {
    $('#battle-view').hidden = true;
    $('#map-view').hidden = false;
    root.innerHTML = '';
    return;
  }
  $('#map-view').hidden = true;
  $('#battle-view').hidden = false;
  const char = { ...st.character, skill_view: st.skills };
  if (App.battle.status !== 'active') {
    root.innerHTML = UI.resultCard(App.battle);
    return;
  }
  if (App.selectedTarget == null) {
    const alive = App.battle.enemies.find((e) => e.alive);
    App.selectedTarget = alive ? alive.index : null;
  }
  root.innerHTML = UI.battleView(App.battle, char, App.picker, App.selectedTarget);
  const log = $('#battle-log');
  if (log) log.scrollTop = log.scrollHeight;
}

function renderAll() {
  if (!App.state || !App.state.active) {
    renderStart();
    return;
  }
  if (window.FX && App.state.area) FX.setMood(App.state.area.id);
  $('#start-screen').hidden = true;
  $('#game-screen').hidden = false;
  renderTop();
  $('#char-panel').innerHTML = UI.characterPanel(App.state.character, App.meta);
  renderMap();
  renderSide();
  renderBattle();
}

function enterGame(kind) {
  App.battle = App.state.battle || null;
  App.selectedTarget = null;
  App.picker = null;
  App.lastLevel = App.state.character ? App.state.character.level : 1;
  if (window.FX && FX.scene) FX.scene(kind || null, renderAll);
  else renderAll();
}

/* ---------------- 战斗反馈动画 ---------------- */
function floatText(container, text, kind) {
  if (!container) return;
  const el = document.createElement('div');
  el.className = `float-dmg ${kind || ''}`;
  el.textContent = text;
  container.appendChild(el);
  setTimeout(() => el.remove(), 900);
}

function animateEvents(events) {
  (events || []).forEach((entry, i) => {
    if (!entry.dmg && !entry.heal && !entry.miss && !entry.dodge) return;
    setTimeout(() => {
      let target;
      if (entry.target != null) {
        target = document.querySelector(`.enemy-card[data-enemy="${entry.target}"]`);
        if (target) {
          target.classList.add('hit');
          setTimeout(() => target.classList.remove('hit'), 320);
        }
      } else {
        target = document.querySelector('[data-player]');
      }
      if (entry.miss || entry.dodge) {
        floatText(target, '闪避', 'miss');
      } else if (entry.heal) {
        floatText(target, `+${entry.heal}`, 'heal');
      } else if (entry.dmg) {
        floatText(target, `-${entry.dmg}`, entry.crit ? 'crit' : '');
      }
    }, i * 110);
  });
}

/* ---------------- 数据操作 ---------------- */
async function withBusy(fn) {
  if (App.busy) return;
  App.busy = true;
  try {
    await fn();
  } catch (err) {
    if (err.state && err.state.active) {
      App.state = err.state;
      renderAll();
    }
    toast(err.message || '操作失败', 'error');
  } finally {
    App.busy = false;
  }
}

async function act(action, payload = {}) {
  return withBusy(async () => {
    const hadBattle = !!App.battle;
    const res = await API.post('/api/action', { action, ...payload });
    if (res.state) {
      App.state = res.state;
      App.stateAt = Date.now();
    }
    if (res.battle) App.battle = res.battle;
    (res.events || []).forEach((e) => {
      if (e.type === 'system') toast(e.text);
    });
    if (action === 'explore' && res.event) {
      if (res.event.kind === 'gold') toast(`拾获 ${res.event.amount} 金币`, 'gold');
      if (res.event.kind === 'item') toast(`拾获【${res.event.name}】`, 'success');
    }
    if (action === 'travel') App.battle = null;

    let kind = 'soft';
    if (action === 'travel') kind = 'travel';
    if (res.battle && !hadBattle) kind = 'encounter';

    if (window.FX && FX.scene) await FX.scene(kind, renderAll);
    else renderAll();
    if (window.FX && kind === 'encounter') FX.impact();
  });
}

async function battleAct(payload) {
  return withBusy(async () => {
    const res = await API.post('/api/battle', payload);
    const prevLevel = App.state.character ? App.state.character.level : 1;
    App.battle = res.battle;
    App.state = res.state;
    App.stateAt = Date.now();
    App.picker = null;

    const status = res.battle ? res.battle.status : 'active';
    const kind = status === 'won' ? 'victory'
      : status === 'lost' ? 'defeat'
        : status === 'fled' ? 'soft' : null;
    if (window.FX && FX.scene) await FX.scene(kind, renderAll);
    else renderAll();

    if (window.FX && kind === 'victory') {
      FX.impact();
      FX.burst(window.innerWidth / 2, window.innerHeight * 0.32);
    }

    animateEvents(res.events);
    if (window.FX) FX.playBattle(res.events, payload.action);
    if (res.state.character && res.state.character.level > prevLevel) {
      setTimeout(() => {
        toast(`升级！当前 Lv.${res.state.character.level}，获得 3 点属性点`, 'gold');
        if (window.FX) FX.levelUp();
      }, 400);
    }
    if (res.unlocked_areas && res.unlocked_areas.length) {
      setTimeout(() => toast('新区域解锁：' + res.unlocked_areas.map((a) => a.name).join('、'), 'success'), 600);
    }
  });
}

async function loadGame(slot) {
  return withBusy(async () => {
    const state = await API.post('/api/load', { slot });
    App.state = state;
    App.stateAt = Date.now();
    enterGame('dive');
    toast('读取存档成功', 'success');
  });
}

/* ---------------- 弹窗内容 ---------------- */
function openShop() {
  const st = App.state;
  const char = st.character;
  const rows = st.shop
    .filter((item) => item.type === 'consumable' || !item.classes || item.classes.includes(char.class_id))
    .map((item) => `
      <div class="shop-row">
        <span class="sr-emoji">${item.emoji}</span>
        <div class="sr-main">
          <div class="sr-name">${UI.esc(item.name)}</div>
          <div class="sr-desc">${UI.esc(item.desc)}</div>
        </div>
        <span class="sr-price">◈ ${item.price}</span>
        <button class="btn btn-sm" data-action="buy" data-item="${item.item_id}"
          ${char.gold < item.price ? 'disabled' : ''}>购买</button>
      </div>`).join('');
  openModal(`
    <h2>晨曦村铁匠铺</h2>
    <p class="m-sub">当前金币 <b style="color:var(--gold-bright)">◈ ${char.gold}</b> · 一阶装备与补给</p>
    ${rows}
    <div style="text-align:right;margin-top:14px">
      <button class="btn" data-action="close-modal">离开</button>
    </div>`);
}

function openSaveDialog() {
  const st = App.state;
  const slots = ['slot1', 'slot2', 'slot3'].map((slot, i) => {
    const info = st.saves.find((s) => s.slot === slot);
    return `
      <div class="shop-row">
        <span class="sr-emoji">${i + 1}</span>
        <div class="sr-main">
          <div class="sr-name">${slot.replace('slot', '槽位 ')}</div>
          <div class="sr-desc">${info ? `${UI.esc(info.name)} Lv.${info.level} · ${UI.esc(info.area_name)} · ${UI.fmtTime(info.playtime)}` : '空槽位'}</div>
        </div>
        <button class="btn btn-sm ${info ? '' : 'btn-primary'}" data-action="save" data-slot="${slot}">保存</button>
        ${info ? `<button class="btn btn-sm btn-primary" data-action="load" data-slot="${slot}">读取</button>` : ''}
      </div>`;
  }).join('');
  openModal(`
    <h2>保存进度</h2>
    <p class="m-sub">战斗中途也可以保存，读档后会回到当前回合。</p>
    ${slots}
    <div style="text-align:right;margin-top:14px">
      <button class="btn" data-action="close-modal">关闭</button>
    </div>`);
}

function openSettings() {
  const d = Settings.data;
  openModal(`
    <h2>界面设置</h2>
    <p class="m-sub">换一套配色，或调整界面密度与动效。设置保存在本机。</p>
    <div class="set-group">
      <div class="set-label">主题色</div>
      <div class="theme-grid">
        ${Object.entries(THEMES).map(([id, t]) => `
          <button class="theme-dot ${d.theme === id ? 'active' : ''}" data-action="set-theme" data-theme="${id}">
            <i style="background: rgb(${t.rgb}); color: rgb(${t.rgb})"></i>
            <span>${t.name}</span>
          </button>`).join('')}
      </div>
    </div>
    <div class="set-group">
      <div class="set-label">显示</div>
      <div class="set-row"><span>扫描线</span>
        <button class="switch ${d.scan ? 'on' : ''}" data-action="toggle-setting" data-key="scan" aria-label="扫描线"><i></i></button></div>
      <div class="set-row"><span>背景网格</span>
        <button class="switch ${d.grid ? 'on' : ''}" data-action="toggle-setting" data-key="grid" aria-label="背景网格"><i></i></button></div>
      <div class="set-row"><span>界面动效</span>
        <button class="switch ${d.motion ? 'on' : ''}" data-action="toggle-setting" data-key="motion" aria-label="界面动效"><i></i></button></div>
      <div class="set-row"><span>紧凑布局</span>
        <button class="switch ${d.compact ? 'on' : ''}" data-action="toggle-setting" data-key="compact" aria-label="紧凑布局"><i></i></button></div>
    </div>
    <div style="text-align:right;margin-top:18px">
      <button class="btn" data-action="close-modal">完成</button>
    </div>`);
}

/* ---------------- 事件委托 ---------------- */
function bindEvents() {
  document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-action]');
    if (!el) return;
    const action = el.dataset.action;

    if (action === 'close-modal') {
      closeModal();
      return;
    }

    switch (action) {
      case 'select-class':
        App.selectedClass = el.dataset.id;
        document.querySelectorAll('.class-card').forEach((c) => c.classList.remove('selected'));
        el.classList.add('selected');
        break;

      case 'new-game': {
        const name = ($('#hero-name').value || '').trim();
        withBusy(async () => {
          const state = await API.post('/api/new', { name, class_id: App.selectedClass });
          App.state = state;
          App.stateAt = Date.now();
          enterGame('dive');
          const cls = (App.meta.classes || []).find((c) => c.id === App.selectedClass);
          if (window.FX) {
            setTimeout(() => {
              FX.chapter(state.area.name, `${state.character.name} · ${cls ? cls.name : state.character.class_name}`);
            }, 680);
          }
          toast('旅程开始。先去迷雾森林试试身手吧。', 'success');
        });
        break;
      }

      case 'replay-intro':
        if (window.FX) FX.cinematic(true);
        break;

      case 'set-theme':
        Settings.set('theme', el.dataset.theme);
        openSettings();
        break;

      case 'toggle-setting':
        Settings.set(el.dataset.key, !Settings.data[el.dataset.key]);
        openSettings();
        break;

      case 'load':
        closeModal();
        loadGame(el.dataset.slot);
        break;

      case 'save':
        withBusy(async () => {
          const res = await API.post('/api/save', { slot: el.dataset.slot });
          App.state = res.state;
          App.stateAt = Date.now();
          renderAll();
          closeModal();
          toast('进度已保存', 'success');
        });
        break;

      case 'delete-save': {
        const slot = el.dataset.slot;
        confirmModal('删除存档', `确定要删除 ${slot.replace('slot', '槽位 ')} 吗？此操作不可撤销。`, () => {
          withBusy(async () => {
            const state = await API.post('/api/delete-save', { slot });
            App.state = state;
            renderAll();
            toast('存档已删除');
          });
        });
        break;
      }

      case 'tab':
        document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t === el));
        ['bag', 'skills', 'saves'].forEach((key) => {
          $(`#tab-${key}`).hidden = key !== el.dataset.tab;
        });
        break;

      case 'travel':
        act('travel', { area_id: el.dataset.area });
        break;

      case 'locked-area':
        toast('该区域尚未解锁，先击败当前区域的守关者。', 'error');
        break;

      case 'explore':
        act('explore');
        break;

      case 'challenge-boss':
        confirmModal('挑战守关者', 'Boss 战无法逃跑，确认现在开战？', () => act('challenge_boss'));
        break;

      case 'rest':
        act('rest');
        break;

      case 'shop':
        openShop();
        break;

      case 'buy':
        withBusy(async () => {
          const res = await API.post('/api/action', { action: 'buy', item_id: el.dataset.item });
          App.state = res.state;
          App.stateAt = Date.now();
          renderAll();
          openShop();
          toast((res.events[0] || {}).text || '购买成功', 'success');
        });
        break;

      case 'equip':
      case 'unequip':
        act(action, { uid: el.dataset.uid, slot: el.dataset.slot });
        break;

      case 'sell':
        confirmModal('出售物品', '出售价格约为原价的 45%，确认出售？', () => act('sell', { uid: el.dataset.uid }));
        break;

      case 'use-item':
        act('use_item', { item_id: el.dataset.item });
        break;

      case 'alloc':
        act('allocate', { stat: el.dataset.stat });
        break;

      case 'target':
        App.selectedTarget = Number(el.dataset.index);
        renderBattle();
        break;

      case 'battle-attack':
        battleAct({ action: 'attack', target: App.selectedTarget });
        break;

      case 'battle-skill':
        App.picker = App.picker === 'skill' ? null : 'skill';
        renderBattle();
        break;

      case 'battle-item':
        App.picker = App.picker === 'item' ? null : 'item';
        renderBattle();
        break;

      case 'close-picker':
        App.picker = null;
        renderBattle();
        break;

      case 'pick-skill':
        battleAct({ action: 'skill', skill_id: el.dataset.id, target: App.selectedTarget });
        break;

      case 'pick-item':
        battleAct({ action: 'item', item_id: el.dataset.id });
        break;

      case 'battle-defend':
        battleAct({ action: 'defend' });
        break;

      case 'battle-dodge':
        battleAct({ action: 'dodge' });
        break;

      case 'battle-flee':
        battleAct({ action: 'flee' });
        break;

      case 'battle-continue':
        App.battle = null;
        App.picker = null;
        App.selectedTarget = null;
        if (window.FX && FX.scene) FX.scene('soft', renderAll);
        else renderAll();
        break;

      default:
        break;
    }
  });

  $('#btn-save').addEventListener('click', openSaveDialog);
  $('#btn-settings').addEventListener('click', openSettings);

  $('#btn-home').addEventListener('click', () => {
    confirmModal('返回主菜单', '当前进度会自动保存，确定返回标题界面吗？', () => {
      withBusy(async () => {
        const state = await API.post('/api/leave', {});
        App.state = state;
        App.battle = null;
        App.picker = null;
        if (window.FX && FX.scene) FX.scene('soft', renderStart);
        else renderStart();
      });
    });
  });

  $('#hero-name').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') document.querySelector('[data-action="new-game"]').click();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if ($('#modal-root').innerHTML) closeModal();
      else if (App.picker) { App.picker = null; renderBattle(); }
      return;
    }
    if (!App.battle || App.battle.status !== 'active' || App.busy) return;
    if (e.target.tagName === 'INPUT') return;
    const map = {
      1: () => battleAct({ action: 'attack', target: App.selectedTarget }),
      2: () => { App.picker = App.picker === 'skill' ? null : 'skill'; renderBattle(); },
      3: () => battleAct({ action: 'defend' }),
      4: () => battleAct({ action: 'dodge' }),
      5: () => { App.picker = App.picker === 'item' ? null : 'item'; renderBattle(); },
    };
    if (map[e.key]) {
      e.preventDefault();
      map[e.key]();
    }
  });
}

/* ---------------- 启动 ---------------- */
async function init() {
  Settings.load();
  Settings.apply();
  if (window.FX) FX.init();
  bindEvents();
  setInterval(() => {
    if (App.state && App.state.active) {
      $('#top-time').textContent = UI.fmtTime(App.state.playtime + (Date.now() - App.stateAt) / 1000);
    }
  }, 1000);

  const cine = window.FX ? FX.cinematic() : Promise.resolve();

  try {
    App.meta = await API.get('/api/meta');
    App.state = await API.get('/api/state');
    if (App.state.active) {
      enterGame();
    } else {
      renderStart();
    }
  } catch (err) {
    toast('无法连接本地服务：' + err.message, 'error');
  }

  await cine;
  if (window.FX) FX.enterScreen();
}

init();
