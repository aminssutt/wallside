import { chromium } from '@playwright/test'

const BASE_URL = 'https://carchat.online'
const MAX_CASE_TIMEOUT_MS = 90_000
const FIRST_TEXT_TIMEOUT_MS = 30_000
const STABLE_WINDOW_MS = 3_000
const POLL_MS = 350
const STATUS_ONLY_TEXTS = new Set([
  'generation de la reponse...',
  'recherche dans le manuel...',
  'recherche sur le web...',
  'recherche web approfondie...',
  'finalisation des sources et de la video...',
  'generating response...',
  'searching manual...',
  'searching the web...',
  'running deeper web search...',
  'finalizing sources and video...',
])

const QUESTIONS = [
  {
    key: 'cruise_control',
    template: 'Comment utiliser le régulateur de vitesse de {name} ?',
  },
  {
    key: 'dashboard_lights',
    template: 'Que signifient les voyants du tableau de bord ?',
  },
]

const pickGuides = (allGuides) => {
  const targetBrands = [
    'BMW',
    'Tesla',
    'Audi',
    'Toyota',
    'Renault',
    'Citroën',
    'Chevrolet',
    'Dacia',
    'Volkswagen',
  ]
  const picked = []
  for (const brand of targetBrands) {
    const g = allGuides.find((row) => String(row.brand || '') === brand)
    if (g) picked.push(g)
  }
  return picked
}

const normalizeSpace = (value) => String(value || '').replace(/\s+/g, ' ').trim()

const repeatedSequenceDetected = (value) => {
  const words = normalizeSpace(value).toLowerCase().match(/[a-zà-ÿ0-9]{2,}/g) || []
  if (words.length < 12) return false
  const seen = new Set()
  for (let i = 0; i <= words.length - 6; i += 1) {
    const key = words.slice(i, i + 6).join(' ')
    if (seen.has(key)) return true
    seen.add(key)
  }
  return false
}

const looksThin = (value) => {
  const text = normalizeSpace(value)
  if (!text) return true
  const sentenceCount = (text.match(/[.!?…](?:\s|$)/g) || []).length
  if (text.length < 180 && sentenceCount < 3) return true
  if (text.length >= 70 && !/[.!?…)\]]$/.test(text)) return true
  return false
}

const qualityFlags = (text) => {
  const lower = normalizeSpace(text).toLowerCase()
  const flags = []
  if (!lower) flags.push('empty')
  if (lower.includes('connexion serveur indisponible')) flags.push('server_unavailable')
  if (lower.includes('la reponse a pris trop de temps')) flags.push('timeout_copy')
  if (lower.includes('ne sont pas disponibles dans le manuel fourni')) flags.push('manual_unavailable_copy')
  if (repeatedSequenceDetected(lower)) flags.push('repetition_loop')
  if (looksThin(lower)) flags.push('thin_or_incomplete')
  return flags
}

const waitForFirstBotText = async (page, startAt) => {
  const deadline = Date.now() + FIRST_TEXT_TIMEOUT_MS
  while (Date.now() < deadline) {
    const text = await page.evaluate(() => {
      const bubbles = Array.from(document.querySelectorAll('.msg.bot .msg-bubble'))
      if (!bubbles.length) return ''
      const last = bubbles[bubbles.length - 1]
      return (last?.innerText || '').trim()
    })
    const normalized = normalizeSpace(text).toLowerCase()
    if (text && !STATUS_ONLY_TEXTS.has(normalized)) {
      return {
        firstTextMs: Date.now() - startAt,
        firstText: text,
      }
    }
    await page.waitForTimeout(POLL_MS)
  }
  return { firstTextMs: null, firstText: '' }
}

const waitForStableBotOutput = async (page) => {
  const started = Date.now()
  const deadline = started + MAX_CASE_TIMEOUT_MS
  let lastSnapshot = ''
  let stableSince = Date.now()

  while (Date.now() < deadline) {
    const snapshot = await page.evaluate(() => {
      const bubbles = Array.from(document.querySelectorAll('.msg.bot .msg-bubble'))
      const lastBubble = bubbles[bubbles.length - 1]
      const text = (lastBubble?.innerText || '').trim()
      const links = Array.from(document.querySelectorAll('.bot-source-link'))
      const hrefs = links.map((node) => node.getAttribute('href') || '')
      const runtimeStatus = (document.querySelector('.chat-runtime-status')?.textContent || '').trim()
      return JSON.stringify({
        text,
        hrefs,
        runtimeStatus,
      })
    })

    const parsed = JSON.parse(snapshot)
    const normalizedText = normalizeSpace(parsed.text).toLowerCase()
    const hasMeaningfulText = Boolean(normalizedText && !STATUS_ONLY_TEXTS.has(normalizedText))

    if (snapshot !== lastSnapshot) {
      lastSnapshot = snapshot
      stableSince = Date.now()
    } else if (
      hasMeaningfulText
      && !parsed.runtimeStatus
      && Date.now() - stableSince >= STABLE_WINDOW_MS
    ) {
      break
    }
    await page.waitForTimeout(POLL_MS)
  }

  const finalState = await page.evaluate(() => {
    const bubbles = Array.from(document.querySelectorAll('.msg.bot .msg-bubble'))
    const lastBubble = bubbles[bubbles.length - 1]
    const text = (lastBubble?.innerText || '').trim()
    const sourceLinks = Array.from(document.querySelectorAll('.bot-source-link')).map((node) => ({
      text: (node.textContent || '').trim(),
      href: node.getAttribute('href') || '',
      tag: String(node.tagName || '').toLowerCase(),
    }))
    const runtimeStatus = (document.querySelector('.chat-runtime-status')?.textContent || '').trim()
    return { text, sourceLinks, runtimeStatus }
  })

  return {
    totalMs: Date.now() - started,
    ...finalState,
  }
}

