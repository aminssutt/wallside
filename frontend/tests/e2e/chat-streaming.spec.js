import { expect, test } from '@playwright/test'

const GUIDE_SLUG = 'tesla-model-y'
const GUIDE_PATH = `/api/guides/${GUIDE_SLUG}`
const GUIDE_NAME = 'Tesla Model Y'
const GUIDE_RE = /\/guides\/tesla-model-y\/?(\?.*)?$/
const STREAM_RE = /\/guides\/tesla-model-y\/chat\/stream\/?(\?.*)?$/
const CHAT_RE = /\/guides\/tesla-model-y\/chat\/?(\?.*)?$/
const CORS_HEADERS = {
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET,POST,OPTIONS',
  'access-control-allow-headers': '*',
}

const buildSsePayload = (events) => events
  .map(({ event, data }) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
  .join('')

const installGuideRoutes = async (page) => {
  await page.route('**/*', async (route) => {
    const url = route.request().url()
    if (!GUIDE_RE.test(new URL(url).pathname)) {
      await route.fallback()
      return
    }
    if (STREAM_RE.test(new URL(url).pathname) || CHAT_RE.test(new URL(url).pathname)) {
      await route.fallback()
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      headers: CORS_HEADERS,
      body: JSON.stringify({
        success: true,
        guide: {
          slug: GUIDE_SLUG,
          name: GUIDE_NAME,
          brand: 'Tesla',
          segment: 'suv',
          coverage_note: '2022-2026',
        },
      }),
    })
  })
}

const askQuestion = async (page, question) => {
  const guideResponsePromise = page.waitForResponse((response) => {
    const pathname = new URL(response.url()).pathname
    return GUIDE_RE.test(pathname) && !STREAM_RE.test(pathname) && !CHAT_RE.test(pathname)
  }, { timeout: 15_000 })

  await page.goto(`/chat/${GUIDE_SLUG}`)
  const guideResponse = await guideResponsePromise
  expect(guideResponse.ok()).toBeTruthy()
  await expect(page.locator('textarea')).toBeVisible()
  await page.locator('textarea').fill(question)
  await page.locator('.chat-action-btn--send').click()
}

test('streamed markdown is rendered cleanly and with sources', async ({ page }) => {
  await installGuideRoutes(page)

  const sseBody = buildSsePayload([
    { event: 'start', data: { success: true, vehicle_name: GUIDE_NAME } },
    { event: 'status', data: { step: 'manual_search', message_id: 'mid-stream-1' } },
    { event: 'status', data: { step: 'generating', message_id: 'mid-stream-1' } },
    {
      event: 'chunk',
      data: {
        message_id: 'mid-stream-1',
        text: '# Voici comment il fonctionne :\n\n* **Principe de fonctionnement** : Le système répartit le couple.\n* **Optimisation** : la traction est ajustée en temps réel.',
      },
    },
    {
      event: 'end',
      data: {
        success: true,
        message_id: 'mid-stream-1',
        response: 'Voici comment il fonctionne :\n\n- **Principe de fonctionnement** : Le système répartit le couple.\n- **Optimisation** : la traction est ajustée en temps réel.',
        confidence: 'medium',
      },
    },
    { event: 'sources_start', data: { message_id: 'mid-stream-1' } },
    {
      event: 'source_item',
      data: {
        message_id: 'mid-stream-1',
        source: {
          kind: 'web',
          label: 'Tesla Support',
          display: 'Tesla Support (xDrive equivalent explanation)',
          url: 'https://www.tesla.com/support',
        },
      },
    },
    { event: 'sources_end', data: { message_id: 'mid-stream-1' } },
    { event: 'video_none', data: { message_id: 'mid-stream-1' } },
  ])

  await page.route('**/*', async (route) => {
    const pathname = new URL(route.request().url()).pathname
    if (!STREAM_RE.test(pathname)) {
      await route.fallback()
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream; charset=utf-8',
      headers: {
        ...CORS_HEADERS,
        'cache-control': 'no-cache',
      },
      body: sseBody,
    })
  })

  await askQuestion(page, 'Comment fonctionne la transmission ?')

  const botBubbles = page.locator('.msg.bot .msg-bubble')
  const lastBubble = botBubbles.last()
  await expect(lastBubble).toContainText('Principe de fonctionnement')
  await expect(lastBubble).not.toContainText('# Voici')
  await expect(lastBubble).not.toContainText('* **')
  await expect(page.locator('.bot-sources-section')).toBeVisible()
  await expect(page.locator('.bot-source-link').first()).toContainText('Tesla Support')
})

test('stream fallback shows deep web search status and no timeout copy', async ({ page }) => {
  await installGuideRoutes(page)

  await page.route('**/*', async (route) => {
    const pathname = new URL(route.request().url()).pathname
    if (!STREAM_RE.test(pathname)) {
      await route.fallback()
      return
    }
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      headers: CORS_HEADERS,
      body: JSON.stringify({ success: false, error: 'stream unavailable' }),
    })
  })

  await page.route('**/*', async (route) => {
    const pathname = new URL(route.request().url()).pathname
    if (!CHAT_RE.test(pathname) || STREAM_RE.test(pathname)) {
      await route.fallback()
      return
    }
    await page.waitForTimeout(700)
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      headers: CORS_HEADERS,
      body: JSON.stringify({
        success: true,
        response: 'Réponse fallback propre depuis la recherche web approfondie.',
      }),
    })
  })

  await askQuestion(page, 'Quelle est l autonomie réelle ?')

  await expect(page.locator('.chat-runtime-status')).toContainText('Recherche web approfondie')
  await expect(page.locator('.msg.bot .msg-bubble').last()).toContainText('Réponse fallback propre')
  await expect(page.locator('body')).not.toContainText('Nouvelle tentative en cours')
  await expect(page.locator('body')).not.toContainText('pris trop de temps')
})

test('end response without chunk is still displayed', async ({ page }) => {
  await installGuideRoutes(page)

  const sseBody = buildSsePayload([
    { event: 'start', data: { success: true, vehicle_name: GUIDE_NAME } },
    { event: 'status', data: { step: 'manual_search', message_id: 'mid-end-only' } },
    { event: 'status', data: { step: 'generating', message_id: 'mid-end-only' } },
    {
      event: 'end',
      data: {
        success: true,
        message_id: 'mid-end-only',
        response: 'Réponse complète portée par end.response sans chunk.',
        confidence: 'low',
      },
    },
  ])

  await page.route('**/*', async (route) => {
    const pathname = new URL(route.request().url()).pathname
    if (!STREAM_RE.test(pathname)) {
      await route.fallback()
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream; charset=utf-8',
      headers: CORS_HEADERS,
      body: sseBody,
    })
  })

  await askQuestion(page, 'Test end sans chunk')

  await expect(page.locator('.msg.bot .msg-bubble').last()).toContainText('end.response sans chunk')
})
