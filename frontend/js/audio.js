/* 音频层：ZzFX 负责音效，TinyMusic 负责 BGM，统一走音量与静音开关。
 *
 * 设计要点：
 * - 零音频素材。所有声音都由振荡器实时合成，仓库里没有一个 mp3/ogg。
 * - 浏览器自动播放策略要求首次用户手势后才能出声，因此音频上下文在 unlock() 中恢复。
 * - BGM 按「场景」切换而不是按区域：同一首曲子覆盖多个区域，避免十首曲子互相打断。
 */
const Sound = (() => {
  const STORE_KEY = 'shiyu-audio';
  const state = {
    music: true,
    sfx: true,
    musicVol: 0.55,
    sfxVol: 0.7,
  };

  let ac = null;
  let musicBus = null;
  let current = null;      // { id, gain, seqs }
  let unlocked = false;
  let wanted = null;       // 解锁前请求过的曲目，解锁后补播

  /* ---------------- 持久化 ---------------- */
  function load() {
    try {
      const raw = JSON.parse(localStorage.getItem(STORE_KEY) || '{}');
      ['music', 'sfx'].forEach((k) => {
        if (typeof raw[k] === 'boolean') state[k] = raw[k];
      });
      ['musicVol', 'sfxVol'].forEach((k) => {
        if (typeof raw[k] === 'number') state[k] = Math.max(0, Math.min(1, raw[k]));
      });
    } catch (e) { /* 忽略损坏的设置 */ }
  }

  function persist() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch (e) { /* 忽略 */ }
  }

  /* ---------------- 上下文 ---------------- */
  function ensure() {
    if (ac) return ac;
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    try {
      ac = new Ctx();
      musicBus = ac.createGain();
      musicBus.gain.value = state.music ? state.musicVol : 0;
      musicBus.connect(ac.destination);
    } catch (e) {
      ac = null;
    }
    return ac;
  }

  /** 首次用户手势时调用：恢复上下文并补播待播曲目。 */
  function unlock() {
    if (unlocked) return;
    unlocked = true;
    if (ac && ac.state === 'suspended') ac.resume();
    // ZzFX 自带一个上下文，需要单独恢复
    try {
      if (typeof zzfxX !== 'undefined' && zzfxX && zzfxX.state === 'suspended') zzfxX.resume();
    } catch (e) { /* 音效不可用时静默降级 */ }
    if (wanted) {
      const id = wanted;
      wanted = null;
      bgm(id);
    }
  }

  /* ---------------- 音效 ---------------- */
  // ZzFX 参数顺序：音量, 随机, 频率, 起音, 持续, 释放, 波形, 波形曲线,
  //               滑音, 滑音增量, 跳变, 跳变时长, 重复, 噪声, 调制, 位压, 延迟, 持续音量, 衰减, 颤音, 滤波
  const SFX = {
    click: [0.22, 0, 720, 0, 0.01, 0.04, 1, 1.7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.7],
    page: [0.18, 0.03, 330, 0, 0.03, 0.15, 0, 1, 5, 0, 0, 0, 0, 0.12, 0, 0, 0, 0.6],
    hit: [0.5, 0.12, 150, 0, 0.04, 0.16, 3, 1.2, -9, 0, 0, 0, 0, 0.42, 0, 0, 0, 0.5],
    crit: [0.58, 0.1, 240, 0, 0.02, 0.2, 2, 1.4, -14, 2, 70, 0.05, 0, 0.3, 0, 0, 0, 0.6],
    magic: [0.4, 0, 520, 0, 0.06, 0.3, 0, 1, 20, 3, 0, 0, 0, 0, 24, 0, 0, 0.72],
    heal: [0.34, 0, 430, 0, 0.05, 0.36, 0, 1, 28, 0, 0, 0, 0, 0, 12, 0, 0, 0.8],
    miss: [0.24, 0.2, 920, 0, 0.01, 0.09, 5, 1, 0, 0, 0, 0, 0, 0.6, 0, 0, 0, 0.4],
    block: [0.4, 0.05, 110, 0, 0.03, 0.13, 1, 1, -6, 0, 0, 0, 0, 0.25, 0, 0, 0, 0.6],
    roar: [0.68, 0.3, 88, 0.02, 0.26, 0.62, 3, 1, -16, 4, 0, 0, 0, 0.5, 10, 0, 0, 0.8],
    defeat: [0.5, 0, 300, 0.02, 0.2, 0.9, 2, 1, -22, 6, 0, 0, 0, 0, 0, 0, 0, 0.72],
    loot: [0.28, 0, 880, 0, 0.02, 0.13, 1, 1.2, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0.6],
    error: [0.3, 0, 190, 0, 0.02, 0.18, 3, 1, -4, 0, 0, 0, 0, 0.1, 0, 0, 0, 0.5],
    save: [0.26, 0, 560, 0, 0.03, 0.16, 1, 1.3, 14, 0, 0, 0, 0, 0, 0, 0, 0, 0.65],
    turn: [0.2, 0, 480, 0, 0.01, 0.06, 1, 1.5, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0.6],
  };

  // 多音琶音：ZzFX 单次只能发一个音，短句用定时器串起来
  const JINGLE = {
    victory: [[0, 660, 0.16], [0.11, 880, 0.16], [0.22, 990, 0.2], [0.34, 1320, 0.5]],
    levelup: [[0, 700, 0.12], [0.09, 930, 0.12], [0.18, 1240, 0.32]],
    ending: [[0, 523, 0.3], [0.18, 659, 0.3], [0.36, 784, 0.3], [0.54, 1046, 0.7]],
  };

  function playZzfx(args) {
    if (typeof zzfx !== 'function') return;
    try { zzfx(...args); } catch (e) { /* 单次失败不影响游戏 */ }
  }

  function sfx(name) {
    if (!state.sfx) return;
    if (JINGLE[name]) {
      const notes = JINGLE[name];
      notes.forEach(([delay, freq, dur]) => {
        setTimeout(() => {
          if (!state.sfx) return;
          playZzfx([0.34 * state.sfxVol, 0, freq, 0, 0.02, dur, 1, 1.25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.75]);
        }, delay * 1000);
      });
      return;
    }
    const preset = SFX[name];
    if (!preset) return;
    const args = preset.slice();
    args[0] = args[0] * state.sfxVol;
    playZzfx(args);
  }

  /* ---------------- BGM ---------------- */
  // 每层：wave 波形、gain 层音量、notes 音符串（字母为音名，w/h/q/e/s 为时值）
  const TRACKS = {
    title: {
      tempo: 72,
      layers: [
        { wave: 'triangle', gain: 0.1, notes: ['A2 w', 'F2 w', 'C3 w', 'G2 w'] },
        { wave: 'sine', gain: 0.07, notes: ['A3 w', 'F3 w', 'C4 w', 'G3 w'] },
        { wave: 'triangle', gain: 0.06, staccato: 0.15, notes: ['E5 h', 'C5 h', 'D5 h', 'A4 h', 'C5 h', 'B4 h', 'A4 w'] },
      ],
    },
    village: {
      tempo: 84,
      layers: [
        { wave: 'triangle', gain: 0.1, notes: ['C3 h', 'G2 h', 'A2 h', 'F2 h', 'C3 h', 'G2 h', 'A2 h', 'F2 h'] },
        { wave: 'sine', gain: 0.06, notes: ['C4 w', 'A3 w', 'F3 w', 'G3 w'] },
        { wave: 'triangle', gain: 0.055, staccato: 0.2, notes: ['G4 q', 'E4 q', 'C4 h', 'D4 q', 'E4 q', 'G4 h', 'G4 q', 'E4 q', 'C4 h', 'D4 q', 'E4 q', 'G4 h'] },
      ],
    },
    wild: {
      tempo: 104,
      layers: [
        { wave: 'triangle', gain: 0.11, notes: ['D2 h', 'A2 h', 'F2 h', 'C3 h', 'D2 h', 'A2 h', 'Bb2 h', 'C3 h'] },
        { wave: 'sine', gain: 0.055, notes: ['D4 w', 'F4 w', 'Bb3 w', 'A3 w'] },
        { wave: 'triangle', gain: 0.06, staccato: 0.25, notes: ['A4 e', 'D5 e', 'F5 q', 'E5 q', 'D5 h', 'C5 e', 'D5 e', 'E5 q', 'D5 q', 'A4 h', 'F4 q', 'G4 q', 'A4 h', '- h'] },
      ],
    },
    dark: {
      tempo: 88,
      layers: [
        { wave: 'triangle', gain: 0.11, notes: ['D2 w', 'D2 w', 'Eb2 w', 'D2 w'] },
        { wave: 'sine', gain: 0.08, notes: ['D3 w', 'D3 w', 'Eb3 w', 'D3 w'] },
        { wave: 'sine', gain: 0.05, staccato: 0.4, notes: ['F4 h', '- h', 'Ab4 h', '- h', 'G4 h', '- h', 'F4 w'] },
      ],
    },
    battle: {
      tempo: 132,
      layers: [
        { wave: 'triangle', gain: 0.12, notes: ['E2 e', 'E2 e', 'E2 e', 'E2 e', 'E2 e', 'E2 e', 'G2 e', 'A2 e', 'E2 e', 'E2 e', 'E2 e', 'E2 e', 'D2 e', 'D2 e', 'C2 e', 'B1 e'] },
        { wave: 'triangle', gain: 0.06, staccato: 0.3, notes: ['E5 q', 'G5 q', 'B5 q', 'A5 q', 'G5 q', 'E5 q', 'D5 h'] },
        { wave: 'sine', gain: 0.04, notes: ['E3 q', '- q', 'B3 q', '- q', 'E3 q', '- q', 'D3 h'] },
      ],
    },
    boss: {
      tempo: 146,
      layers: [
        { wave: 'triangle', gain: 0.13, notes: ['C2 e', 'C2 e', 'C2 e', 'C2 e', 'C2 e', 'C2 e', 'Db2 e', 'D2 e', 'C2 e', 'C2 e', 'C2 e', 'C2 e', 'Eb2 e', 'Eb2 e', 'F2 e', 'Gb2 e'] },
        { wave: 'triangle', gain: 0.07, staccato: 0.35, notes: ['C5 q', 'Eb5 q', 'F5 q', 'Ab5 q', 'G5 q', 'F5 q', 'Eb5 h'] },
        { wave: 'sine', gain: 0.05, notes: ['C6 h', '- h', 'Bb5 h', '- h'] },
      ],
    },
    ending: {
      tempo: 68,
      layers: [
        { wave: 'triangle', gain: 0.1, notes: ['C3 w', 'G2 w', 'A2 w', 'F2 w'] },
        { wave: 'sine', gain: 0.075, notes: ['E4 w', 'G4 w', 'A4 w', 'F4 w'] },
        { wave: 'triangle', gain: 0.06, staccato: 0.1, notes: ['E5 h', 'G5 h', 'C5 h', 'D5 h', 'E5 h', 'D5 h', 'C5 w'] },
      ],
    },
  };

  // 区域 → 曲目
  const AREA_TRACK = {
    village: 'village',
    forest: 'wild',
    mine: 'wild',
    swamp: 'dark',
    desert: 'wild',
    frost: 'dark',
    graveyard: 'dark',
    lava: 'dark',
    temple: 'dark',
    void: 'dark',
  };

  function stopTrack(track) {
    if (!track) return;
    const now = ac.currentTime;
    try {
      track.gain.gain.cancelScheduledValues(now);
      track.gain.gain.setValueAtTime(track.gain.gain.value, now);
      track.gain.gain.linearRampToValueAtTime(0, now + 0.5);
    } catch (e) { /* 已断开 */ }
    setTimeout(() => {
      track.seqs.forEach((s) => { try { s.stop(); } catch (e) { /* 忽略 */ } });
      try { track.gain.disconnect(); } catch (e) { /* 忽略 */ }
    }, 620);
  }

  /** 切换 BGM。同一首曲子重复调用不会打断。 */
  function bgm(id) {
    if (!ensure()) return;
    if (!unlocked) { wanted = id; return; }
    if (current && current.id === id) return;
    const def = TRACKS[id];
    if (!def || !state.music) {
      stopTrack(current);
      current = null;
      return;
    }
    if (current) { stopTrack(current); current = null; }
    if (!window.TinyMusic) return;

    const gain = ac.createGain();
    gain.gain.value = 0;
    gain.connect(musicBus);
    const seqs = def.layers.map((layer) => {
      const seq = new TinyMusic.Sequence(ac, def.tempo, layer.notes);
      seq.loop = true;
      seq.waveType = layer.wave;
      seq.staccato = layer.staccato || 0;
      seq.gain.gain.value = layer.gain;
      seq.treble.disconnect();
      seq.treble.connect(gain);
      seq.play();
      return seq;
    });
    gain.gain.linearRampToValueAtTime(1, ac.currentTime + 1.1);
    current = { id, gain, seqs };
  }

  /** 根据区域切曲；战斗中不覆盖战斗曲。 */
  function mood(areaId) {
    if (current && (current.id === 'battle' || current.id === 'boss')) return;
    bgm(AREA_TRACK[areaId] || 'wild');
  }

  function battleMusic(isBoss) {
    bgm(isBoss ? 'boss' : 'battle');
  }

  /* ---------------- 开关 ---------------- */
  function setMusic(on) {
    state.music = !!on;
    persist();
    if (!ensure()) return;
    if (!on) {
      if (current) { stopTrack(current); current = null; }
      musicBus.gain.value = 0;
    } else {
      musicBus.gain.value = state.musicVol;
      if (wanted) { const id = wanted; wanted = null; bgm(id); }
    }
  }

  function setMusicVol(v) {
    state.musicVol = Math.max(0, Math.min(1, v));
    persist();
    if (musicBus) musicBus.gain.value = state.music ? state.musicVol : 0;
  }

  function setSfx(on) {
    state.sfx = !!on;
    persist();
  }

  function setSfxVol(v) {
    state.sfxVol = Math.max(0, Math.min(1, v));
    persist();
  }

  function init() {
    load();
    ensure();
    ['pointerdown', 'keydown', 'touchstart'].forEach((evt) => {
      window.addEventListener(evt, unlock, { once: true, passive: true });
    });
    document.addEventListener('visibilitychange', () => {
      if (!ac) return;
      if (document.hidden) ac.suspend();
      else if (unlocked) ac.resume();
    });
  }

  return {
    init, unlock, sfx, bgm, mood, battleMusic,
    setMusic, setMusicVol, setSfx, setSfxVol,
    get settings() { return { ...state }; },
    get track() { return current ? current.id : null; },
    get contextState() { return ac ? ac.state : 'none'; },
  };
})();

// 顶层 const 只进全局词法环境，不挂 window；显式导出一次，方便其它脚本判空
window.Sound = Sound;
