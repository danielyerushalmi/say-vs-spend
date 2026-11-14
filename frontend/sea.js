/* Hero: one iceberg per brand, built from the run file.
   Tip above the water  = how likely the AI crowd says it would buy (intent_mean, SYNTHETIC), to scale.
   Mass below the water = real yearly revenue (revenue_usd, MEASURED), to scale; a depth ruler shows the dollars.
   Mouse/pen: drag to turn the sea. Everyone: tap/click an iceberg (or use the brand buttons).
   Isolated module: if WebGL or the CDN fails, the page and its brand buttons still work. */
import * as THREE from 'three'

const hero = document.getElementById('hero')
const canvas = document.getElementById('sea')
const labelsEl = document.getElementById('berg-labels')
const rulerEl = document.getElementById('depth-ruler')
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches
let DEPTH_MAX = 5.2     // world units for the biggest revenue (fitted to the screen in resize)
const TIP_PER_POINT = 0.42  // world units per point of "would buy" (out of 10)

try { start() } catch (e) { console.warn('3D sea disabled:', e); hero.classList.add('no-3d') }

function start() {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true })
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  const scene = new THREE.Scene()
  scene.fog = new THREE.Fog(0x123c5a, 14, 34)
  const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100)
  const camBase = new THREE.Vector3(0, 2.6, 17)
  camera.position.copy(camBase)
  const lookAt = new THREE.Vector3(0, 2.0, 0)

  scene.add(new THREE.HemisphereLight(0xe6f4ff, 0x0b2f4d, 1.6))
  const sun = new THREE.DirectionalLight(0xffffff, 2.1); sun.position.set(-6, 10, 8); scene.add(sun)

  // the water surface: tints everything below it, with a gentle swell
  const waterGeo = new THREE.PlaneGeometry(80, 40, 80, 40)
  const water = new THREE.Mesh(waterGeo, new THREE.MeshPhysicalMaterial({ color: 0x1d5f8a, transparent: true, opacity: 0.55, roughness: 0.12, side: THREE.DoubleSide, depthWrite: false, flatShading: true }))
  water.rotation.x = -Math.PI / 2
  scene.add(water)
  const wpos = waterGeo.attributes.position, wbase = Float32Array.from(wpos.array)

  const sea = new THREE.Group(); scene.add(sea)
  const bergs = []
  const highlight = new THREE.Color(0x8fd3ff)

  function rng(seed) { let x = seed >>> 0 || 1; return () => ((x = Math.imul(x ^ (x >>> 15), 2246822507) ^ Math.imul(x ^ (x >>> 13), 3266489909)) >>> 0) / 4294967296 }
  function hash(t) { let x = 2166136261; for (const c of String(t)) { x ^= c.charCodeAt(0); x = Math.imul(x, 16777619) } return x >>> 0 }
  function jitter(geo, amt, r) {
    const p = geo.attributes.position, v = new THREE.Vector3(), seen = new Map()
    for (let i = 0; i < p.count; i++) {
      v.fromBufferAttribute(p, i)
      const k = `${v.x.toFixed(3)},${v.y.toFixed(3)},${v.z.toFixed(3)}`
      if (!seen.has(k)) seen.set(k, [(r() - 0.5) * amt, (r() - 0.5) * amt * 0.6, (r() - 0.5) * amt])
      const d = seen.get(k); p.setXYZ(i, v.x + d[0], v.y + d[1], v.z + d[2])
    }
    geo.computeVertexNormals(); return geo
  }

  let maxRev = 1, lastRun = null
  const portrait = () => camera.aspect < 0.9
  let lastSpacing = 0
  const wantSpacing = n => { const halfW = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * camBase.z * camera.aspect; return portrait() ? 2.6 : Math.min(2.8, (halfW * 2 * 0.62) / Math.max(1, n - 1)) }
  function build(run, keepRisen) {
    lastRun = run
    for (const b of bergs) { sea.remove(b.group); b.label.remove() }
    bergs.length = 0
    const brands = (run && Array.isArray(run.brands) ? run.brands : []).filter(b => typeof b.revenue_usd === 'number')
    if (!brands.length) return
    maxRev = Math.max(...brands.map(b => b.revenue_usd))
    const n = brands.length
    const spacing = lastSpacing = wantSpacing(n)
    const risen = REDUCED || !!keepRisen
    brands.forEach((b, i) => {
      const r = rng(hash(b.id || b.name))
      const tipH = Math.max(0.25, (typeof b.intent_mean === 'number' ? b.intent_mean : 0) * TIP_PER_POINT)
      const depth = Math.max(0.3, (b.revenue_usd / maxRev) * DEPTH_MAX)
      const width = 0.55 + 0.35 * Math.sqrt(b.revenue_usd / maxRev)
      const g = new THREE.Group()
      const tipGeo = jitter(new THREE.ConeGeometry(width * 0.9, tipH, 7, 3), 0.22, r); tipGeo.translate(0, tipH / 2, 0)
      const tip = new THREE.Mesh(tipGeo, new THREE.MeshPhysicalMaterial({ color: 0xf5fbff, roughness: 0.3, clearcoat: 0.4, flatShading: true, transparent: true }))
      const body = new THREE.Mesh(jitter(new THREE.IcosahedronGeometry(1, 1), 0.35, r),
        new THREE.MeshPhysicalMaterial({ color: 0x9fd2ea, roughness: 0.45, flatShading: true, transparent: true, opacity: 0.92 }))
      body.scale.set(width * 1.6, depth / 2, width * 1.4); body.position.y = -depth / 2 + 0.05
      tip.userData.id = body.userData.id = b.id
      g.add(tip, body)
      g.position.set((i - (n - 1) / 2) * spacing, risen ? 0 : -9, (r() - 0.5) * 1.6)
      g.rotation.y = r() * Math.PI
      sea.add(g)
      const label = document.createElement('span'); label.className = 'berg-label'; label.textContent = b.name; labelsEl.append(label)
      bergs.push({ id: b.id, group: g, tip, body, tipH, phase: r() * Math.PI * 2, label, rise: risen ? 1 : 0, delay: i * 0.12, fade: 1 })
    })
    if (selected) select(selected, false)   // a rebuild keeps the current pick
    drawRuler()
  }

  let selected = null, hovered = null
  function select(id, emit) {
    selected = id
    for (const b of bergs) {
      const on = b.id === id
      b.tip.material.emissive = on ? highlight : new THREE.Color(0)
      b.tip.material.emissiveIntensity = on ? 0.45 : 0
      b.label.classList.toggle('on', on)
    }
    if (emit) window.dispatchEvent(new CustomEvent('ss:select', { detail: { id, from: '3d' } }))
  }
  window.addEventListener('ss:select', e => { if (e.detail.from !== '3d') select(e.detail.id, false) })

  /* depth ruler: dollar ticks placed at the same world depth the icebergs use */
  const fmt = v => v >= 1e9 ? '$' + (v / 1e9).toFixed(v % 1e9 ? 1 : 0) + 'B' : '$' + Math.round(v / 1e6) + 'M'
  function drawRuler() {
    if (!rulerEl || !bergs.length) return
    rulerEl.textContent = ''
    const step = maxRev > 2e9 ? 5e8 : maxRev > 8e8 ? 2.5e8 : 1e8
    const h = hero.clientHeight, p = new THREE.Vector3()
    const ui = document.getElementById('brand-picker'), hr = hero.getBoundingClientRect()
    const limit = ui ? Math.min(h - 24, ui.getBoundingClientRect().top - hr.top - 14) : h - 24
    const top = new THREE.Vector3(0, 0, 0).project(camera)
    const y0 = (1 - (top.y + 1) / 2) * h
    for (let v = step; v <= maxRev * 1.001; v += step) {
      p.set(0, -(v / maxRev) * DEPTH_MAX, 0).project(camera)
      const y = (1 - (p.y + 1) / 2) * h
      if (y > limit) break
      const t = document.createElement('span'); t.className = 'tick'; t.style.top = y.toFixed(1) + 'px'; t.textContent = fmt(v); rulerEl.append(t)
    }
    const cap = document.createElement('span'); cap.className = 'ruler-cap'; cap.style.top = (y0 - 22).toFixed(1) + 'px'
    cap.textContent = 'Depth = yearly revenue, to scale'; rulerEl.append(cap)
  }

  function fitDepth() {
    // the world depth (at z = 0) that lands ~84% down the screen, so the biggest berg ends above the brand buttons
    const r = new THREE.Raycaster(); r.setFromCamera(new THREE.Vector2(0, 1 - 2 * 0.86), camera)
    const hit = new THREE.Vector3(); if (!r.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 0, 1), 0), hit)) return
    const d = Math.max(1.5, Math.min(6, -hit.y / 1.18))
    if (Math.abs(d - DEPTH_MAX) > 0.05) { DEPTH_MAX = d; if (lastRun) build(lastRun, bergs.length && bergs.every(b => b.rise >= 1)) }
  }
  function resize() {
    const w = hero.clientWidth, h = hero.clientHeight
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix()
    sea.position.x = 0   // icebergs centered on every screen
    // wide screens: camera near the waterline so the hidden mass gets real height; phones keep the higher view
    camBase.y = w / h < 0.9 ? 2.6 : 0.95
    lookAt.y = w / h < 0.9 ? 2.9 : 1.05
    camera.position.copy(camBase); camera.lookAt(lookAt)
    const horizon = new THREE.Vector3(0, 0, -30).project(camera)
    hero.style.setProperty('--wl', ((1 - (horizon.y + 1) / 2) * 100).toFixed(2) + '%')
    fitDepth()
    if (lastRun && bergs.length && Math.abs(wantSpacing(bergs.length) - lastSpacing) > 0.05) build(lastRun, bergs.every(b => b.rise >= 1))
    drawRuler()
  }
  resize()
  new ResizeObserver(resize).observe(hero)

  /* input: drag to turn (mouse/pen), hover to preview, tap to pick (everyone) */
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2()
  let drag = null, spin = 0, vel = 0, px = 0, py = 0
  const meshes = () => bergs.flatMap(b => [b.tip, b.body])
  const toNdc = e => { const r = canvas.getBoundingClientRect(); ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1) }
  canvas.addEventListener('pointerdown', e => { drag = { x: e.clientX, moved: 0, type: e.pointerType } })
  window.addEventListener('pointermove', e => {
    const r = hero.getBoundingClientRect()
    px = ((e.clientX - r.left) / r.width - 0.5); py = ((e.clientY - r.top) / r.height - 0.5)
    if (drag && drag.type !== 'touch') { const dx = e.clientX - drag.x; drag.x = e.clientX; drag.moved += Math.abs(dx); spin += dx * 0.0035; vel = dx * 0.002 }
    if (!drag && e.target === canvas) {
      toNdc(e); ray.setFromCamera(ndc, camera)
      const hit = ray.intersectObjects(meshes())[0]
      hovered = hit ? hit.object.userData.id : null
      canvas.style.cursor = hit ? 'pointer' : 'grab'
    } else if (e.target !== canvas) hovered = null
    for (const b of bergs) b.label.classList.toggle('hover', b.id === hovered && b.id !== selected)
  })
  window.addEventListener('pointerup', e => {
    if (drag && drag.moved < 6 && e.target === canvas) {
      toNdc(e); ray.setFromCamera(ndc, camera)
      const hit = ray.intersectObjects(meshes())[0]
      if (hit) select(hit.object.userData.id, true)
    }
    drag = null
  })

  let visible = true
  new IntersectionObserver(([en]) => { visible = en.isIntersecting }).observe(hero)

  const tmp = new THREE.Vector3()
  const copyEl = document.querySelector('.hero-copy')
  let copyCache = null, copyAt = 0
  const copyRect = () => {   // hero-copy box relative to the hero, refreshed a few times a second
    const now = performance.now(); if (copyCache && now - copyAt < 300) return copyCache
    if (!copyEl) return null
    const a = copyEl.getBoundingClientRect(), hr = hero.getBoundingClientRect()
    copyAt = now; copyCache = { left: a.left - hr.left, right: a.right - hr.left, bottom: a.bottom - hr.top }; return copyCache
  }
  const focusX = () => { if (!portrait() || !selected) return 0; const b = bergs.find(x => x.id === selected); if (!b) return 0; b.group.getWorldPosition(tmp); return tmp.x }
  const clock = new THREE.Clock()
  document.addEventListener('visibilitychange', () => { if (!document.hidden) clock.getDelta() })
  const easeOut = x => 1 - Math.pow(1 - x, 3)
  let t = 0, rulerDirty = 0
  renderer.setAnimationLoop(() => {
    const dt = Math.min(clock.getDelta(), 1 / 30)
    if (!visible || document.hidden) return
    t += dt
    if (!drag) { vel *= Math.pow(0.04, dt); spin += vel }
    sea.rotation.y += (spin - sea.rotation.y) * Math.min(1, dt * 8)
    for (const b of bergs) {
      // rise from the deep on load, then a slow bob
      if (b.rise < 1 && t > b.delay) b.rise = Math.min(1, b.rise + dt * 0.9)
      const bob = REDUCED ? 0 : Math.sin(t * 0.9 + b.phase) * 0.06
      b.group.position.y = -9 * (1 - easeOut(b.rise)) + bob
      // focus: others fade back a little while one is picked
      const target = !selected || b.id === selected ? 1 : 0.45
      b.fade += (target - b.fade) * Math.min(1, dt * 6)
      b.tip.material.opacity = b.fade; b.body.material.opacity = 0.92 * b.fade
    }
    if (REDUCED && portrait()) { const fx = focusX(); camera.position.x = camBase.x + fx; lookAt.x = fx; camera.lookAt(lookAt) }
    if (!REDUCED) {
      for (let i = 0; i < wpos.count; i++) {
        const x = wbase[i * 3], y = wbase[i * 3 + 1]
        wpos.setZ(i, Math.sin(x * 0.35 + t * 0.8) * 0.05 + Math.cos(y * 0.5 + t * 0.6) * 0.04)
      }
      wpos.needsUpdate = true
      camera.position.x += ((camBase.x + focusX() + px * 1.2) - camera.position.x) * Math.min(1, dt * 2)
      lookAt.x += (focusX() - lookAt.x) * Math.min(1, dt * 2)
      camera.position.y += ((camBase.y - py * 0.5) - camera.position.y) * Math.min(1, dt * 2)
      camera.lookAt(lookAt)
      if ((rulerDirty += dt) > 0.25) { rulerDirty = 0; drawRuler() }
    }
    const w = hero.clientWidth, h = hero.clientHeight
    const cr = copyRect()
    for (const b of bergs) {
      b.tip.getWorldPosition(tmp); tmp.y += b.tipH + 0.35; tmp.project(camera)
      const lx = (tmp.x + 1) / 2 * w
      let ly = (1 - tmp.y) / 2 * h
      // never sit on the headline/paragraph: drop below the text block if the tag would land on it
      if (cr && lx > cr.left - 60 && lx < cr.right + 60 && ly - 26 < cr.bottom) ly = cr.bottom + 30
      b.label.style.transform = `translate(${lx.toFixed(1)}px, ${ly.toFixed(1)}px) translate(-50%, -100%)`
      b.label.style.visibility = tmp.z < 1 && b.rise > 0.9 ? '' : 'hidden'
    }
    renderer.render(scene, camera)
  })

  window.__sea = { bergs: () => bergs.length, selected: () => selected, spin: () => +sea.rotation.y.toFixed(3), risen: () => bergs.every(b => b.rise >= 1), ticks: () => rulerEl ? rulerEl.querySelectorAll('.tick').length : 0 }
  const go = run => { build(run); const cur = document.querySelector('#brand-picker .chip[aria-pressed="true"]'); const id = selected || (cur && cur.dataset.id); if (id) select(id, false) }
  if (window.SS && window.SS.run) go(window.SS.run)
  window.addEventListener('ss:run', e => go(e.detail))
}
