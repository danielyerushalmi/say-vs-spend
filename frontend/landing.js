/* Say vs. Spend landing page: brand picker + card, the depth game, the verdict reveal. */
(() => {
  'use strict'
  const { $, h, put, isNum, str, f1, f2, pct, money, link, tag, VERDICT, brandsOf, byRank, REDUCED, HAS_GSAP } = window.SS
  let RUN = null

  /* ---------------- hero: picker + card (works with or without the 3D) ---------------- */
  function renderPicker(run) {
    const box = $('#brand-picker'); box.textContent = ''
    byRank(brandsOf(run), 'rank_revenue').forEach(b => box.append(
      h('button', { class: 'chip', type: 'button', 'data-id': str(b.id), 'aria-pressed': 'false', onclick: () => select(b.id, true) }, str(b.name))))
  }
  function select(id, emit, quiet) {
    const b = brandsOf(RUN).find(x => str(x.id) === str(id)); if (!b) return
    document.querySelectorAll('#brand-picker .chip').forEach(c => c.setAttribute('aria-pressed', String(c.dataset.id === str(id))))
    const n = brandsOf(RUN).length
    const card = $('#berg-card'); card.textContent = ''
    put(card,
      h('p', { class: 'card-name' }, str(b.name), b.niche === true ? h('span', { class: 'flag' }, 'niche') : null),
      h('div', { class: 'card-split' },
        h('div', { class: 'said' }, h('p', { class: 'mono' }, 'Said ', tag('syn')),
          h('p', { class: 'big' }, f1(b.intent_mean), h('small', null, '/10 would buy')),
          h('p', { class: 'mono dim' }, `rank ${str(b.rank_intent)} of ${n}`)),
        h('div', { class: 'spent' }, h('p', { class: 'mono' }, 'Earned ', tag('meas')),
          h('p', { class: 'big' }, money(b.revenue_usd)),
          h('p', { class: 'mono dim' }, `rank ${str(b.rank_revenue)} of ${n} · `, link('10-K', b.filing_url)))))
    card.classList.toggle('show', !(quiet && matchMedia('(max-width: 900px)').matches))
    if (emit) window.dispatchEvent(new CustomEvent('ss:select', { detail: { id: b.id, from: 'ui' } }))
  }
  window.addEventListener('ss:select', e => { if (e.detail.from === '3d') select(e.detail.id, false) })

  /* ---------------- game: how deep does it go? ---------------- */
  const spearman = (a, b) => { const n = a.length; if (n < 2) return null; let d = 0; for (let i = 0; i < n; i++) d += (a[i] - b[i]) ** 2; return 1 - 6 * d / (n * (n * n - 1)) }
  const rankDesc = vals => { const idx = vals.map((v, i) => i).sort((a, b) => vals[b] - vals[a]); const r = []; idx.forEach((i, k) => { r[i] = k + 1 }); return r }
  function renderGame(run) {
    const tank = $('#tank'); tank.textContent = ''
    const bs = byRank(brandsOf(run), 'rank_intent')
    const maxI = Math.max(1, ...bs.map(b => b.intent_mean).filter(isNum))
    tank.style.setProperty('--cols', bs.length)
    bs.forEach(b => {
      const id = 'g-' + str(b.id)
      const col = h('div', { class: 'col', 'data-id': str(b.id) },
        h('div', { class: 'col-tip' }, h('span', { class: 'tri', style: `--h:${(isNum(b.intent_mean) ? b.intent_mean / maxI : 0) * 100}%` }),
          h('span', { class: 'tip-val mono' }, `${f1(b.intent_mean)}/10`)),
        h('div', { class: 'col-sea' },
          h('div', { class: 'guess-berg', style: '--g:30%' }),
          h('div', { class: 'truth-berg', style: '--t:0%' }),
          h('input', { class: 'depth', id, type: 'range', min: 0, max: 100, value: 30, 'aria-label': `How much money ${str(b.name)} makes, your guess`,
            oninput: e => { e.target.closest('.col').querySelector('.guess-berg').style.setProperty('--g', e.target.value + '%') } })),
        h('label', { class: 'col-name', for: id }, str(b.name)),
        h('span', { class: 'truth-val mono' }))
      tank.append(col)
    })
    $('#game-result').textContent = ''
    $('#tank').classList.remove('locked')
  }
  function lockGame() {
    const bs = brandsOf(RUN); if (!bs.length) return
    const maxRev = Math.max(...bs.map(b => b.revenue_usd).filter(isNum))
    const guesses = bs.map(b => +document.getElementById('g-' + str(b.id)).value)
    if (new Set(guesses).size < guesses.length) {
      const box = $('#game-result'); box.textContent = ''
      put(box, h('p', { class: 'result-h' }, 'Move every slider to a different depth first.'), h('p', { class: 'dim small' }, 'Two or more brands are at the same depth, so there is no ranking to score yet.'))
      return
    }
    const you = spearman(rankDesc(guesses), bs.map(b => b.rank_revenue))
    const crowd = spearman(bs.map(b => b.rank_intent), bs.map(b => b.rank_revenue))
    const tank = $('#tank'); tank.classList.add('locked')
    bs.forEach(b => {
      const col = tank.querySelector(`.col[data-id="${CSS.escape(str(b.id))}"]`); if (!col) return
      col.querySelector('.truth-berg').style.setProperty('--t', ((b.revenue_usd / maxRev) * 100).toFixed(1) + '%')
      col.querySelector('.truth-val').textContent = money(b.revenue_usd)
    })
    const win = isNum(you) && isNum(crowd) && you > crowd + 0.005, tie = isNum(you) && isNum(crowd) && Math.abs(you - crowd) <= 0.005
    const wiki = RUN.fame_wiki && RUN.fame_wiki.agreement && isNum(RUN.fame_wiki.agreement.spearman) ? RUN.fame_wiki.agreement.spearman : null
    const box = $('#game-result'); box.textContent = ''
    put(box,
      h('p', { class: 'result-h' }, tie ? 'Dead even with the AI crowd.' : win ? 'You read the money better than the AI crowd.' : 'The AI crowd read the money better than you.'),
      h('div', { class: 'trio' },
        h('div', null, h('p', { class: 'mono' }, 'YOU (your guess vs MEASURED)'), h('p', { class: 'big' + (win ? ' coral' : '') }, isNum(you) ? f2(you) : '–')),
        h('div', null, h('p', { class: 'mono' }, 'AI CROWD ', tag('syn')), h('p', { class: 'big' + (!win && !tie ? ' coral' : '') }, isNum(crowd) ? f2(crowd) : '–')),
        wiki != null ? h('div', null, h('p', { class: 'mono' }, 'WIKIPEDIA VIEWS ', tag('meas')), h('p', { class: 'big' }, f2(wiki)), h('p', { class: 'dim small' }, wikiNote(RUN))) : null),
      h('p', { class: 'mono dim' }, 'Score = how well the order matches real revenue. 1 = same order, 0 = no relation, −1 = reversed. The dashed outlines show the real depth.'))
    if (HAS_GSAP && !REDUCED) gsap.from('#game-result > *', { y: 16, opacity: 0, stagger: 0.08, duration: 0.5, ease: 'power3.out' })
  }

  function wikiNote(run) {
    const a = run.fame_wiki && run.fame_wiki.agreement; if (!a) return ''
    return [isNum(a.n_brands) ? `${a.n_brands} brands` : '', 'exploratory', a.could_be_chance === true ? 'could be chance' : ''].filter(Boolean).join(' · ')
  }

  /* ---------------- website report card ---------------- */
  const GRADES = ['A', 'A−', 'B+', 'B', 'B−', 'C+', 'C', 'C−', 'D']
  function histogram(id) {
    const counts = Array(10).fill(0)
    ;(Array.isArray(RUN.personas) ? RUN.personas : []).forEach(p => { const a = p.answers && p.answers[id]; if (a && isNum(a.say) && a.say >= 1 && a.say <= 10) counts[Math.round(a.say) - 1]++ })
    const max = Math.max(1, ...counts), total = counts.reduce((x, y) => x + y, 0)
    const svg = window.SS.s('svg', { viewBox: '0 0 100 34', class: 'hist', role: 'img', 'aria-label': `Ratings from 1 to 10: ${counts.join(', ')}` })
    counts.forEach((c, i) => svg.append(window.SS.s('rect', { x: i * 10 + 1, y: 30 - (c / max) * 28, width: 8, height: Math.max(0.5, (c / max) * 28), rx: 1, class: i >= 7 ? 'hi' : '' })))
    svg.append(window.SS.s('text', { x: 1, y: 34, class: 'hx' }, '1'), window.SS.s('text', { x: 92, y: 34, class: 'hx' }, '10'))
    return { svg, total, top: counts.slice(7).reduce((x, y) => x + y, 0) }
  }
  function renderGrades(run) {
    const grid = $('#grades-grid'); grid.textContent = ''
    const n = run.panel && isNum(run.panel.n_personas) ? run.panel.n_personas : null
    if (n) $('#grades-intro').textContent = `Graded by a Flashpoint crowd of ${n} AI shoppers. Each one answered: “How good do you think this brand's website is?” on a 1 to 10 scale.`
    const rr = run.repeat_run && Array.isArray(run.repeat_run.brands) ? run.repeat_run.brands : []
    const levels = [...new Set(brandsOf(run).map(x => +f1(x.say_mean)))].sort((x, y) => y - x)
    byRank(brandsOf(run), 'rank_say').forEach((b) => {
      const i = levels.indexOf(+f1(b.say_mean))
      const hs = histogram(str(b.id)), r2 = rr.find(x => str(x.id) === str(b.id))
      const same = r2 && isNum(r2.rank_say) ? Math.abs(r2.rank_say - b.rank_say) : null
      grid.append(h('button', { class: 'grade', type: 'button', role: 'listitem', 'data-id': str(b.id), onclick: () => { select(b.id, true); document.getElementById('hero').scrollIntoView({ behavior: REDUCED ? 'auto' : 'smooth' }) } },
        h('span', { class: 'letter' }, GRADES[Math.min(i, GRADES.length - 1)]),
        h('span', { class: 'g-name' }, str(b.name)),
        h('span', { class: 'g-score' }, h('b', null, f1(b.say_mean)), '/10 ', tag('syn')),
        hs.svg,
        h('span', { class: 'g-meta mono' }, hs.total ? `${Math.round(hs.top / hs.total * 100)}% gave it 8+ · ${hs.total} ratings` : ''),
        same != null ? h('span', { class: 'g-meta mono' }, same === 0 ? `✓ second crowd agreed: also #${b.rank_say}` : `≈ second crowd: #${r2.rank_say} (this crowd #${b.rank_say})`) : null))
    })
    const a = (run.agreement || {}).say
    const proof = $('#grades-proof'); proof.textContent = ''
    if (a && isNum(a.spearman)) put(proof, 'Grades are on a curve among these sites and show what the AI shoppers said, not a verified quality score. For a first check, the crowd\'s website ranking lined up with the companies\' real revenue at ', h('b', null, f2(a.spearman)), ' ', tag('vs'), a.could_be_chance ? ', though with 6 brands that could be chance.' : '.')
  }

  /* ---------------- verdict reveal ---------------- */
  function renderVerdict(run) {
    const tc = run.trust_card || {}, ag = run.agreement || {}, rr = run.repeat_run || null, fw = run.fame_wiki || null
    const v = VERDICT[tc.verdict] || ['·', str(tc.verdict) || 'No verdict yet']
    const body = $('#verdict-body'); body.textContent = ''
    const stat = (label, val, t, note) => h('div', { class: 'stat' }, h('p', { class: 'mono' }, label, ' ', t), h('p', { class: 'big' }, isNum(val) ? f2(val) : '–'), note ? h('p', { class: 'dim small' }, note) : null)
    const ci = ag.intent || {}
    const rrI = rr && rr.agreement && rr.agreement.intent ? rr.agreement.intent.spearman : null
    const stab = rr && rr.stability ? rr.stability.intent_rank_spearman_between_panels : null
    const wiki = fw && fw.agreement ? fw.agreement.spearman : null
    const db = brandsOf(run).find(b => str(b.id) === str(tc.draft_question_brand))
    const sayA = ag.say || {}, fameA = ag.fame || {}, st = rr && rr.stability ? rr.stability : {}
    const consist = [st.say_rank_spearman_between_panels, st.intent_rank_spearman_between_panels, st.fame_rank_spearman_between_panels].filter(isNum)
    put(body,
      h('div', { class: 'shines' },
        h('div', { class: 'use' }, h('p', { class: 'mono' }, 'Promising, not proven (exploratory; rule added 13:30, after results)'),
          h('ul', null,
            isNum(sayA.spearman) ? h('li', null, h('b', null, 'Grading websites. '), `The crowd's website ranking lined up with real revenue at ${f2(sayA.spearman)}` + (sayA.could_be_chance ? ', though with 6 brands that could still be chance.' : '.')) : null,
            isNum(fameA.spearman) ? h('li', null, h('b', null, 'Brand awareness. '), `Who had heard of each brand lined up with revenue at ${f2(fameA.spearman)}` + (fameA.could_be_chance ? ', also possibly chance.' : '.')) : null,
            consist.length ? h('li', null, h('b', null, 'Consistent answers. '), `A second crowd ranked the brands much the same way (${f2(Math.min(...consist))} to ${f2(Math.max(...consist))}). Consistent is not the same as correct: both crowds come from the same persona model.`, ' ', h('span', { class: 'tag tag-syn' }, 'SYNTHETIC vs SYNTHETIC')) : null)),
        h('div', { class: 'short' }, h('p', { class: 'mono' }, 'Ask real people: the say/do gap'),
          h('ul', null, h('li', null, h('b', null, 'Stated “would buy”. '), `It matched revenue at only ${f2(ci.spearman)}. That is the say/do gap this hackathon is about: what the AI shoppers say they will buy is not where the money goes. Our rule, written before any result, says check it with real people before betting money on it.`)))),
      h('p', { class: 'dim small' }, `${ag.n_brands || brandsOf(run).length} brands, so every number here could be chance. Exploratory, not a final answer.`),
      h('p', { class: 'mono', style: 'margin-top:10px' }, 'On the pre-registered “would buy” question:'),
      h('p', { class: 'verdict-word' }, h('span', { class: 'ico', 'aria-hidden': 'true' }, v[0]), ' ', v[1]),
      isNum(stab) && isNum(ci.spearman) ? h('p', { class: 'insight' },
        `Two AI crowds agreed with each other at ${f2(stab)}, and with real revenue at only ${f2(ci.spearman)}${isNum(rrI) ? ` and ${f2(rrI)}` : ''}. `, h('b', null, 'Consistent is not correct.')) : null,
      tc.reason ? h('p', { class: 'verdict-reason' }, str(tc.reason)) : null,
      h('div', { class: 'stats two' },
        stat('AI crowd vs real revenue', ci.spearman, tag('vs'), ci.could_be_chance ? 'could be chance' : ''),
        isNum(wiki) ? stat('Wikipedia views vs real revenue', wiki, tag('meas'), wikiNote(run)) : null),
      h('p', { class: 'dim small' }, '1 = same order as real revenue, 0 = no relation.'),
      tc.draft_question ? h('div', { class: 'draft' },
        h('p', { class: 'mono' }, 'Next step: ask real shoppers' + (db ? ` about ${str(db.name)}` : '')),
        h('p', { class: 'draft-q' }, '“' + str(tc.draft_question) + '”'),
        tc.draft_question_source ? h('p', { class: 'draft-src' }, (/claude|^model\b/i.test(str(tc.draft_question_source)) && !/no model/i.test(str(tc.draft_question_source))) ? tag('ai') : null, ' Written by: ' + str(tc.draft_question_source)) : null,
        h('p', { class: 'mono stop' }, str(tc.note || 'Drafted by the agent. Stopped for a human. Nothing was bought.'))) : null)
  }
  function initReveal() {
    const btn = $('#reveal'), body = $('#verdict-body')
    btn.addEventListener('click', () => {
      const open = body.hidden
      body.hidden = !open; btn.setAttribute('aria-expanded', String(open))
      btn.querySelector('.sonar-label').textContent = open ? 'Hide the verdict' : 'Reveal the verdict'
      btn.classList.toggle('pinged', open)
      if (open && HAS_GSAP && !REDUCED) gsap.from('#verdict-body > *', { y: 24, opacity: 0, stagger: 0.07, duration: 0.6, ease: 'power3.out' })
    })
  }

  /* ---------------- boot ---------------- */
  function render(run, path) {
    RUN = run; window.SS.run = run; window.SS.path = path
    window.SS.fillChrome(run, path)
    const n = run.panel && isNum(run.panel.n_personas) ? run.panel.n_personas : null
    if (n) $('#hero-lede').firstChild.textContent = `We ran ${n} of Flashpoint's AI shoppers on ${brandsOf(run).length} real online brands and checked them against SEC revenue. Above the water is what they `
    renderPicker(run); renderGrades(run); renderGame(run); renderVerdict(run)
    const fe = $('#feasible'), c = run.cost || {}
    if (fe) fe.textContent = `Runs on one Flashpoint panel + public SEC filings` + (isNum(c.estimate_usd) && c.estimate_usd > 0 ? ` · about $${c.estimate_usd.toFixed(2)} in Claude calls per run (estimate)` : '') + ` · every number labeled synthetic or measured`
    const hr = $('#hero-result'), ai = (run.agreement || {}).intent, tc = run.trust_card
    if (hr && ai && isNum(ai.spearman) && tc) {
      hr.textContent = ''
      const ag = run.agreement || {}
      const part = (label, a) => a && isNum(a.spearman) ? h('span', { class: 'hr-part' }, label + ' ', h('b', null, f2(a.spearman))) : null
      const nb = ag.n_brands || brandsOf(run).length
      const stb = run.repeat_run && run.repeat_run.stability ? [run.repeat_run.stability.say_rank_spearman_between_panels, run.repeat_run.stability.intent_rank_spearman_between_panels, run.repeat_run.stability.fame_rank_spearman_between_panels].filter(isNum) : []
      put(hr, stb.length ? h('span', { class: 'hr-part' }, 'Crowd vs crowd ', h('b', null, `${f2(Math.min(...stb))}–${f2(Math.max(...stb))}`)) : null, part('· Websites vs revenue', ag.say), part('· Awareness', ag.fame), part('· “Would buy” (pre-registered)', ag.intent), h('span', { class: 'mono hr-note' }, ` exploratory · ${nb} brands`))
      hr.setAttribute('href', '#grades')
      hr.hidden = false
    }
    const first = byRank(brandsOf(run), 'rank_revenue')[0]; if (first) select(first.id, true, true)
    window.dispatchEvent(new CustomEvent('ss:run', { detail: run }))
  }
  $('#game-lock').addEventListener('click', lockGame)
  $('#game-reset').addEventListener('click', () => renderGame(RUN))
  initReveal()
  window.SS.loadRun().then(({ run, path }) => {
    render(run, path)
    ;(document.fonts ? document.fonts.ready : Promise.resolve()).then(() => {
      window.SS.smoothScroll()
      if (!HAS_GSAP || REDUCED) return
      gsap.from('.hero-copy > *', { y: 30, opacity: 0, stagger: 0.1, duration: 1, ease: 'power4.out' })
      gsap.utils.toArray('.section-title, .step, .tank, .sonar-btn, .end-cta > *').forEach(el =>
        gsap.from(el, { y: 40, opacity: 0, duration: 0.9, ease: 'power3.out', scrollTrigger: { trigger: el, start: 'top 88%' } }))
    })
  }).catch(err => { const el = $('#load-error'); el.hidden = false; el.textContent = 'Could not load a run file (' + (err && err.message || 'error') + '). Start with: python3 frontend/server.py' })
})()
