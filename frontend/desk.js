/* Say vs. Spend: the desk. A conversation (left) + evidence (right: Evidence / Crowd / Verdict tabs).
   Answers come from the run file in the browser. If server.py has Claude available, free-text
   questions go to Claude (grounded in the same run file) and are labeled AI-generated. */
(() => {
  'use strict'
  const { $, h, s, put, isNum, str, f1, f2, pct, money, link, tag, VERDICT, brandsOf, byRank, REDUCED, HAS_GSAP } = window.SS
  let RUN = null
  const chat = { history: [], llm: false, busy: false }

  /* ---------------- tabs ---------------- */
  const TABS = ['ev', 'crowd', 'verdict', 'check']
  function showTab(name, focus) {
    TABS.forEach(t => {
      const tab = $('#t-' + t), panel = $('#p-' + t), on = t === name
      tab.setAttribute('aria-selected', String(on)); tab.tabIndex = on ? 0 : -1; panel.hidden = !on
      if (on && focus) tab.focus()
    })
  }
  TABS.forEach((t, i) => {
    const tab = $('#t-' + t)
    tab.addEventListener('click', () => showTab(t))
    tab.addEventListener('keydown', e => {
      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { e.preventDefault(); showTab(TABS[(i + (e.key === 'ArrowRight' ? 1 : TABS.length - 1)) % TABS.length], true) }
    })
  })

  /* ---------------- evidence cards ---------------- */
  function pushEvidence(...cards) {
    const box = $('#evidence'); box.querySelector('.ev-empty')?.remove()
    box.querySelectorAll('.ev.new').forEach(c => c.classList.remove('new'))
    cards.filter(Boolean).reverse().forEach(c => { c.classList.add('new'); box.prepend(c) })
    showTab('ev'); $('#p-ev').scrollTop = 0
    if (HAS_GSAP && !REDUCED) gsap.from(cards.filter(Boolean), { x: 24, opacity: 0, stagger: 0.06, duration: 0.45, ease: 'power3.out' })
  }
  const maxRev = () => Math.max(1, ...brandsOf(RUN).map(b => b.revenue_usd).filter(isNum))
  function brandCard(b) {
    const n = brandsOf(RUN).length
    return h('article', { class: 'ev' },
      h('h3', null, str(b.name), b.niche === true ? ' ' : null, b.niche === true ? h('span', { class: 'flag' }, 'niche') : null),
      b.description ? h('p', { class: 'dim small' }, str(b.description)) : null,
      h('div', { class: 'pair' },
        h('div', null, h('p', { class: 'mono' }, 'Said would buy ', tag('syn')), h('p', { class: 'big' }, f1(b.intent_mean), h('small', { class: 'dim' }, ' /10')),
          h('div', { class: 'depthbar say' }, h('i', { style: `width:${(isNum(b.intent_mean) ? b.intent_mean * 10 : 0)}%` })),
          h('p', { class: 'mono dim' }, `#${str(b.rank_intent)} of ${n}` + (isNum(b.buy_share) ? ` · ${pct(b.buy_share)} buy this kind of product` : ''))),
        h('div', null, h('p', { class: 'mono' }, 'Real revenue ', tag('meas')), h('p', { class: 'big sea' }, money(b.revenue_usd)),
          h('div', { class: 'depthbar spend' }, h('i', { style: `width:${(isNum(b.revenue_usd) ? b.revenue_usd / maxRev() * 100 : 0)}%` })),
          h('p', { class: 'mono dim' }, `#${str(b.rank_revenue)} of ${n} · ${str(b.fiscal_year)} `, link('10-K', b.filing_url)))),
      h('p', { class: 'mono dim' }, `Heard of it ${pct(b.aware_share)} · site rated ${f1(b.say_mean)}/10 `, tag('syn')))
  }
  function verdictCard() {
    const tc = RUN.trust_card || {}, v = VERDICT[tc.verdict] || ['·', str(tc.verdict) || 'No verdict']
    return h('article', { class: 'ev' }, h('p', { class: 'mono' }, 'How far to trust this AI crowd ', tag('vs')),
      h('h3', { class: 'coral' }, v[0] + ' ' + v[1]), tc.reason ? h('p', null, str(tc.reason)) : null, tc.metric ? h('p', { class: 'mono dim' }, str(tc.metric)) : null, tc.note ? h('p', { class: 'mono coral' }, str(tc.note)) : null)
  }
  function statCard(title, val, t, note) {
    return h('article', { class: 'ev' }, h('p', { class: 'mono' }, title, ' ', t), h('p', { class: 'big' }, isNum(val) ? f2(val) : '–'), note ? h('p', { class: 'dim small' }, note) : null)
  }

  /* ---------------- the conversation ---------------- */
  const log = () => $('#log')
  const scrollDown = () => { const l = log(); l.scrollTop = l.scrollHeight }
  function wave() { return s('svg', { class: 'wave', viewBox: '0 0 90 18', 'aria-label': 'thinking' }, s('path', { d: 'M0 9 Q 7.5 0 15 9 T 30 9 T 45 9 T 60 9 T 75 9 T 90 9' })) }
  function startTurn(q) {
    const turn = h('div', { class: 'turn' }, h('p', { class: 'q' }, q), h('p', { class: 'src' }, 'Reading the run file'), h('div', { class: 'a' }, wave()))
    log().append(turn); scrollDown()
    chat.history.push({ role: 'user', content: q })
    return turn
  }
  function finishTurn(turn, paras, source) {
    turn.querySelector('.src').textContent = source || 'From the run file'
    turn.querySelector('.src').classList.toggle('claude', /claude/i.test(source || ''))
    const a = turn.querySelector('.a'); a.textContent = ''
    paras.filter(Boolean).forEach(p => a.append(h('p', null, p)))
    chat.history.push({ role: 'assistant', content: paras.join(' ').slice(0, 2000) })
    if (HAS_GSAP && !REDUCED) gsap.from(a.children, { opacity: 0, y: 8, stagger: 0.08, duration: 0.4, ease: 'power3.out' })
    scrollDown()
  }

  function findBrand(q) { const ql = q.toLowerCase(); return brandsOf(RUN).find(b => { const n = str(b.name).toLowerCase(), id = str(b.id).toLowerCase(); return (n && ql.includes(n)) || (id.length > 2 && ql.includes(id)) || (n && ql.includes(n.split(/[\s&]+/)[0]) && n.split(/[\s&]+/)[0].length > 3) }) }

  function localAnswer(q) {
    const ql = q.toLowerCase(), b = findBrand(q), ag = RUN.agreement || {}, rr = RUN.repeat_run, fw = RUN.fame_wiki, tc = RUN.trust_card || {}
    const stab = rr && rr.stability ? rr.stability.intent_rank_spearman_between_panels : null
    if (b) {
      pushEvidence(brandCard(b))
      const over = b.rank_intent < b.rank_revenue, same = b.rank_intent === b.rank_revenue
      return [`The AI crowd ranked ${b.name} #${b.rank_intent} for "would buy" (${f1(b.intent_mean)}/10, synthetic). Real revenue ranks it #${b.rank_revenue} (${money(b.revenue_usd)}, measured).`,
        same ? 'Here the crowd and the money agree.' : over ? 'So the crowd overrated it compared with where the money goes.' : 'So the crowd underrated it compared with where the money goes.']
    }
    if (/second|again|repeat|stable|consisten|each other/.test(ql) && rr) {
      pushEvidence(statCard('Crowd 1 vs crowd 2', stab, tag('syn'), 'How similar the two AI crowds ranked the brands'), statCard('Second crowd vs revenue', rr.agreement && rr.agreement.intent && rr.agreement.intent.spearman, tag('vs')))
      return [`We ran a second crowd of ${rr.n_personas || 200} different AI shoppers from the same persona model. The two AI crowds ranked the brands almost the same way (${f2(stab)}), but neither matched real revenue (${f2(ag.intent && ag.intent.spearman)} and ${f2(rr.agreement && rr.agreement.intent && rr.agreement.intent.spearman)}).`,
        'So the crowd is consistent, just consistently off. Asking it twice does not make it right.']
    }
    if (/wiki|fame|famous|heard/.test(ql)) {
      const w = fw && fw.agreement ? fw.agreement.spearman : null
      pushEvidence(statCard('Fame (heard of it) vs revenue', ag.fame && ag.fame.spearman, tag('vs')), isNum(w) ? statCard('Wikipedia views vs revenue', w, tag('meas'), [fw.agreement.n_brands ? `${fw.agreement.n_brands} brands` : '', 'exploratory', fw.agreement.could_be_chance ? 'could be chance' : ''].filter(Boolean).join(' · ')) : null)
      return [`How many AI shoppers had heard of each brand tracked revenue at ${f2(ag.fame && ag.fame.spearman)}.` + (isNum(w) ? ` Plain Wikipedia page views tracked it at ${f2(w)}, far better than what the crowd said it would buy (${f2(ag.intent && ag.intent.spearman)}).` : '')]
    }
    if (/trust|verdict|believe|reliab|accura|how (close|good|well)|should i/.test(ql)) {
      pushEvidence(verdictCard(), statCard('AI crowd vs revenue', ag.intent && ag.intent.spearman, tag('vs'), ag.intent && ag.intent.could_be_chance ? 'Could be chance: the wobble range crosses zero' : ''))
      return [`The label is "${(VERDICT[tc.verdict] || ['', str(tc.verdict)])[1]}". ${str(tc.reason)}`, tc.draft_question ? `The agent drafted a question for real shoppers: "${tc.draft_question}" It stopped there for a human. Nothing was bought.` : '']
    }
    if (/overrat|underrat|miss|wrong|gap|surpris|worst|off/.test(ql)) {
      const gaps = (RUN.top_gaps || []).map(g => brandsOf(RUN).find(x => str(x.id) === str(g.brand_id))).filter(Boolean)
      pushEvidence(...gaps.map(brandCard))
      return gaps.length ? ['The biggest gaps between what the crowd said and where the money went:', gaps.map(x => `${x.name} (crowd #${x.rank_intent}, revenue #${x.rank_revenue})`).join('; ') + '.']
        : ['No gaps are listed in this run file yet.']
    }
    if (/rate (my|our)|my (website|site|store|shop|brand|business)|our (website|site|store)|focus group/.test(ql)) {
      showTab('check'); $('#grade-url').focus()
      return ['Paste your website link in the "Grade your website" box on the right. It loads your real page, grades it, and shows where it would sit next to the sites the Flashpoint crowd rated.']
    }
    if (/crowd|people|shopper|persona|who/.test(ql)) {
      showTab('crowd')
      return [`The Crowd tab shows all ${(RUN.personas || []).length || 'the'} AI shoppers. Each bubble is one AI shopper; the fill is how likely they said they would buy. Click one to read their answers.`]
    }
    if (/how|method|work|data|source|where|what is/.test(ql)) {
      const n = RUN.panel && RUN.panel.n_personas
      return [`${n || 'A panel of'} AI shoppers from one Flashpoint panel rated each brand: how good the website is, how likely they are to buy from it in the next 12 months, whether it is a kind of product they buy, and whether they had heard of it. Those are things the AI shoppers say.`,
        'The answer key is company revenue: each company\'s yearly revenue from its own SEC 10-K filing. Code compares the two rankings, and a rule written before any result sets the trust label.']
    }
    return ['I can answer from this study: name a brand, or ask "should I trust it?", "who did the crowd get wrong?", "what about a second crowd?", or "how does this work?".']
  }

  async function ask(q) {
    q = str(q).trim(); if (!q || chat.busy || !RUN) return
    $('#ask-input').value = ''
    chat.busy = true
    const turn = startTurn(q)
    await new Promise(r => setTimeout(r, REDUCED ? 0 : 420))
    if (chat.llm && !turn.dataset.chip) {
      try {
        const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 25000)
        const r = await fetch('/api/chat', { method: 'POST', signal: ctl.signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ messages: chat.history.slice(-12), run_path: window.SS.path }) })
        clearTimeout(timer)
        const j = await r.json()
        if (!r.ok || !j.reply) throw new Error(j.error || 'no reply')
        const b = findBrand(q); if (b) pushEvidence(brandCard(b))
        finishTurn(turn, str(j.reply).split(/\n{2,}/).map(p => p.trim()), 'Claude · AI-generated · grounded in this study')
        chat.busy = false; return
      } catch {
        chat.llm = false; setEngine()
      }
    }
    finishTurn(turn, localAnswer(q), chat.llm ? 'From the run file' : 'From the run file')
    chat.busy = false
  }

  function setEngine() {
    const e = $('#engine')
    e.textContent = chat.llm ? '● Claude is on · answers grounded in this study' : 'Answers from the run file'
    e.classList.toggle('on', chat.llm)
  }
  async function detectLLM() {
    try { const r = await fetch('/api/health', { cache: 'no-store' }); const j = await r.json(); chat.llm = !!(r.ok && j.ok && j.llm) } catch { chat.llm = false }
    setEngine()
  }

  function renderSuggest() {
    const box = $('#suggest'); box.textContent = ''
    const top = byRank(brandsOf(RUN), 'rank_intent')[0]
    ;['Can an AI crowd rate my website?', 'Should I trust the crowd?', top ? `What about ${top.name}?` : null, 'Who did the crowd get wrong?', RUN.repeat_run ? 'What about a second crowd?' : null, 'How does this work?']
      .filter(Boolean).forEach(t => box.append(h('button', { class: 'chip', type: 'button', onclick: () => ask(t) }, t)))
  }

  /* ---------------- crowd tab: bubbles ---------------- */
  const wall = { brand: null, filter: 'all', sel: null }
  const FILTERS = [['all', 'Everyone'], ['buy', 'Would buy (7+)'], ['nobuy', 'Would not (3 or less)'], ['yes', 'Buy this kind of product'], ['never', 'Never heard of it']]
  function personas() { return (Array.isArray(RUN.personas) ? RUN.personas : []).slice(0, 400).map((p, i) => ({ ...p, id: str(p.id ?? p.n ?? i + 1), num: i + 1 })) }
  function renderWall() {
    const bs = byRank(brandsOf(RUN), 'rank_intent'), sel = $('#wall-brand'), fil = $('#wall-filter'), box = $('#bubbles')
    if (!sel.options.length) { bs.forEach(b => sel.append(h('option', { value: str(b.id) }, str(b.name)))); FILTERS.forEach(([v, l]) => fil.append(h('option', { value: v }, l))) }
    if (!wall.brand) wall.brand = bs[0] ? str(bs[0].id) : null
    sel.value = wall.brand || ''; fil.value = wall.filter
    box.textContent = ''
    const ps = personas()
    if (!ps.length) { box.append(h('p', { class: 'dim' }, 'Per-shopper answers are not in this run file.')); return }
    const ok = a => wall.filter === 'all' || (a && (wall.filter === 'buy' ? a.intent >= 7 : wall.filter === 'nobuy' ? a.intent <= 3 : wall.filter === 'yes' ? a.buy === true : a.aware === false))
    ps.forEach(p => {
      const a = p.answers && p.answers[wall.brand]
      const fill = a && isNum(a.intent) ? Math.round(a.intent * 10) : 0
      box.append(h('button', { class: 'bub' + (a && a.aware === false ? ' never' : '') + (ok(a) ? '' : ' dim') + (wall.sel === p.id ? ' sel' : ''), type: 'button', role: 'listitem', style: `--f:${fill}%`,
        'aria-label': `Shopper ${p.num}` + (a && isNum(a.intent) ? `, would buy ${a.intent} of 10` : ''), onclick: e => { wall.sel = p.id; box.querySelectorAll('.bub.sel').forEach(x => x.classList.remove('sel')); e.currentTarget.classList.add('sel'); showPersona(p) } }))
    })
  }
  function showPersona(p) {
    const box = $('#persona'); box.textContent = ''
    put(box, h('p', { class: 'mono' }, 'AI shopper ', tag('syn')), h('h3', null, 'Shopper #' + p.num),
      h('div', { class: 'p-grid' }, byRank(brandsOf(RUN), 'rank_intent').map(b => {
        const a = p.answers && p.answers[str(b.id)]
        return h('div', { class: 'p-cell' + (str(b.id) === wall.brand ? ' cur' : '') }, h('p', null, str(b.name)),
          h('p', { class: 'mono dim' }, a ? `site ${a.say ?? '–'} · buy ${a.intent ?? '–'}${a.buy === true ? ' · buys this kind' : a.buy === false ? ' · not this kind' : ''}${a.aware === false ? ' · never heard' : ''}` : 'no answer'))
      })))
  }
  $('#wall-brand').addEventListener('change', e => { wall.brand = e.target.value; renderWall() })
  $('#wall-filter').addEventListener('change', e => { wall.filter = e.target.value; renderWall() })

  /* ---------------- verdict tab ---------------- */
  function renderVerdictPanel() {
    const box = $('#verdict-panel'); box.textContent = ''
    const ag = RUN.agreement || {}, rr = RUN.repeat_run, fw = RUN.fame_wiki, tc = RUN.trust_card || {}
    const db = brandsOf(RUN).find(b => str(b.id) === str(tc.draft_question_brand))
    put(box, verdictCard(),
      statCard('AI crowd (would buy) vs revenue', ag.intent && ag.intent.spearman, tag('vs'), ag.intent && ag.intent.could_be_chance ? 'Could be chance' : ''),
      rr ? statCard('Second crowd vs revenue', rr.agreement && rr.agreement.intent && rr.agreement.intent.spearman, tag('vs')) : null,
      rr && rr.stability ? statCard('Crowd 1 vs crowd 2', rr.stability.intent_rank_spearman_between_panels, tag('syn'), 'The crowds agree with each other') : null,
      fw && fw.agreement ? statCard('Wikipedia views vs revenue', fw.agreement.spearman, tag('meas'), [fw.agreement.n_brands ? `${fw.agreement.n_brands} brands` : '', 'exploratory', fw.agreement.could_be_chance ? 'could be chance' : ''].filter(Boolean).join(' · ')) : null,
      tc.rule ? h('article', { class: 'ev' }, h('p', { class: 'mono' }, 'Rule written before any result'), h('p', { class: 'small' }, str(tc.rule))) : null,
      tc.draft_question ? h('article', { class: 'ev' }, h('p', { class: 'mono' }, 'Drafted question for real shoppers' + (db ? ` · ${db.name}` : '')), h('p', null, '“' + str(tc.draft_question) + '”'),
        tc.draft_question_source ? h('p', { class: 'draft-src' }, (/claude|^model\b/i.test(str(tc.draft_question_source)) && !/no model/i.test(str(tc.draft_question_source))) ? tag('ai') : null, ' Written by: ' + str(tc.draft_question_source)) : null,
        h('p', { class: 'mono coral' }, str(tc.note || 'Drafted by the agent. Stopped for a human. Nothing was bought.'))) : null)
  }

  /* ---------------- check my crowd (say/trust_check.py via /api/trust-check) ---------------- */
  const EXAMPLES = [
    ['Rate my website', 'My online candle shop', 'Do people like my website design?'],
    ['Will they buy?', 'Hand-made soy candles', 'Will people buy my new pumpkin scent?'],
    ['What price?', 'Vintage sneakers', 'What price should I charge?'],
  ]
  function renderExamples() {
    const box = $('#check-examples'); box.textContent = ''
    EXAMPLES.forEach(([label, store, q]) => box.append(h('button', { class: 'chip', type: 'button', onclick: () => { $('#check-store').value = store; $('#check-q').value = q; runCheck() } }, label)))
  }
  async function runCheck() {
    const store = $('#check-store').value.trim(), question = $('#check-q').value.trim(), out = $('#check-result')
    if (!store || !question) { $(store ? '#check-q' : '#check-store').focus(); return }
    out.textContent = ''; out.append(h('p', { class: 'dim' }, 'Checking against the study…'))
    try {
      const post = (url, body) => fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      const [r, rp] = await Promise.all([post('/api/trust-check', { store, question, run_path: window.SS.path }), post('/api/predict', { store }).catch(() => null)])
      const j = await r.json()
      if (!r.ok) throw new Error(j.error || 'check failed')
      const pj = rp && rp.ok ? await rp.json() : null
      out.textContent = ''
      if (pj && isNum(pj.predicted_website_score)) out.append(predictCard(pj))
      const src = str(j.question_source), byModel = /^model/i.test(src)
      put(out,
        h('article', { class: 'ev new' },
          h('p', { class: 'mono' }, 'How far to trust an AI crowd for this ', j.evidence && j.evidence.label ? h('span', { class: 'tag tag-vs' }, str(j.evidence.label)) : h('span', { class: 'tag tag-est' }, 'NOT TESTED IN THIS STUDY')),
          h('h3', { class: 'coral' }, str(j.level_text)),
          j.level_source ? h('p', { class: 'mono dim' }, 'Label set by: ' + str(j.level_source)) : null,
          j.why ? h('p', null, str(j.why)) : null),
        j.real_question ? h('article', { class: 'ev' },
          h('p', { class: 'mono' }, 'Ask real people this ', byModel ? tag('ai') : h('span', { class: 'tag tag-est' }, 'CODE TEMPLATE')),
          h('p', { class: 'check-q' }, '“' + str(j.real_question) + '”')) : null,
        Array.isArray(j.check_steps) && j.check_steps.length ? h('article', { class: 'ev' }, h('p', { class: 'mono' }, 'A quick check with real people'),
          h('ol', { class: 'steps-list' }, j.check_steps.map(t => h('li', null, str(t))))) : null,
        Array.isArray(j.limits) && j.limits.length ? h('ul', { class: 'check-limits dim small' }, j.limits.map(t => h('li', null, str(t)))) : null,
        j.note ? h('p', { class: 'mono coral' }, str(j.note)) : null)
      if (HAS_GSAP && !REDUCED) gsap.from(out.children, { y: 14, opacity: 0, stagger: 0.07, duration: 0.4, ease: 'power3.out' })
    } catch (e) {
      out.textContent = ''
      out.append(h('p', { class: 'dim' }, 'The check runs on the local server. Start it with: python3 frontend/server.py (' + str(e.message) + ')'))
    }
  }
  function predictCard(p) {
    const [lo, hi] = Array.isArray(p.crowd_range_12_brands && p.crowd_range_12_brands.website) ? p.crowd_range_12_brands.website : [5, 8]
    const a = Math.min(lo, p.predicted_website_score) - 0.3, b = Math.max(hi, p.predicted_website_score) + 0.3
    const pos = v => ((v - a) / (b - a) * 100).toFixed(1) + '%'
    const err = p.typical_error && isNum(p.typical_error.website) ? p.typical_error.website : null
    const avgOnly = /^code: average/i.test(str(p.method && p.method.website))
    return h('article', { class: 'ev predict' },
      h('p', { class: 'mono' }, avgOnly ? 'AI-crowd average (no prediction ran) ' : 'Predicted AI-crowd rating of your website ', h('span', { class: 'tag tag-est' }, 'ESTIMATE')),
      h('p', { class: 'big' }, f1(p.predicted_website_score), h('small', { class: 'dim' }, ' /10'), err != null ? h('small', { class: 'dim' }, ` · typical error ${f1(err)}`) : null),
      h('div', { class: 'gauge', role: 'img', 'aria-label': `Predicted ${f1(p.predicted_website_score)}; real brands were rated ${f1(lo)} to ${f1(hi)}` },
        h('span', { class: 'g-range', style: `left:${pos(lo)};width:calc(${pos(hi)} - ${pos(lo)})` }),
        err != null ? h('span', { class: 'g-err', style: `left:${pos(p.predicted_website_score - err)};width:calc(${pos(p.predicted_website_score + err)} - ${pos(p.predicted_website_score - err)})` }) : null,
        h('span', { class: 'g-dot', style: `left:${pos(p.predicted_website_score)}` })),
      h('p', { class: 'mono dim' }, `Real brands the crowd rated: ${f1(lo)} to ${f1(hi)}`),
      avgOnly ? h('p', null, `A typical store gets about ${f1(p.predicted_website_score)}/10 from this crowd${err != null ? ` (typical error ${f1(err)})` : ''}. It rated 12 real brands' websites (our 6 plus 6 that failed the online-first rule) between ${f1(lo)} and ${f1(hi)}, so it rates almost every site about the same.`) : p.headline ? h('p', null, str(p.headline)) : null,
      isNum(p.predicted_buy_score) ? h('p', { class: 'mono dim' }, `${avgOnly && /average/i.test(str(p.method && p.method.buy)) ? 'Average' : 'Predicted'} "likely to buy": ${f1(p.predicted_buy_score)}/10` + (p.typical_error && isNum(p.typical_error.buy) ? ` · typical error ${f1(p.typical_error.buy)}` : '')) : null,
      Array.isArray(p.why) && p.why.length ? h('p', { class: 'dim small' }, p.why.map(str).join(' ')) : null,
      p.label ? h('p', { class: 'dim small' }, str(p.label)) : null,
      p.reality_note ? h('p', { class: 'small' }, str(p.reality_note)) : null,
      p.note ? h('p', { class: 'mono dim' }, str(p.note)) : null)
  }
  $('#check-form').addEventListener('submit', e => { e.preventDefault(); runCheck() })

  /* ---------------- grade a real website from a pasted link (/api/grade-site) ---------------- */
  async function gradeSite() {
    const url = $('#grade-url').value.trim(), out = $('#grade-result')
    if (!url) { $('#grade-url').focus(); return }
    out.textContent = ''; out.append(h('p', { class: 'dim' }, 'Loading your page and grading it…'))
    try {
      const r = await fetch('/api/grade-site', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) })
      const j = await r.json()
      if (!r.ok) throw new Error(j.error || 'could not grade that site')
      out.textContent = ''
      const range = Array.isArray(j.crowd_range) ? j.crowd_range : null
      const ai = j.ai_read && isNum(j.ai_read.score) ? j.ai_read : null
      put(out,
        h('article', { class: 'ev new' },
          h('p', { class: 'mono' }, 'Site check of your real page ', h('span', { class: 'tag tag-est' }, 'ESTIMATE')),
          h('h3', null, str(j.title) || str(j.url)),
          h('p', { class: 'mono dim' }, str(j.url) + ` · loaded in ${f1(j.load_seconds)}s · about ${str(j.words)} words`),
          h('p', { class: 'big' }, f1(j.site_check_score), h('small', { class: 'dim' }, ' /10 on 10 checks')),
          h('ul', { class: 'site-checks' }, (j.checks || []).map(c => h('li', { class: c.ok ? 'ok' : 'no' },
            h('span', { 'aria-hidden': 'true' }, c.ok ? '✓ ' : '✗ '), h('b', null, str(c.name)), c.ok ? h('span', { class: 'sr-only' }, ' passed') : h('span', { class: 'dim' }, ' · ' + str(c.fix))))),
          h('p', { class: 'dim small' }, str(j.site_check_label))),
        ai ? h('article', { class: 'ev' },
          h('p', { class: 'mono' }, "Claude's read of your page ", tag('ai')),
          h('p', { class: 'big' }, f1(ai.score), h('small', { class: 'dim' }, ' /10')),
          ai.impression ? h('p', null, str(ai.impression)) : null,
          Array.isArray(ai.fixes) && ai.fixes.length ? h('ol', { class: 'steps-list' }, ai.fixes.map(t => h('li', null, str(t)))) : null,
          h('p', { class: 'dim small' }, str(ai.label))) : j.ai_read && j.ai_read.error ? h('p', { class: 'dim small' }, str(j.ai_read.error)) : null,
        range ? h('article', { class: 'ev' },
          h('p', { class: 'mono' }, 'Next to the Flashpoint crowd ', tag('syn')),
          h('p', null, `Our crowd of AI shoppers rated 12 real online brands' websites (our 6 plus 6 that failed the online-first rule) between ${f1(range[0])} and ${f1(range[1])} out of 10. They rate most sites about the same, so the fixes above are the part to act on.`)) : null)
      if (HAS_GSAP && !REDUCED) gsap.from(out.children, { y: 14, opacity: 0, stagger: 0.07, duration: 0.4, ease: 'power3.out' })
    } catch (e) {
      out.textContent = ''; out.append(h('p', { class: 'dim' }, str(e.message)))
    }
  }
  $('#grade-form').addEventListener('submit', e => { e.preventDefault(); gradeSite() })

  /* ---------------- boot ---------------- */
  $('#ask').addEventListener('submit', e => { e.preventDefault(); ask($('#ask-input').value) })
  window.SS.loadRun().then(({ run, path }) => {
    RUN = run; window.SS.run = run; window.SS.path = path
    window.SS.fillChrome(run, path)
    renderSuggest(); renderWall(); renderVerdictPanel(); renderExamples()
    if (location.hash.startsWith('#check')) showTab('check')
    detectLLM()
    const q = new URLSearchParams(location.search).get('q'); if (q) ask(q)
  }).catch(err => { const el = $('#load-error'); el.hidden = false; el.textContent = 'Could not load a run file (' + (err && err.message || 'error') + '). Start with: python3 frontend/server.py' })
})()
