/* 渲染层：把后端状态转成 DOM 片段，保持无框架、可预测 */
const UI = (() => {
  const esc = (value) => String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

  const pct = (value, max) => {
    if (!max) return 0;
    return Math.max(0, Math.min(100, (value / max) * 100));
  };

  const fmtTime = (seconds) => {
    const total = Math.max(0, Math.floor(seconds || 0));
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    const mm = String(m).padStart(2, '0');
    const ss = String(s).padStart(2, '0');
    return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
  };

  const STAT_LABEL = {
    atk: '攻击', def: '防御', hp: '生命', mp: '法力',
    agi: '敏捷', crit: '暴击', dodge: '闪避',
  };

  const statText = (stats) => Object.entries(stats || {})
    .map(([key, value]) => `${STAT_LABEL[key] || key}+${value}`)
    .join(' · ');

  const rarityColor = (item) => (item && item.color) || '#9aa4b2';

  /* ---------- 开始界面 ---------- */
  function classList(classes, selected) {
    return classes.map((c) => `
      <button class="class-card ${c.id === selected ? 'selected' : ''}" data-action="select-class" data-id="${c.id}">
        <span class="cc-check">◆</span>
        <div class="cc-top">
          <span class="cc-emoji">${c.emoji}</span>
          <div>
            <div class="cc-name">${esc(c.name)}</div>
            <div class="cc-title">${esc(c.title)}</div>
          </div>
        </div>
        <p class="cc-desc">${esc(c.desc)}</p>
        <div class="cc-tags">
          <span class="tag diff">${esc(c.difficulty)}</span>
          <span class="tag">生命 ${c.base.hp}</span>
          <span class="tag">攻击 ${c.base.atk}</span>
          <span class="tag">敏捷 ${c.base.agi}</span>
        </div>
      </button>`).join('');
  }

  function saveList(saves, options = {}) {
    const { showEmpty = '暂无存档', actions = true } = options;
    if (!saves || !saves.length) {
      return `<div class="empty-tip">${esc(showEmpty)}</div>`;
    }
    return saves.map((s) => `
      <div class="save-card ${s.slot === 'auto' ? 'auto' : ''}" data-slot="${s.slot}">
        <div class="sc-top">
          <span class="sc-slot">${s.slot === 'auto' ? '自动存档' : s.slot.replace('slot', '槽位 ')}</span>
          <span class="sc-main">${esc(s.name)} · Lv.${s.level}</span>
          ${s.in_battle ? '<span class="chip debuff">战斗中</span>' : ''}
        </div>
        <div class="sc-meta">
          ${esc(s.class_emoji || '')} ${esc(s.class_name)} · ${esc(s.area_name)}<br />
          ${esc((s.saved_at || '').replace('T', ' '))} · ${fmtTime(s.playtime)}
        </div>
        ${actions ? `<div class="sc-actions">
          ${s.slot === 'auto' ? '' : `<button class="btn btn-sm" data-action="save" data-slot="${s.slot}">覆盖保存</button>`}
          <button class="btn btn-sm btn-primary" data-action="load" data-slot="${s.slot}">读取</button>
          ${s.slot === 'auto' ? '' : `<button class="btn btn-sm btn-danger" data-action="delete-save" data-slot="${s.slot}">删除</button>`}
        </div>` : ''}
      </div>`).join('');
  }

  /* ---------- 角色面板 ---------- */
  function characterPanel(char) {
    const s = char.stats;
    const expPct = pct(char.exp, char.exp_need);
    const alloc = char.points > 0 ? `
      <div class="alloc-box">
        <div class="alloc-head"><span>可分配属性点</span><b>${char.points}</b></div>
        <div class="alloc-grid">
          ${['hp', 'mp', 'atk', 'def', 'agi'].map((key) => `
            <button class="alloc-btn" data-action="alloc" data-stat="${key}">
              ${STAT_LABEL[key]}<span>+</span>
            </button>`).join('')}
        </div>
      </div>` : '';

    const equip = ['weapon', 'armor', 'accessory'].map((slot) => {
      const item = char.equipment[slot];
      const label = { weapon: '武器', armor: '护甲', accessory: '饰品' }[slot];
      if (!item) {
        return `<div class="equip-slot empty">
          <span class="es-emoji">·</span>
          <div class="es-main"><div class="es-name">${label}</div><div class="es-label">未装备</div></div>
        </div>`;
      }
      return `<div class="equip-slot filled" data-action="unequip" data-slot="${slot}" title="点击卸下">
        <span class="es-emoji">${item.emoji}</span>
        <div class="es-main">
          <div class="es-name" style="color:${rarityColor(item)}">${esc(item.name)}</div>
          <div class="es-stat">${esc(statText(item.stats))}</div>
        </div>
      </div>`;
    }).join('');

    return `
      <div class="char-head">
        <div class="avatar">${char.class_emoji}</div>
        <div class="char-id">
          <div class="char-name">${esc(char.name)}</div>
          <div class="char-sub">${esc(char.class_name)} · <b>Lv.${char.level}</b></div>
        </div>
      </div>
      <div class="level-row"><span>经验</span><span><b>${char.exp}</b> / ${char.exp_need}</span></div>
      <div class="bar exp thin"><i style="width:${expPct}%"></i></div>

      <div class="vital hp">
        <div class="vital-head"><span>生命</span><span>${char.hp} / ${s.max_hp}</span></div>
        <div class="bar hp"><i style="width:${pct(char.hp, s.max_hp)}%"></i></div>
      </div>
      <div class="vital mp">
        <div class="vital-head"><span>法力</span><span>${char.mp} / ${s.max_mp}</span></div>
        <div class="bar mp"><i style="width:${pct(char.mp, s.max_mp)}%"></i></div>
      </div>

      <div class="stat-grid">
        <div class="stat-cell"><span>攻击</span><b>${s.atk}</b></div>
        <div class="stat-cell"><span>防御</span><b>${s.def}</b></div>
        <div class="stat-cell"><span>敏捷</span><b>${s.agi}</b></div>
        <div class="stat-cell"><span>暴击</span><b>${s.crit}%</b></div>
        <div class="stat-cell"><span>闪避</span><b>${s.dodge}%</b></div>
        <div class="stat-cell"><span>击杀</span><b>${char.kills}</b></div>
      </div>

      ${alloc}
      <div class="equip-title">装备</div>
      <div class="equip-list">${equip}</div>
    `;
  }

  /* ---------- 地图 ---------- */
  function areaDetail(area, char) {
    const boss = area.boss;
    const bossChip = area.cleared
      ? `<span class="boss-chip cleared">✓ 守关者已击败</span>`
      : boss
        ? `<span class="boss-chip">☠ ${esc(boss.name)} · Lv.${boss.level}</span>`
        : '';
    const actions = area.safe
      ? `<button class="btn btn-primary" data-action="rest">在村中休整</button>
         <button class="btn" data-action="shop">铁匠铺 · 商店</button>`
      : `<button class="btn btn-primary" data-action="explore">探索区域</button>
         ${boss && !area.cleared ? `<button class="btn btn-danger" data-action="challenge-boss">挑战 Boss</button>` : ''}`;
    return `
      <div class="ad-head">
        <div class="ad-emoji">${area.emoji}</div>
        <div class="ad-title">
          <h2>${esc(area.name)}</h2>
          <div class="ad-meta">
            <span>推荐等级 ${area.level_range[0]} - ${area.level_range[1]}</span>
            <span>层级 ${area.tier}</span>
            ${bossChip}
          </div>
        </div>
      </div>
      <p class="ad-desc">${esc(area.desc)}</p>
      <div class="ad-actions">${actions}</div>
    `;
  }

  function mapGrid(world) {
    return world.areas.map((a) => {
      const locked = !a.unlocked;
      const cls = [
        'map-card',
        a.current ? 'current' : '',
        locked ? 'locked' : '',
        a.cleared ? 'cleared' : '',
      ].join(' ');
      return `
        <div class="${cls}" data-action="${locked ? 'locked-area' : 'travel'}" data-area="${a.id}">
          <div class="mc-top">
            <span class="mc-emoji">${a.emoji}</span>
            <span class="mc-name">${esc(a.name)}</span>
            <span class="mc-lv">Lv.${a.level_range[0]}-${a.level_range[1]}</span>
          </div>
          <div class="mc-desc">${esc(a.desc)}</div>
          <div class="mc-boss">${a.cleared ? '✓ 已肃清' : a.boss ? '☠ 守关者未击败' : '— 安全区域'}</div>
          ${locked ? '<div class="mc-lock">🔒</div>' : ''}
        </div>`;
    }).join('');
  }

  /* ---------- 背包 ---------- */
  function bag(char) {
    if (!char.inventory.length) {
      return `<div class="empty-tip">背包空空如也。<br />去野外探索，或到晨曦村铁匠铺补给。</div>`;
    }
    const order = { equipment: 0, consumable: 1 };
    const items = [...char.inventory].sort((a, b) => (order[a.type] ?? 9) - (order[b.type] ?? 9));
    return items.map((item) => {
      const isEquip = item.type === 'equipment';
      const sub = isEquip
        ? `${statText(item.stats)} · 需 Lv.${item.req_level}`
        : esc(item.desc);
      const actions = isEquip
        ? `<button class="btn btn-sm" data-action="equip" data-uid="${item.uid}">装备</button>
           <button class="btn btn-sm btn-danger" data-action="sell" data-uid="${item.uid}">出售 ${Math.max(1, Math.floor(item.price * 0.45))}</button>`
        : `<button class="btn btn-sm" data-action="use-item" data-item="${item.item_id}">使用</button>
           <button class="btn btn-sm btn-danger" data-action="sell" data-uid="${item.uid}">出售</button>`;
      return `
        <div class="item-card">
          <div class="ic-top">
            <span class="ic-emoji">${item.emoji || '•'}</span>
            <span class="ic-name" style="color:${rarityColor(item)}">${esc(item.name)}</span>
            <span class="ic-qty">${item.qty ? '×' + item.qty : ''}</span>
          </div>
          <div class="ic-sub">${sub}</div>
          <div class="ic-actions">${actions}</div>
        </div>`;
    }).join('');
  }

  /* ---------- 技能 ---------- */
  function skillList(skills) {
    return skills.map((s) => {
      if (!s.unlocked) {
        return `
          <div class="skill-card locked">
            <div class="sk-top">
              <span>${s.icon}</span>
              <span class="sk-name">${esc(s.name)}</span>
              <span class="sk-lv">Lv.${s.unlock_level} 解锁</span>
            </div>
            <div class="sk-desc">${esc(s.desc)}</div>
          </div>`;
      }
      const profPct = s.prof_need ? pct(s.prof, s.prof_need) : 100;
      return `
        <div class="skill-card">
          <div class="sk-top">
            <span>${s.icon}</span>
            <span class="sk-name">${esc(s.name)}</span>
            <span class="sk-lv">Lv.${s.level}</span>
          </div>
          <div class="sk-desc">${esc(s.desc)}</div>
          <div class="sk-foot">
            <span>法力 ${s.mp}</span>
            <span>${s.level >= s.max_level ? '已精通' : `熟练 ${s.prof}/${s.prof_need}`}</span>
          </div>
          <div class="bar exp thin"><i style="width:${profPct}%"></i></div>
        </div>`;
    }).join('');
  }

  /* ---------- 战斗 ---------- */
  function battleHead(battle) {
    return `
      <div class="battle-head">
        <span class="bh-tag">${battle.is_boss ? 'BOSS BATTLE' : 'ENCOUNTER'}</span>
        <h2>${esc(battle.area_name)}</h2>
        <span class="round">第 ${battle.round} 回合</span>
      </div>`;
  }

  function buffChips(unit) {
    const chips = [];
    (unit.buffs || []).forEach((b) => {
      const label = { atk: '攻', def: '防', agi: '速', dodge: '闪', regen: '愈' }[b.stat] || b.stat;
      const positive = b.pct > 0;
      chips.push(`<span class="chip ${positive ? 'buff' : 'debuff'}">${label}${positive ? '↑' : '↓'}${Math.abs(Math.round(b.pct * 100))}%</span>`);
    });
    (unit.dots || []).forEach((d) => {
      chips.push(`<span class="chip debuff">${d.id === 'poison' ? '毒' : '燃'} ${d.rounds}</span>`);
    });
    if (unit.stunned) chips.push('<span class="chip debuff">眩晕</span>');
    if (unit.enraged) chips.push('<span class="chip enrage">狂暴</span>');
    if (unit.shield) chips.push(`<span class="chip buff">盾 ${unit.shield}</span>`);
    return chips.join('');
  }

  function enemyCards(battle, selected) {
    return battle.enemies.map((e) => {
      const dead = !e.alive || e.hp <= 0;
      const sel = selected === e.index && !dead;
      return `
        <div class="enemy-card ${e.is_boss ? 'boss' : ''} ${dead ? 'dead' : ''} ${sel ? 'selected' : ''} ${dead ? '' : 'targetable'}"
             data-action="target" data-index="${e.index}" data-enemy="${e.index}">
          <div class="ec-top">
            <span class="ec-emoji">${e.emoji}</span>
            <div>
              <div class="ec-name">${esc(e.name)}${e.is_boss ? '<span class="ec-boss-tag">BOSS</span>' : ''}</div>
              <div class="ec-lv">Lv.${e.level} · 攻 ${e.atk} · 防 ${e.def}</div>
            </div>
          </div>
          <div class="ec-hp-text"><span>生命</span><span>${Math.max(0, e.hp)} / ${e.max_hp}</span></div>
          <div class="bar hp thin"><i style="width:${pct(Math.max(0, e.hp), e.max_hp)}%"></i></div>
          <div class="ec-buffs">${buffChips(e)}</div>
        </div>`;
    }).join('');
  }

  function playerStrip(battle, char) {
    const p = battle.player;
    return `
      <div class="player-strip" data-player>
        <div class="ps-top">
          <span class="ec-emoji">${char.class_emoji}</span>
          <div>
            <div class="ps-name">${esc(char.name)}</div>
            <div class="ps-sub">Lv.${char.level} ${esc(char.class_name)} · 闪避 ${p.dodge}%</div>
          </div>
          <div class="ps-bars">
            <div class="ps-bar">
              <div class="vital-head"><span>生命</span><span>${p.hp} / ${p.max_hp}</span></div>
              <div class="bar hp"><i style="width:${pct(p.hp, p.max_hp)}%"></i></div>
            </div>
            <div class="ps-bar">
              <div class="vital-head"><span>法力</span><span>${p.mp} / ${p.max_mp}</span></div>
              <div class="bar mp"><i style="width:${pct(p.mp, p.max_mp)}%"></i></div>
            </div>
          </div>
        </div>
        <div class="ec-buffs">${buffChips(p)}</div>
      </div>`;
  }

  function battleLog(log) {
    return log.map((entry) => {
      const cls = `log-line ${entry.type || ''} ${entry.crit ? 'crit' : ''} enter`;
      let text = esc(entry.text);
      if (entry.dmg) {
        text = text.replace(String(entry.dmg), `<span class="dmg">${entry.dmg}</span>`);
      }
      if (entry.heal) {
        text = text.replace(String(entry.heal), `<span class="heal">${entry.heal}</span>`);
      }
      return `<div class="${cls}"><span class="rt">R${entry.round}</span>${text}</div>`;
    }).join('');
  }

  function battleView(battle, char, picker, selected) {
    const alive = battle.enemies.filter((e) => e.alive).length;
    return `
      <div class="battle-wrap">
        ${battleHead(battle)}
        <div class="enemy-grid">${enemyCards(battle, selected)}</div>
        ${playerStrip(battle, char)}
        <div class="battle-log" id="battle-log">${battleLog(battle.log)}</div>
        <div class="action-bar">
          <button class="btn btn-primary" data-action="battle-attack">普通攻击</button>
          <button class="btn ${picker === 'skill' ? 'btn-primary' : ''}" data-action="battle-skill">技能</button>
          <button class="btn" data-action="battle-defend">防御</button>
          <button class="btn" data-action="battle-dodge">闪避姿态</button>
          <button class="btn ${picker === 'item' ? 'btn-primary' : ''}" data-action="battle-item">道具</button>
          <span class="spacer"></span>
          <button class="btn btn-ghost" data-action="battle-flee" ${battle.can_flee ? '' : 'disabled'}>
            ${battle.can_flee ? '逃跑' : '无法逃脱'}
          </button>
        </div>
        ${picker === 'skill' ? skillPicker(battle, char) : ''}
        ${picker === 'item' ? itemPicker(char) : ''}
        <div class="section-sub" style="text-align:right">剩余敌人 ${alive}</div>
      </div>`;
  }

  function skillPicker(battle, char) {
    const list = (char.skill_view || []).filter((s) => s.unlocked);
    return `
      <div class="picker">
        <div class="picker-head">
          <span>选择技能（点击目标卡片可切换目标）</span>
          <button class="btn btn-sm btn-ghost" data-action="close-picker">收起</button>
        </div>
        <div class="picker-grid">
          ${list.map((s) => {
            const noMp = battle.player.mp < s.mp;
            const support = s.type === 'heal' || s.type === 'buff';
            return `<button class="pick-item" data-action="pick-skill" data-id="${s.id}" ${noMp ? 'disabled' : ''}>
              <div class="pi-top">${s.icon} <b>${esc(s.name)}</b> <span class="sk-lv">Lv.${s.level}</span></div>
              <div class="pi-meta"><span class="mp">法力 ${s.mp}</span> · ${support ? '辅助' : (s.aoe ? '群体' : '单体')}${s.hits > 1 ? ` · ${s.hits} 段` : ''}</div>
            </button>`;
          }).join('')}
        </div>
      </div>`;
  }

  function itemPicker(char) {
    const items = char.inventory.filter((i) => i.type === 'consumable');
    if (!items.length) {
      return `<div class="picker"><div class="picker-head"><span>背包里没有可用道具</span>
        <button class="btn btn-sm btn-ghost" data-action="close-picker">收起</button></div></div>`;
    }
    return `
      <div class="picker">
        <div class="picker-head">
          <span>选择道具</span>
          <button class="btn btn-sm btn-ghost" data-action="close-picker">收起</button>
        </div>
        <div class="picker-grid">
          ${items.map((i) => `
            <button class="pick-item" data-action="pick-item" data-id="${i.item_id}">
              <div class="pi-top">${i.emoji} <b>${esc(i.name)}</b> <span class="ic-qty">×${i.qty}</span></div>
              <div class="pi-meta">${esc(i.desc)}</div>
            </button>`).join('')}
        </div>
      </div>`;
  }

  function resultCard(battle) {
    const won = battle.status === 'won';
    const rewards = battle.rewards || {};
    const title = won ? '战斗胜利' : battle.status === 'fled' ? '成功脱离' : '你倒下了';
    const sub = won
      ? '战利品已收入背包，自动存档已更新。'
      : battle.status === 'fled'
        ? '你退回安全地带，未能获得奖励。'
        : '你在晨曦村醒来，损失了部分金币。';
    const loot = (rewards.drops || []).map((d) => {
      if (d.type === 'gold_convert') {
        return `<div class="loot-row"><span>💰</span><span>${esc(d.name)}</span><span class="lr-tag">折算 ${d.gold} 金币</span></div>`;
      }
      return `<div class="loot-row"><span>${d.emoji || '◆'}</span>
        <span style="color:${d.color || '#e8ebf2'}">${esc(d.name)}</span>
        <span class="lr-tag">${d.qty ? '×' + d.qty : d.rarity_name || ''}</span></div>`;
    }).join('');
    return `
      <div class="result-card">
        <h2>${title}</h2>
        <p class="rc-sub">${sub}</p>
        ${won ? `<div class="result-stats">
          <div class="rs"><b>+${rewards.exp || 0}</b><span>经验</span></div>
          <div class="rs"><b>+${rewards.gold || 0}</b><span>金币</span></div>
          <div class="rs"><b>${(rewards.drops || []).length}</b><span>战利品</span></div>
        </div>
        <div class="loot-list">${loot || '<div class="empty-tip">没有掉落物</div>'}</div>` : ''}
        <button class="btn btn-primary" style="min-width:180px" data-action="battle-continue">继续旅程</button>
      </div>`;
  }

  return {
    esc, pct, fmtTime, statText, rarityColor,
    classList, saveList, characterPanel, areaDetail, mapGrid, bag, skillList,
    battleView, resultCard,
  };
})();