const runCase = async (context, guide, questionTemplate) => {
  const page = await context.newPage()
  const question = questionTemplate.replace('{name}', guide.name)
  const record = {
    brand: guide.brand,
    slug: guide.slug,
    vehicle: guide.name,
    question,
    firstTextMs: null,
    totalMs: null,
    textLength: 0,
    sourceCount: 0,
    badSourceLinks: 0,
    flags: [],
    textPreview: '',
    runtimeStatus: '',
    error: '',
  }

  try {
    await page.goto(`${BASE_URL}/chat/${guide.slug}`, { timeout: 45_000, waitUntil: 'domcontentloaded' })
    await page.locator('textarea').waitFor({ timeout: 25_000 })
    await page.locator('textarea').fill(question)

    const startedAt = Date.now()
    await page.locator('.chat-action-btn--send').click({ timeout: 10_000 })

    const first = await waitForFirstBotText(page, startedAt)
    record.firstTextMs = first.firstTextMs

    const done = await waitForStableBotOutput(page)
    record.totalMs = Date.now() - startedAt
    record.runtimeStatus = normalizeSpace(done.runtimeStatus)
    record.textLength = normalizeSpace(done.text).length
    record.textPreview = normalizeSpace(done.text).slice(0, 220)
    record.sourceCount = done.sourceLinks.length
    record.badSourceLinks = done.sourceLinks.filter((s) => {
      if (String(s.tag || '').toLowerCase() !== 'a') return false
      const href = String(s.href || '').trim()
      if (!href) return true
      if (href.startsWith('#')) return true
      return !(/^https?:\/\//i.test(href) || href.startsWith('/'))
    }).length
    record.flags = qualityFlags(done.text)
  } catch (error) {
    record.error = String(error?.message || error)
    record.flags.push('case_error')
  } finally {
    await page.close()
  }

  return record
}

const aggregate = (rows) => {
  const ok = rows.filter((r) => !r.flags.includes('server_unavailable') && !r.flags.includes('case_error'))
  const avg = (values) => values.length ? Math.round(values.reduce((a, b) => a + b, 0) / values.length) : null
  return {
    totalCases: rows.length,
    successCases: ok.length,
    failedCases: rows.length - ok.length,
    avgFirstTextMs: avg(ok.map((r) => r.firstTextMs).filter((v) => Number.isFinite(v))),
    avgTotalMs: avg(ok.map((r) => r.totalMs).filter((v) => Number.isFinite(v))),
    thinOrIncomplete: rows.filter((r) => r.flags.includes('thin_or_incomplete')).length,
    repetitionLoop: rows.filter((r) => r.flags.includes('repetition_loop')).length,
    serverUnavailable: rows.filter((r) => r.flags.includes('server_unavailable')).length,
    badSourceLinks: rows.reduce((sum, r) => sum + (r.badSourceLinks || 0), 0),
  }
}

const main = async () => {
  const guidesRes = await fetch(`${BASE_URL}/api/guides`)
  const guidesJson = await guidesRes.json()
  const guides = pickGuides(guidesJson.guides || [])
  if (!guides.length) {
    console.error('No guides found')
    process.exit(1)
  }

  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({
    viewport: { width: 1720, height: 970 },
  })

  const results = []
  try {
    for (const guide of guides) {
      for (const q of QUESTIONS) {
        const row = await runCase(context, guide, q.template)
        row.questionKey = q.key
        results.push(row)
        console.log(
          `[${row.brand}] ${q.key} | first=${row.firstTextMs ?? 'NA'}ms | total=${row.totalMs ?? 'NA'}ms | len=${row.textLength} | src=${row.sourceCount} | flags=${row.flags.join(',') || 'ok'}`
        )
      }
    }
  } finally {
    await context.close()
    await browser.close()
  }

  const summary = aggregate(results)
  console.log('\n=== LIVE DIAGNOSTIC SUMMARY ===')
  console.log(JSON.stringify(summary, null, 2))
  console.log('\n=== LIVE DIAGNOSTIC DETAILS ===')
  console.log(JSON.stringify(results, null, 2))
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
