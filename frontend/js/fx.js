/* ============================================================
   FX：背景星海 / 3D 交互 / SVG 小人 / 电影化开场
   纯原生实现，无依赖。暴露 window.FX 与 window.Sprite。
   ============================================================ */
(function () {
  'use strict';

  /* ==========================================================
     Sprite：内联 SVG 小人 & 怪物
     ========================================================== */
  let _uid = 0;
  const nid = () => 'fx' + (++_uid);

  const HERO_THEME = {
    warrior: {
      cloak1: '#9c4238', cloak2: '#3b1613', body1: '#8792a3', body2: '#3b4250',
      accent: '#f0cd8c', trim: '#c9a45f', hair: '#3a2b22', skin: '#f2d5b8',
    },
    mage: {
      cloak1: '#6344ad', cloak2: '#241243', body1: '#43589b', body2: '#1c2547',
      accent: '#c39bff', trim: '#9a76ff', hair: '#2a1f3d', skin: '#f0d3bd',
    },
    ranger: {
      cloak1: '#2f8158', cloak2: '#0d2a1c', body1: '#4f7258', body2: '#1f2f26',
      accent: '#9df0bd', trim: '#63b98a', hair: '#2a2119', skin: '#eed0b4',
    },
    cleric: {
      cloak1: '#e2d5b2', cloak2: '#8d7c4f', body1: '#efe7d2', body2: '#b0a37c',
      accent: '#ffe9a8', trim: '#ffdf9a', hair: '#d8c99c', skin: '#f6ddc4',
    },
  };

  function heroWeapon(classId, t) {
    if (classId === 'mage') {
      return `
        <g class="sp-weapon">
          <rect x="96" y="52" width="4.5" height="102" rx="2.2" fill="#6b5433"/>
          <circle cx="98" cy="50" r="10" fill="${t.accent}" opacity=".28"/>
          <circle class="sp-orb" cx="98" cy="50" r="6.4" fill="${t.accent}"/>
          <circle cx="98" cy="50" r="2.8" fill="#fffaf0"/>
        </g>`;
    }
    if (classId === 'ranger') {
      return `
        <g class="sp-weapon">
          <path d="M101 58 C 122 82, 122 122, 101 146" fill="none" stroke="${t.trim}" stroke-width="3.6" stroke-linecap="round"/>
          <path d="M101 58 L 101 146" fill="none" stroke="rgba(240,245,255,.55)" stroke-width="1.1"/>
        </g>`;
    }
    if (classId === 'cleric') {
      return `
        <g class="sp-weapon">
          <rect x="97" y="54" width="4" height="100" rx="2" fill="#8a7448"/>
          <circle cx="99" cy="44" r="11" fill="none" stroke="${t.trim}" stroke-width="2.4"/>
          <circle cx="99" cy="44" r="12" fill="${t.accent}" opacity=".22"/>
          <circle class="sp-orb" cx="99" cy="44" r="4.6" fill="#fffdf2"/>
        </g>`;
    }
    return `
      <g class="sp-weapon">
        <rect x="94" y="58" width="6" height="60" rx="2" fill="#d7e2f2" transform="rotate(11 97 88)"/>
        <rect x="88" y="114" width="19" height="5" rx="2.5" fill="${t.trim}"/>
        <rect x="94.5" y="118" width="5" height="15" rx="2.5" fill="#4a3520"/>
      </g>`;
  }

  function heroHead(classId, t) {
    const hat = classId === 'mage'
      ? `<path d="M70 4 L97 42 L43 42 Z" fill="url(#cloak)" opacity=".96"/>
         <ellipse cx="70" cy="42" rx="30" ry="6" fill="${t.cloak2}"/>`
      : '';
    const hood = classId === 'ranger'
      ? `<path d="M46 50 C 46 22, 94 22, 94 50 C 90 38, 50 38, 46 50 Z" fill="url(#cloak)"/>`
      : '';
    const halo = classId === 'cleric'
      ? `<ellipse cx="70" cy="14" rx="17" ry="4.6" fill="none" stroke="${t.trim}" stroke-width="2.6" opacity=".95"/>
         <ellipse cx="70" cy="14" rx="17" ry="4.6" fill="none" stroke="${t.accent}" stroke-width="5" opacity=".22"/>`
      : '';
    return `
      <g class="sp-head">
        ${hat}
        <circle cx="70" cy="48" r="21.5" fill="${t.skin}"/>
        <path d="M49 46 C 50 26, 90 26, 91 46 C 86 37, 78 33, 70 34 C 62 33, 54 37, 49 46 Z" fill="${t.hair}"/>
        <circle cx="62" cy="50" r="2.5" fill="#2a2330"/>
        <circle cx="78" cy="50" r="2.5" fill="#2a2330"/>
        <circle cx="62.9" cy="49.2" r=".9" fill="#fff" opacity=".9"/>
        <circle cx="78.9" cy="49.2" r=".9" fill="#fff" opacity=".9"/>
        <path d="M66 57 Q 70 60 74 57" fill="none" stroke="#b57a63" stroke-width="1.5" stroke-linecap="round"/>
        <ellipse cx="57" cy="55" rx="3.4" ry="2" fill="#e39a8c" opacity=".45"/>
        <ellipse cx="83" cy="55" rx="3.4" ry="2" fill="#e39a8c" opacity=".45"/>
        ${hood}
        ${halo}
      </g>`;
  }

  function hero(classId, extraClass) {
    const t = HERO_THEME[classId] || HERO_THEME.warrior;
    const c = nid();
    return `
      <svg class="sprite ${extraClass || ''}" viewBox="0 0 140 190" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <defs>
          <linearGradient id="cloak${c}" x1="0" y1="0" x2=".35" y2="1">
            <stop offset="0" stop-color="${t.cloak1}"/>
            <stop offset="1" stop-color="${t.cloak2}"/>
          </linearGradient>
          <linearGradient id="body${c}" x1="0" y1="0" x2=".4" y2="1">
            <stop offset="0" stop-color="${t.body1}"/>
            <stop offset="1" stop-color="${t.body2}"/>
          </linearGradient>
          <radialGradient id="aura${c}">
            <stop offset="0" stop-color="${t.accent}" stop-opacity=".40"/>
            <stop offset=".55" stop-color="${t.accent}" stop-opacity=".12"/>
            <stop offset="1" stop-color="${t.accent}" stop-opacity="0"/>
          </radialGradient>
        </defs>
        <ellipse cx="70" cy="179" rx="33" ry="6" fill="rgba(0,0,0,.55)"/>
        <g class="sp-root">
          <g class="sp-breathe">
            <ellipse class="sp-aura" cx="70" cy="118" rx="50" ry="64" fill="url(#aura${c})"/>
            <path class="sp-cloak" d="M70 64 C 47 66 37 96 33 152 C 50 167 90 167 107 152 C 103 96 93 66 70 64 Z" fill="url(#cloak${c})" stroke="rgba(8,10,16,.45)" stroke-width="1.6"/>
            <path d="M70 64 C 55 66 47 92 44 150 L 56 150 C 58 104 62 78 70 70 Z" fill="rgba(255,255,255,.06)"/>
            <rect x="56" y="138" width="12.5" height="32" rx="6" fill="#2b3140"/>
            <rect x="71.5" y="138" width="12.5" height="32" rx="6" fill="#20242f"/>
            <rect x="51" y="164" width="21" height="10" rx="5" fill="#161a23"/>
            <rect x="69" y="164" width="21" height="10" rx="5" fill="#11141b"/>
            <path d="M70 70 C 56 70 50 84 50 101 L 50 133 C 58 141 82 141 90 133 L 90 101 C 90 84 84 70 70 70 Z" fill="url(#body${c})" stroke="rgba(8,10,16,.35)" stroke-width="1.4"/>
            <path d="M70 70 C 63 70 58 74 55 80 L 55 100 L 85 100 L 85 80 C 82 74 77 70 70 70 Z" fill="rgba(255,255,255,.10)"/>
            <rect x="50" y="124" width="40" height="7.5" rx="3.5" fill="#3b2f1c"/>
            <rect x="65" y="123" width="10" height="9.5" rx="2" fill="${t.trim}"/>
            <g class="sp-arm-left">
              <rect x="40" y="82" width="12" height="40" rx="6" fill="url(#body${c})" transform="rotate(6 46 102)"/>
              <circle cx="45" cy="123" r="6" fill="${t.skin}"/>
            </g>
            <g class="sp-arm-right">
              <rect x="88" y="82" width="12" height="40" rx="6" fill="url(#body${c})" transform="rotate(-6 94 102)"/>
              <circle cx="96" cy="123" r="6" fill="${t.skin}"/>
              ${heroWeapon(classId, t)}
            </g>
            <path d="M50 76 C 44 78 40 84 39 90 L 50 94 Z" fill="${t.trim}" opacity=".85"/>
            <path d="M90 76 C 96 78 100 84 101 90 L 90 94 Z" fill="${t.trim}" opacity=".85"/>
            ${heroHead(classId, t)}
          </g>
        </g>
      </svg>`;
  }

  const hash = (str) => {
    let h = 2166136261;
    for (let i = 0; i < String(str).length; i += 1) {
      h ^= String(str).charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return Math.abs(h);
  };

  function monster(seed, boss, extraClass) {
    const h = hash(seed);
    const HUES = [4, 26, 44, 88, 142, 176, 205, 262, 316];
    const hue = HUES[h % HUES.length];
    const body1 = `hsl(${hue} 46% 36%)`;
    const body2 = `hsl(${(hue + 26) % 360} 54% 15%)`;
    const eye = `hsl(${(hue + 168) % 360} 92% 64%)`;
    const c = nid();
    const horns = (h >> 3) % 3;
    const eyes = boss ? 3 : (h >> 5) % 2 === 0 ? 2 : 3;
    const eyeXs = eyes === 2 ? [57, 83] : [50, 70, 90];
    const eyeY = eyes === 2 ? 76 : 72;

    const hornSvg = horns === 0
      ? `<path d="M48 46 C 40 26 42 14 52 8 C 50 22 54 34 58 42 Z" fill="${body2}"/>
         <path d="M92 46 C 100 26 98 14 88 8 C 90 22 86 34 82 42 Z" fill="${body2}"/>`
      : horns === 1
        ? `<path d="M52 44 C 44 30 46 18 54 10 C 56 24 60 34 62 42 Z" fill="${body2}"/>`
        : `<path d="M46 50 C 34 44 28 34 30 26 C 40 32 46 38 52 44 Z" fill="${body2}"/>
           <path d="M94 50 C 106 44 112 34 110 26 C 100 32 94 38 88 44 Z" fill="${body2}"/>`;

    const crown = boss
      ? `<path d="M50 24 L58 36 L66 22 L74 36 L82 22 L90 36 L96 26 L94 46 L52 46 Z"
              fill="hsl(45 78% 62%)" stroke="hsl(45 70% 40%)" stroke-width="1.2" opacity=".95"/>`
      : '';

    return `
      <svg class="sprite ${boss ? 'boss-monster' : ''} ${extraClass || ''}" viewBox="0 0 140 180" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <defs>
          <linearGradient id="mb${c}" x1="0" y1="0" x2=".4" y2="1">
            <stop offset="0" stop-color="${body1}"/>
            <stop offset="1" stop-color="${body2}"/>
          </linearGradient>
          <radialGradient id="me${c}">
            <stop offset="0" stop-color="${eye}" stop-opacity=".95"/>
            <stop offset="1" stop-color="${eye}" stop-opacity="0"/>
          </radialGradient>
          <radialGradient id="ma${c}">
            <stop offset="0" stop-color="${eye}" stop-opacity=".28"/>
            <stop offset="1" stop-color="${eye}" stop-opacity="0"/>
          </radialGradient>
        </defs>
        <ellipse cx="70" cy="168" rx="40" ry="7" fill="rgba(0,0,0,.55)"/>
        <g class="sp-root">
          <g class="sp-breathe">
            <ellipse class="sp-aura" cx="70" cy="100" rx="56" ry="66" fill="url(#ma${c})"/>
            <path d="M70 42 C 42 42 30 70 32 108 C 34 146 48 162 70 162 C 92 162 106 146 108 108 C 110 70 98 42 70 42 Z" fill="url(#mb${c})"/>
            <ellipse cx="70" cy="118" rx="26" ry="30" fill="rgba(255,255,255,.07)"/>
            <path d="M40 104 C 26 110 22 126 28 136 C 34 130 38 122 42 116 Z" fill="url(#mb${c})"/>
            <path d="M100 104 C 114 110 118 126 112 136 C 106 130 102 122 98 116 Z" fill="url(#mb${c})"/>
            <path d="M36 136 L28 148 L38 146 Z" fill="${body2}"/>
            <path d="M104 136 L112 148 L102 146 Z" fill="${body2}"/>
            ${hornSvg}
            ${crown}
            ${eyeXs.map((x) => `
              <circle cx="${x}" cy="${eyeY}" r="11" fill="url(#me${c})"/>
              <circle cx="${x}" cy="${eyeY}" r="4.4" fill="${eye}"/>
              <circle cx="${x}" cy="${eyeY}" r="1.8" fill="#10131b"/>`).join('')}
            <path d="M56 98 Q 70 108 84 98 Q 70 118 56 98 Z" fill="#160f14"/>
            <path d="M60 100 L64 108 L67 100 Z" fill="#f3ead8"/>
            <path d="M73 100 L76 108 L80 100 Z" fill="#f3ead8"/>
            <path d="M46 62 C 52 56 60 54 66 56" fill="none" stroke="rgba(255,255,255,.18)" stroke-width="2" stroke-linecap="round"/>
          </g>
        </g>
      </svg>`;
  }

  /* ---- 区域场景插画：每个区域一张程序化生成的风景 ---- */
  const AREA_PALETTE = {
    village: ['#2e3d37', '#0b1313', '#f0c884'],
    forest: ['#1d3b31', '#08130f', '#8fe0b4'],
    mine: ['#332718', '#0c0a08', '#e8b268'],
    swamp: ['#243527', '#0a120d', '#a8cc74'],
    desert: ['#45301d', '#150e09', '#f5b872'],
    frost: ['#203347', '#080f16', '#b4e0f5'],
    graveyard: ['#2a2940', '#0b0a12', '#c4b4e8'],
    lava: ['#45201a', '#120706', '#ff8a55'],
    temple: ['#34342c', '#0f0f0c', '#fff0b8'],
    void: ['#2b1f3f', '#080511', '#d49bff'],
  };

  function ridge(y, amp, color, phase) {
    let d = `M0 ${y}`;
    for (let x = 20; x <= 320; x += 20) {
      const h = y - amp * (0.55 + 0.45 * Math.sin(x / 46 + phase) * Math.cos(x / 110 + phase * 0.7));
      d += ` L${x} ${h.toFixed(1)}`;
    }
    return `<path d="${d} L320 160 L0 160 Z" fill="${color}"/>`;
  }

  function sceneFeature(areaId, a) {
    switch (areaId) {
      case 'village':
        return `<g>
          <path d="M34 122 L34 98 L58 82 L82 98 L82 122 Z" fill="#0f1b19"/>
          <path d="M92 122 L92 106 L112 92 L132 106 L132 122 Z" fill="#0b1513"/>
          <path d="M150 122 L150 110 L166 100 L182 110 L182 122 Z" fill="#0a1311"/>
          <rect x="52" y="102" width="8" height="10" fill="${a}" opacity=".6"/>
          <rect x="105" y="106" width="7" height="9" fill="${a}" opacity=".45"/>
          <circle cx="56" cy="107" r="13" fill="${a}" opacity=".10"/>
          <circle cx="108" cy="110" r="10" fill="${a}" opacity=".08"/>
          <path d="M60 82 q9 -13 0 -24 q-7 -9 2 -16" stroke="rgba(220,230,225,.16)" stroke-width="2" fill="none"/>
        </g>`;
      case 'forest':
        return `<g>
          ${[26, 58, 92, 128, 206, 246, 286].map((x, i) => {
            const h = 34 + (i % 3) * 16;
            return `<path d="M${x} ${118 - h} L${x - 11} 118 L${x + 11} 118 Z" fill="#0b1c17"/>
                    <rect x="${x - 1.5}" y="116" width="3" height="8" fill="#08110e"/>`;
          }).join('')}
          <ellipse cx="120" cy="112" rx="90" ry="10" fill="rgba(200,225,215,.06)"/>
          ${[70, 150, 232].map((x, i) => `<circle cx="${x}" cy="${86 + i * 9}" r="1.6" fill="${a}" opacity=".8"/>`).join('')}
        </g>`;
      case 'mine':
        return `<g>
          <path d="M108 150 L108 96 Q160 58 212 96 L212 150 Z" fill="#060505"/>
          <path d="M108 96 Q160 58 212 96" stroke="#3d2f1d" stroke-width="3" fill="none"/>
          <rect x="104" y="94" width="7" height="56" fill="#332616"/>
          <rect x="209" y="94" width="7" height="56" fill="#332616"/>
          <rect x="112" y="106" width="96" height="4" fill="#2b2013"/>
          <circle cx="124" cy="100" r="3.4" fill="${a}"/>
          <circle cx="124" cy="100" r="9" fill="${a}" opacity=".18"/>
          <circle cx="196" cy="100" r="2.6" fill="${a}" opacity=".7"/>
          <path d="M146 150 L152 128 L158 150 Z" fill="${a}" opacity=".25"/>
          <path d="M172 150 L177 134 L182 150 Z" fill="${a}" opacity=".18"/>
        </g>`;
      case 'swamp':
        return `<g>
          <path d="M0 126 Q80 118 160 126 T320 124 L320 160 L0 160 Z" fill="#07100c"/>
          <path d="M0 132 Q70 126 140 132 T320 130" stroke="rgba(160,200,140,.10)" stroke-width="1" fill="none"/>
          ${[52, 96, 224, 268].map((x, i) => {
            const h = 26 + (i % 2) * 12;
            return `<path d="M${x} 128 L${x} ${128 - h} M${x} ${128 - h * 0.55} L${x - 9} ${128 - h * 0.8} M${x} ${128 - h * 0.7} L${x + 8} ${128 - h * 0.92}"
                      stroke="#0e1c15" stroke-width="2.4" fill="none" stroke-linecap="round"/>`;
          }).join('')}
          ${[40, 130, 250].map((x, i) => `<ellipse cx="${x}" cy="${120 + i * 3}" rx="22" ry="3" fill="rgba(180,220,170,.05)"/>`).join('')}
        </g>`;
      case 'desert':
        return `<g>
          <path d="M0 122 Q70 108 140 120 T320 116 L320 160 L0 160 Z" fill="#1a120b"/>
          <path d="M0 138 Q90 128 180 138 T320 134 L320 160 L0 160 Z" fill="#120c08"/>
          <path d="M196 122 L200 84 L206 84 L210 122 Z" fill="#0d0906"/>
          <path d="M200 84 L203 74 L206 84 Z" fill="${a}" opacity=".35"/>
          <path d="M40 96 q14 -4 28 0 M52 88 q10 -3 20 0" stroke="rgba(240,190,130,.10)" stroke-width="1.5" fill="none"/>
        </g>`;
      case 'frost':
        return `<g>
          ${[36, 78, 132, 196, 258, 292].map((x, i) => {
            const h = 26 + (i % 3) * 18;
            return `<path d="M${x} 124 L${x - 8} 124 L${x} ${124 - h} L${x + 8} 124 Z" fill="rgba(190,225,245,.14)" stroke="rgba(200,235,255,.18)" stroke-width=".8"/>`;
          }).join('')}
          <path d="M0 124 Q80 118 160 124 T320 122 L320 160 L0 160 Z" fill="#0a1118"/>
          <path d="M40 40 q60 -16 120 0" stroke="rgba(150,220,255,.16)" stroke-width="8" fill="none" filter="none"/>
        </g>`;
      case 'graveyard':
        return `<g>
          ${[44, 84, 148, 212, 268].map((x, i) => `
            <path d="M${x} 124 L${x} ${112 - (i % 2) * 6} q6 -8 12 0 L${x + 12} 124 Z" fill="#12111a"/>
            <rect x="${x + 4}" y="${108 - (i % 2) * 6}" width="4" height="1.6" fill="rgba(230,230,240,.18)"/>`).join('')}
          <path d="M240 124 L240 74 M240 92 L228 82 M240 100 L254 88" stroke="#0e0d15" stroke-width="3" fill="none"/>
          ${[110, 176].map((x, i) => `<circle cx="${x}" cy="${88 + i * 10}" r="2" fill="${a}" opacity=".8"/><circle cx="${x}" cy="${88 + i * 10}" r="7" fill="${a}" opacity=".12"/>`).join('')}
        </g>`;
      case 'lava':
        return `<g>
          <path d="M0 150 L64 96 L110 128 L150 108 L196 150 Z" fill="#0c0504"/>
          <path d="M196 150 L242 104 L292 138 L320 122 L320 160 L196 160 Z" fill="#0a0403"/>
          <path d="M64 96 q10 8 4 14 q14 -2 18 10" stroke="${a}" stroke-width="2" fill="none" opacity=".55"/>
          <path d="M150 112 q26 12 40 26 q14 12 30 8" stroke="${a}" stroke-width="3" fill="none" opacity=".5"/>
          <path d="M120 138 q40 -8 80 0 q30 6 60 -2" stroke="${a}" stroke-width="2" fill="none" opacity=".35"/>
          ${[90, 130, 210, 260].map((x, i) => `<circle cx="${x}" cy="${96 + i * 8}" r="1.4" fill="${a}" opacity=".7"/>`).join('')}
        </g>`;
      case 'temple':
        return `<g>
          ${[54, 88, 122, 198, 232, 266].map((x, i) => `
            <rect x="${x}" y="66" width="10" height="58" fill="rgba(235,228,205,.10)" stroke="rgba(255,240,200,.14)" stroke-width=".8"/>
            <rect x="${x - 4}" y="60" width="18" height="6" fill="rgba(235,228,205,.14)"/>`).join('')}
          <rect x="40" y="124" width="240" height="5" fill="rgba(235,228,205,.10)"/>
          <rect x="28" y="130" width="264" height="4" fill="rgba(235,228,205,.07)"/>
          <path d="M160 60 L160 130" stroke="${a}" stroke-width="10" opacity=".08"/>
          <path d="M160 58 L160 132" stroke="${a}" stroke-width="1.4" opacity=".35"/>
        </g>`;
      case 'void':
      default:
        return `<g>
          ${[[58, 96, 22, 8], [104, 78, 15, 6], [236, 104, 26, 9], [282, 84, 16, 6]].map(([x, y, w, h]) => `
            <path d="M${x} ${y} L${x + w} ${y - h} L${x + w + 6} ${y + h} L${x + 4} ${y + h + 4} Z" fill="#160f22" stroke="rgba(200,140,255,.18)" stroke-width=".8"/>`).join('')}
          <path d="M158 30 L150 70 L162 96 L152 130 L168 150" stroke="${a}" stroke-width="2.4" fill="none" opacity=".45"/>
          <path d="M158 30 L150 70 L162 96 L152 130 L168 150" stroke="${a}" stroke-width="7" fill="none" opacity=".10"/>
          ${[70, 120, 200, 258].map((x, i) => `<circle cx="${x}" cy="${40 + i * 12}" r="1.3" fill="#dcc8ff" opacity=".6"/>`).join('')}
        </g>`;
    }
  }

  function areaScene(areaId) {
    const [top, bottom, accent] = AREA_PALETTE[areaId] || AREA_PALETTE.village;
    const id = nid();
    return `
      <svg class="scene-svg" viewBox="0 0 320 160" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <defs>
          <linearGradient id="sk${id}" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="${top}"/>
            <stop offset="1" stop-color="${bottom}"/>
          </linearGradient>
          <radialGradient id="gl${id}">
            <stop offset="0" stop-color="${accent}" stop-opacity=".55"/>
            <stop offset="1" stop-color="${accent}" stop-opacity="0"/>
          </radialGradient>
          <linearGradient id="fg${id}" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="${bottom}" stop-opacity="0"/>
            <stop offset="1" stop-color="${bottom}" stop-opacity=".92"/>
          </linearGradient>
        </defs>
        <rect width="320" height="160" fill="url(#sk${id})"/>
        ${[[24, 18], [48, 34], [76, 12], [110, 26], [140, 16], [176, 30], [208, 14], [236, 26], [268, 18], [292, 32], [60, 44], [188, 44], [120, 40], [300, 12]]
          .map(([x, y], i) => `<circle cx="${x}" cy="${y}" r="${i % 3 === 0 ? 1.2 : 0.8}" fill="#ffffff" opacity="${(0.12 + (i % 4) * 0.06).toFixed(2)}"/>`).join('')}
        <circle cx="250" cy="40" r="38" fill="url(#gl${id})"/>
        <circle cx="250" cy="40" r="9" fill="${accent}" opacity=".5"/>
        ${ridge(98, 26, 'rgba(0,0,0,.22)', 1.1)}
        ${ridge(114, 18, 'rgba(0,0,0,.36)', 2.6)}
        ${sceneFeature(areaId, accent)}
        <ellipse cx="160" cy="118" rx="180" ry="12" fill="${accent}" opacity=".05"/>
        <rect y="120" width="320" height="40" fill="url(#fg${id})"/>
      </svg>`;
  }

  window.Sprite = { hero, monster, scene: areaScene };

  /* ==========================================================
     FX 主体
     ========================================================== */
  const MOODS = {
    village: ['214,177,116', '120,190,160', '176,123,255'],
    forest: ['122,214,156', '72,150,220', '96,226,178'],
    mine: ['228,170,86', '156,112,62', '255,196,116'],
    swamp: ['152,204,112', '92,122,192', '146,92,184'],
    desert: ['242,182,92', '224,122,62', '255,214,144'],
    frost: ['154,214,255', '94,144,232', '206,242,255'],
    graveyard: ['174,164,214', '112,102,172', '154,192,222'],
    lava: ['255,124,72', '204,62,52', '255,174,92'],
    temple: ['255,232,172', '192,212,255', '255,246,212'],
    void: ['204,124,255', '122,92,242', '255,112,202'],
  };

  let canvas = null;
  let ctx = null;
  let W = 0;
  let H = 0;
  let dpr = 1;
  let stars = [];
  let motes = [];
  let shooting = null;
  let nextShootAt = 0;
  let pointer = { x: 0.5, y: 0.5 };
  let smooth = { x: 0.5, y: 0.5 };
  let rafId = null;
  let started = false;
  let lastT = 0;
  let mood = 'village';
  let reduced = false;

  const rand = (a, b) => a + Math.random() * (b - a);

  // localStorage 在隐私模式下可能抛异常，统一兜底
  const store = {
    get(key) { try { return localStorage.getItem(key); } catch (e) { return null; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* 忽略 */ } },
  };

  function sizeCanvas() {
    if (!canvas) return;
    dpr = Math.min(2, window.devicePixelRatio || 1);
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = Math.floor(W * dpr);
    canvas.height = Math.floor(H * dpr);
    canvas.style.width = W + 'px';
    canvas.style.height = H + 'px';
    if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    buildStars();
  }

  function buildStars() {
    const count = Math.max(90, Math.min(260, Math.round((W * H) / 7600)));
    stars = Array.from({ length: count }, () => {
      const z = Math.random();
      return {
        x: Math.random() * W,
        y: Math.random() * H,
        r: 0.4 + z * 1.5,
        z: 0.25 + z * 0.95,
        phase: Math.random() * Math.PI * 2,
        speed: rand(0.4, 1.5),
        warm: Math.random() > 0.78,
      };
    });
    motes = Array.from({ length: 24 }, () => ({
      x: Math.random() * W,
      y: Math.random() * H,
      r: rand(0.7, 2.1),
      vy: rand(-0.22, -0.55),
      sway: rand(0.3, 1.1),
      phase: Math.random() * Math.PI * 2,
      warm: Math.random() > 0.45,
    }));
  }

  function spawnShoot(t) {
    shooting = {
      x: rand(W * 0.15, W * 0.9),
      y: rand(-40, H * 0.35),
      vx: rand(-7.5, -4.2),
      vy: rand(3.4, 6.2),
      life: 1,
      len: rand(90, 180),
    };
    nextShootAt = t + rand(5, 12);
  }

  function draw(t) {
    if (!ctx) return;
    ctx.clearRect(0, 0, W, H);
    smooth.x += (pointer.x - smooth.x) * 0.055;
    smooth.y += (pointer.y - smooth.y) * 0.055;
    const ox = (smooth.x - 0.5) * 2;
    const oy = (smooth.y - 0.5) * 2;

    ctx.globalCompositeOperation = 'lighter';

    for (const s of stars) {
      const tw = 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(t * s.speed + s.phase));
      const x = s.x + ox * 26 * s.z;
      const y = s.y + oy * 18 * s.z;
      const alpha = tw * (0.35 + s.z * 0.55);
      ctx.beginPath();
      ctx.fillStyle = s.warm
        ? `rgba(255, 236, 200, ${alpha})`
        : `rgba(198, 222, 255, ${alpha})`;
      ctx.arc(x, y, s.r, 0, Math.PI * 2);
      ctx.fill();
      if (s.r > 1.35) {
        ctx.beginPath();
        ctx.fillStyle = s.warm
          ? `rgba(255, 220, 160, ${alpha * 0.16})`
          : `rgba(160, 200, 255, ${alpha * 0.16})`;
        ctx.arc(x, y, s.r * 5.5, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    for (const m of motes) {
      m.y += m.vy;
      m.phase += 0.012;
      const x = m.x + Math.sin(m.phase) * m.sway * 12 + ox * 10;
      if (m.y < -20) {
        m.y = H + 20;
        m.x = Math.random() * W;
      }
      const a = 0.18 + 0.28 * (0.5 + 0.5 * Math.sin(m.phase * 1.7));
      ctx.beginPath();
      ctx.fillStyle = m.warm
        ? `rgba(255, 224, 168, ${a})`
        : `rgba(150, 205, 255, ${a})`;
      ctx.arc(x, m.y, m.r, 0, Math.PI * 2);
      ctx.fill();
    }

    if (!shooting && t > nextShootAt) spawnShoot(t);
    if (shooting) {
      const s = shooting;
      s.x += s.vx;
      s.y += s.vy;
      s.life -= 0.012;
      if (s.life <= 0 || s.y > H + 60 || s.x < -80) {
        shooting = null;
      } else {
        const nx = s.x - s.vx * (s.len / 10);
        const ny = s.y - s.vy * (s.len / 10);
        const grad = ctx.createLinearGradient(s.x, s.y, nx, ny);
        grad.addColorStop(0, `rgba(255,255,255,${0.85 * s.life})`);
        grad.addColorStop(0.4, `rgba(170,210,255,${0.35 * s.life})`);
        grad.addColorStop(1, 'rgba(120,160,255,0)');
        ctx.strokeStyle = grad;
        ctx.lineWidth = 1.8;
        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(nx, ny);
        ctx.stroke();
      }
    }

    ctx.globalCompositeOperation = 'source-over';
  }

  function loop(now) {
    rafId = requestAnimationFrame(loop);
    const t = now / 1000;
    const dt = Math.min(0.05, t - (lastT || t));
    lastT = t;
    if (reduced) return;
    draw(t + dt * 0);
  }

  function bindPointer() {
    window.addEventListener('pointermove', (e) => {
      pointer.x = e.clientX / window.innerWidth;
      pointer.y = e.clientY / window.innerHeight;
      document.body.style.setProperty('--px', ((pointer.x - 0.5) * 2).toFixed(3));
      document.body.style.setProperty('--py', ((pointer.y - 0.5) * 2).toFixed(3));
    }, { passive: true });
  }

  function bindTilt() {
    let current = null;
    let pending = false;
    let mx = 0;
    let my = 0;

    const reset = (el) => {
      if (!el) return;
      el.style.setProperty('--rx', '0deg');
      el.style.setProperty('--ry', '0deg');
    };

    document.addEventListener('pointermove', (e) => {
      const el = e.target && e.target.closest ? e.target.closest('[data-tilt]') : null;
      if (current && current !== el) reset(current);
      current = el;
      if (!el) return;
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) return;
      mx = (e.clientX - r.left) / r.width - 0.5;
      my = (e.clientY - r.top) / r.height - 0.5;
      if (pending) return;
      pending = true;
      requestAnimationFrame(() => {
        pending = false;
        if (!current) return;
        current.style.setProperty('--ry', (mx * 10).toFixed(2) + 'deg');
        current.style.setProperty('--rx', (-my * 8).toFixed(2) + 'deg');
      });
    }, { passive: true });

    document.addEventListener('pointerleave', () => {
      if (current) reset(current);
      current = null;
    });
  }

  function buildRunes() {
    const host = document.querySelector('.fx-runes');
    if (!host) return;
    const glyphs = ['✦', '✧', '◈', '❖', '✵', '⌘', '☾', '△', '○', '✶'];
    for (let i = 0; i < 14; i += 1) {
      const s = document.createElement('span');
      s.textContent = glyphs[i % glyphs.length];
      s.style.left = rand(2, 96).toFixed(1) + '%';
      s.style.top = rand(40, 100).toFixed(1) + '%';
      s.style.fontSize = rand(11, 24).toFixed(0) + 'px';
      s.style.animationDuration = rand(16, 34).toFixed(0) + 's';
      s.style.animationDelay = (-rand(0, 30)).toFixed(1) + 's';
      host.appendChild(s);
    }
  }

  function setMood(areaId) {
    const key = MOODS[areaId] ? areaId : 'village';
    if (key === mood && document.body.dataset.mood) return;
    mood = key;
    const [a, b, c] = MOODS[key];
    const root = document.body;
    root.dataset.mood = key;
    root.style.setProperty('--mood1', a);
    root.style.setProperty('--mood2', b);
    root.style.setProperty('--mood3', c);
  }

  /* ---------------- 场景切换 ---------------- */
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  let vtBusy = false;

  /**
   * 切场：优先使用浏览器原生 View Transitions API（零依赖、走合成层），
   * 不支持时退回一层轻量遮罩 + 内容入场动画。
   * kind: dive / encounter / travel / victory / defeat / soft
   */
  async function scene(kind, fn) {
    if (!kind || reduced) {
      fn();
      return;
    }

    if (!document.startViewTransition || vtBusy) {
      const ov = document.getElementById('fx-transition');
      if (!ov) {
        fn();
        return;
      }
      ov.hidden = false;
      ov.className = 'fx-transition t-' + kind;
      void ov.offsetWidth;
      ov.classList.add('play');
      await wait(kind === 'encounter' ? 140 : 100);
      fn();
      await wait(40);
      ov.classList.add('out');
      await wait(360);
      ov.hidden = true;
      ov.className = 'fx-transition';
      return;
    }

    vtBusy = true;
    const root = document.documentElement;
    root.dataset.vt = kind;
    try {
      const vt = document.startViewTransition(() => {
        fn();
      });
      await vt.finished;
    } catch (err) {
      // 过渡被中断时界面已更新，忽略即可
    } finally {
      delete root.dataset.vt;
      vtBusy = false;
    }
  }

  /* ---------------- 落地冲击 ---------------- */
  function impact() {
    const el = document.getElementById('game-screen');
    if (!el || reduced) return;
    el.classList.remove('impact');
    void el.offsetWidth;
    el.classList.add('impact');
    setTimeout(() => el.classList.remove('impact'), 440);
  }

  /* ---------------- 战斗演出 ---------------- */
  function replay(el, cls, ms) {
    if (!el) return;
    el.classList.remove(cls);
    void el.offsetWidth;
    el.classList.add(cls);
    setTimeout(() => el.classList.remove(cls), ms);
  }

  function enemySprite(index) {
    return document.querySelector(`.enemy-card[data-enemy="${index}"] .sprite`);
  }

  function playerSprite() {
    return document.querySelector('.player-strip .sprite');
  }

  function slash(index) {
    const card = document.querySelector(`.enemy-card[data-enemy="${index}"]`);
    if (!card) return;
    const el = document.createElement('div');
    el.className = 'slash';
    card.appendChild(el);
    setTimeout(() => el.remove(), 520);
  }

  function playBattle(events, action) {
    if (!events || !events.length) return;
    const ps = playerSprite();
    if (ps && (action === 'attack' || action === 'skill')) replay(ps, 'attacking', 560);
    if (ps && action === 'skill') replay(ps, 'casting', 720);

    events.forEach((ev, i) => {
      const delay = i * 95;
      setTimeout(() => {
        const target = ev.target != null ? enemySprite(ev.target) : ps;
        if (ev.miss || ev.dodge) {
          replay(target, 'casting', 400);
          return;
        }
        if (ev.dmg) {
          replay(target, 'hurt', 420);
          if (ev.target != null) slash(ev.target);
        }
        if (ev.heal) replay(target, 'casting', 520);
      }, delay);
    });
  }

  function burst(x, y, colors) {
    const palette = colors || ['#f2d49a', '#b07bff', '#5f92ea', '#ffe9b0'];
    for (let i = 0; i < 22; i += 1) {
      const dot = document.createElement('div');
      dot.className = 'fx-burst';
      dot.style.left = x + 'px';
      dot.style.top = y + 'px';
      dot.style.background = palette[i % palette.length];
      dot.style.boxShadow = `0 0 12px ${palette[i % palette.length]}`;
      document.body.appendChild(dot);
      const angle = (Math.PI * 2 * i) / 22 + rand(-0.2, 0.2);
      const dist = rand(60, 190);
      dot.animate([
        { transform: 'translate(-50%, -50%) scale(1)', opacity: 1 },
        {
          transform: `translate(calc(-50% + ${Math.cos(angle) * dist}px), calc(-50% + ${Math.sin(angle) * dist}px)) scale(0.2)`,
          opacity: 0,
        },
      ], { duration: rand(700, 1200), easing: 'cubic-bezier(.2,.8,.3,1)' })
        .onfinish = () => dot.remove();
    }
  }

  function levelUp() {
    const el = document.querySelector('.player-strip') || document.querySelector('.char-panel');
    const r = el ? el.getBoundingClientRect() : { left: window.innerWidth / 2, top: window.innerHeight / 2, width: 0, height: 0 };
    burst(r.left + r.width / 2, r.top + r.height / 2);
  }

  /* ---------------- 电影化开场 ---------------- */
  let cineTimers = [];
  let cineTyping = null;

  function clearCineTimers() {
    cineTimers.forEach((id) => clearTimeout(id));
    cineTimers = [];
    if (cineTyping) {
      clearInterval(cineTyping);
      cineTyping = null;
    }
  }

  function typeSubtitle(el, text) {
    const node = el.querySelector('.cine-sub');
    if (!node) return;
    node.innerHTML = '<span class="caret"></span>';
    let i = 0;
    cineTyping = setInterval(() => {
      i += 1;
      node.innerHTML = text.slice(0, i) + '<span class="caret"></span>';
      if (i >= text.length) {
        clearInterval(cineTyping);
        cineTyping = null;
        setTimeout(() => {
          const caret = node.querySelector('.caret');
          if (caret) caret.remove();
        }, 1400);
      }
    }, 46);
  }

  function cinematic(force) {
    const el = document.getElementById('cine');
    if (!el) return Promise.resolve();
    if (!force && store.get('cine-seen-v1') === '1') {
      el.hidden = true;
      return Promise.resolve();
    }

    return new Promise((resolve) => {
      el.hidden = false;
      el.classList.remove('out');
      el.querySelectorAll('.cine-title span').forEach((s) => {
        s.style.animation = 'none';
        void s.offsetWidth;
        s.style.animation = '';
      });

      const finish = () => {
        if (el.dataset.done === '1') return;
        el.dataset.done = '1';
        clearCineTimers();
        el.classList.add('out');
        store.set('cine-seen-v1', '1');
        setTimeout(() => {
          el.hidden = true;
          el.classList.remove('out');
          el.dataset.done = '0';
          resolve();
        }, 900);
        document.removeEventListener('keydown', onKey);
      };

      const onKey = (e) => {
        if (e.key === 'Escape' || e.key === ' ' || e.key === 'Enter') {
          e.preventDefault();
          finish();
        }
      };

      el.addEventListener('click', finish, { once: true });
      document.addEventListener('keydown', onKey);
      const skip = el.querySelector('.cine-skip');
      if (skip) skip.onclick = (e) => { e.stopPropagation(); finish(); };

      cineTimers.push(setTimeout(() => typeSubtitle(el, 'TEN REALMS · NINE KINGS'), 1900));
      cineTimers.push(setTimeout(finish, 6200));
    });
  }

  function chapter(areaName, heroText, holdMs) {
    const el = document.getElementById('chapter');
    if (!el) return;
    el.querySelector('.chapter-area').textContent = areaName || '';
    el.querySelector('.chapter-hero').textContent = heroText || '';
    el.hidden = false;
    el.classList.remove('out');
    const inner = el.querySelector('.chapter-inner');
    if (inner) {
      inner.style.animation = 'none';
      void inner.offsetWidth;
      inner.style.animation = '';
    }
    setTimeout(() => {
      el.classList.add('out');
      setTimeout(() => {
        el.hidden = true;
        el.classList.remove('out');
      }, 700);
    }, holdMs || 2100);
  }

  function enterScreen() {
    document.querySelectorAll('.screen').forEach((s) => {
      if (s.hidden) return;
      s.classList.remove('screen-enter');
      void s.offsetWidth;
      s.classList.add('screen-enter');
    });
  }

  function init() {
    reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    canvas = document.getElementById('fx-canvas');
    if (canvas && canvas.getContext) {
      ctx = canvas.getContext('2d');
      sizeCanvas();
      window.addEventListener('resize', sizeCanvas);
      if (!reduced && !started) {
        started = true;
        nextShootAt = performance.now() / 1000 + rand(2, 5);
        rafId = requestAnimationFrame(loop);
      }
    }
    buildRunes();
    bindPointer();
    bindTilt();
    setMood('village');
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        if (rafId) cancelAnimationFrame(rafId);
        rafId = null;
      } else if (started && !rafId && !reduced) {
        lastT = performance.now() / 1000;
        rafId = requestAnimationFrame(loop);
      }
    });
  }

  window.FX = {
    init, setMood, playBattle, burst, levelUp, scene, impact,
    cinematic, chapter, enterScreen, playEvents: playBattle,
  };
})();
