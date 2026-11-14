/* Say vs. Spend: shared helpers for both pages (landing + desk).
   Loads the run file, fills the badge/banner/footer, exposes helpers on window.SS.
   All run-file text is inserted as text, never as HTML. */
(() => {
  'use strict'
  const SVGNS = 'http://www.w3.org/2000/svg'
  const $ = q => document.querySelector(q)
  function attrs(el, a) {
    if (!a) return el
    for (const [k, v] of Object.entries(a)) {
      if (v == null || v === false) continue
      if (k.startsWith('on')) el.addEventListener(k.slice(2), v)
      else el.setAttribute(k, v === true ? '' : String(v))
    }
    return el
  }
  function kids(el, list) {
    for (const k of list.flat(Infinity)) { if (k == null || k === false) continue; el.append(k instanceof Node ? k : document.createTextNode(String(k))) }
    return el
  }
  const h = (t, a, ...c) => kids(attrs(document.createElement(t), a), c)
  const s = (t, a, ...c) => kids(attrs(document.createElementNS(SVGNS, t), a), c)
  const put = (el, ...c) => kids(el, c)
  const isNum = v => typeof v === 'number' && Number.isFinite(v)
  const str = v => (v == null ? '' : String(v))
  const f1 = v => (isNum(v) ? v.toFixed(1) : '–')
  const f2 = v => (isNum(v) ? v.toFixed(2) : '–')
  const pct = v => (isNum(v) ? Math.round(v * 100) + '%' : '–')
  const money = v => !isNum(v) ? '–' : v >= 1e9 ? '$' + (v / 1e9).toFixed(2) + 'B' : v >= 1e6 ? '$' + Math.round(v / 1e6) + 'M' : '$' + Math.round(v).toLocaleString('en-US')
  function safeUrl(u) { if (typeof u !== 'string') return null; try { const x = new URL(u, location.href); return /^https?:$/.test(x.protocol) ? x.href : null } catch { return null } }
  const link = (label, u) => { const href = safeUrl(u); return href ? h('a', { href, target: '_blank', rel: 'noopener' }, label) : null }
  const fmtTime = (iso, sec) => { const d = new Date(iso); return isNaN(d) ? str(iso) : d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', second: sec ? '2-digit' : undefined, timeZone: 'America/New_York' }) }
  function tag(kind) {
    const t = { syn: ['tag tag-syn', 'SYNTHETIC'], meas: ['tag tag-meas', 'MEASURED'], est: ['tag tag-est', 'ESTIMATE'],
      vs: ['tag tag-vs', 'SYNTHETIC vs MEASURED'], ai: ['tag tag-ai', 'AI-GENERATED'] }[kind]
    return h('span', { class: t[0] }, t[1])
  }
  const VERDICT = { trust: ['✓', 'Trust it'], verify: ['?', 'Double-check it'], ask_real_people: ['→', 'Ask real people'] }
  const brandsOf = run => (run && Array.isArray(run.brands) ? run.brands : [])
  const byRank = (bs, key) => [...bs].sort((a, b) => (a[key] || 99) - (b[key] || 99))
  const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches
  const HAS_GSAP = typeof window.gsap !== 'undefined'

  async function fetchJson(path) {
    const r = await fetch(path + (path.includes('?') ? '&' : '?') + 't=' + Date.now(), { cache: 'no-store' })
    if (!r.ok) throw new Error(path + ' returned ' + r.status)
    return r.json()
  }
  async function loadRun() {
    const q = new URLSearchParams(location.search).get('run')
    const cands = q && /^runs\/[\w.-]+\.json$/.test(q) ? [q] : ['runs/say_latest.json', 'runs/sample.json']
    let last
    for (const p of cands) { try { return { run: await fetchJson(p), path: p } } catch (e) { last = e } }
    throw last
  }

  function fillChrome(run, path) {
    const mode = str(run.mode)
    const ban = $('#sample-banner'); if (ban) ban.hidden = mode !== 'sample'
    const b = $('#run-badge')
    if (b) {
      const n = run.panel && isNum(run.panel.n_personas) ? `${run.panel.n_personas} AI shoppers · ` : ''
      b.textContent = n + (mode === 'recorded' ? `recorded ${fmtTime(run.recorded_at)}` : mode === 'live' ? 'live' : mode === 'sample' ? 'sample data' : mode)
    }
    const ul = $('#limits')
    if (ul) { ul.textContent = ''; (Array.isArray(run.limits) ? run.limits : []).forEach(l => ul.append(h('li', null, str(l)))) }
    const note = $('#panel-note')
    if (note) {
      const p = run.panel || {}, c = run.cost || {}
      note.textContent = [p.persona_model_note, c.flashpoint_note].filter(Boolean).map(str).join(' · ')
    }
    const rf = $('#run-file'); if (rf) rf.textContent = 'Run file: ' + path
  }

  function smoothScroll() {
    if (REDUCED || !window.Lenis || !HAS_GSAP) return null
    gsap.registerPlugin(ScrollTrigger)
    const lenis = new Lenis({ lerp: 0.1, smoothWheel: true, prevent: n => !!(n.closest && n.closest('[data-lenis-prevent]')) })
    lenis.on('scroll', ScrollTrigger.update)
    gsap.ticker.add(t => lenis.raf(t * 1000)); gsap.ticker.lagSmoothing(0)
    return lenis
  }

  window.SS = { $, h, s, put, kids, isNum, str, f1, f2, pct, money, safeUrl, link, fmtTime, tag, VERDICT, brandsOf, byRank, REDUCED, HAS_GSAP, loadRun, fillChrome, smoothScroll, run: null, path: null }
})()
