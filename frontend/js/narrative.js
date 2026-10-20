/* 叙事层：章节旁白、Boss 对话、结局页。
 *
 * 统一用一块浮层承载三种场景，靠 payload.kind 区分表现：
 *   prologue / enter / boss_pre / boss_post  → 章节卡 + 逐条台词
 *   ending                                   → 台词 + 通关统计 + 尾声
 */
const Narrative = (() => {
  let layer = null;
  let resolveClose = null;
  let busy = false;

  const esc = (value) => String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

  function ensure() {
    if (layer) return layer;
    layer = document.createElement('div');
    layer.className = 'story-layer';
    layer.hidden = true;
    layer.innerHTML = `
      <div class="story-backdrop"></div>
      <article class="story-panel" role="dialog" aria-modal="true" aria-labelledby="story-title">
        <div class="story-rule top" aria-hidden="true"></div>
        <header class="story-head">
          <span class="story-kicker"></span>
          <h2 class="story-title" id="story-title"></h2>
        </header>
        <div class="story-body"></div>
        <footer class="story-foot">
          <span class="story-hint">点击任意处继续</span>
          <button class="btn btn-primary" data-story-close>继续</button>
        </footer>
        <div class="story-rule bottom" aria-hidden="true"></div>
      </article>`;
    document.body.appendChild(layer);

    layer.addEventListener('click', (e) => {
      if (e.target.closest('[data-story-close]')) {
        close();
        return;
      }
      // 第一次点击跳过逐条动画；全部显示后再点一次即关闭
      if (!layer.classList.contains('reveal-all')) {
        layer.classList.add('reveal-all');
        if (window.Sound) Sound.sfx('page');
      } else {
        close();
      }
    });

    document.addEventListener('keydown', (e) => {
      if (layer.hidden) return;
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'Escape') {
        e.preventDefault();
        if (!layer.classList.contains('reveal-all')) layer.classList.add('reveal-all');
        else close();
      }
    });
    return layer;
  }

  function lineHtml(line, index, kind) {
    const who = (line.who || '').trim();
    const narration = !who || who === '旁白';
    return `
      <p class="story-line ${narration ? 'narration' : 'speech'}" style="--i:${index}">
        ${narration ? '' : `<span class="story-who">${esc(who)}</span>`}
        <span class="story-text">${esc(line.text)}</span>
      </p>`;
  }

  function statsHtml(stats) {
    if (!stats) return '';
    const fmt = (seconds) => {
      const t = Math.max(0, Math.floor(seconds || 0));
      const h = Math.floor(t / 3600);
      const m = Math.floor((t % 3600) / 60);
      return h > 0 ? `${h}:${String(m).padStart(2, '0')}` : `${m} 分`;
    };
    const rows = [
      ['等级', `Lv.${stats.level}`],
      ['击败', `${stats.kills}`],
      ['守关者', `${stats.bosses} / 9`],
      ['金币', `${stats.gold}`],
      ['行程', `${stats.steps} 步`],
      ['用时', fmt(stats.playtime)],
    ];
    return `<div class="story-stats">${rows.map(([k, v]) => `
      <div class="ss-cell"><b>${esc(v)}</b><span>${esc(k)}</span></div>`).join('')}</div>`;
  }

  /**
   * 播放一段叙事。payload: { kind, kicker, title, lines, epilogue }
   * opts: { stats, onClose }
   */
  function play(payload, opts = {}) {
    if (!payload || !payload.lines || !payload.lines.length) return Promise.resolve();
    const el = ensure();
    if (busy) return Promise.resolve();
    busy = true;

    const isEnding = payload.kind === 'ending';
    el.classList.toggle('is-ending', isEnding);
    el.classList.remove('reveal-all');

    el.querySelector('.story-kicker').textContent = payload.kicker || '';
    el.querySelector('.story-title').textContent = payload.title || '';

    const lines = payload.lines;
    const stats = isEnding ? statsHtml(opts.stats) : '';
    const epilogue = isEnding && payload.epilogue
      ? `<p class="story-epilogue" style="--i:${lines.length + 1}">${esc(payload.epilogue)}</p>`
      : '';

    el.querySelector('.story-body').innerHTML = lines.map((l, i) => lineHtml(l, i, payload.kind)).join('') + stats + epilogue;
    el.querySelector('[data-story-close]').textContent = isEnding ? '回到十域' : '继续';
    el.querySelector('.story-hint').textContent = isEnding ? '' : '点击任意处继续';

    el.hidden = false;
    void el.offsetWidth;
    el.classList.add('in');
    if (window.Sound) Sound.sfx(isEnding ? 'ending' : 'page');

    // 台词播完后自动进入「可关闭」状态，按钮始终可点，不逼玩家逐句点
    const total = (lines.length + (epilogue ? 1 : 0)) * 240 + 700;
    const timer = setTimeout(() => el.classList.add('reveal-all'), total);

    return new Promise((resolve) => {
      resolveClose = () => {
        clearTimeout(timer);
        busy = false;
        if (opts.onClose) opts.onClose();
        resolve();
      };
    });
  }

  function close() {
    if (!layer || layer.hidden) return;
    if (window.Sound) Sound.sfx('click');
    layer.classList.remove('in');
    layer.hidden = true;
    const done = resolveClose;
    resolveClose = null;
    if (done) done();
  }

  return { play, close, get open() { return !!layer && !layer.hidden; } };
})();

window.Narrative = Narrative;
