import { memo, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useParams, useNavigate } from 'react-router-dom'
import { motion as Motion, AnimatePresence } from 'framer-motion'
import { formatText, FLAG_BY_LANG, LANGUAGES, UI_TEXT, useAppLanguage } from '../i18n'
import { API_URL } from '../api'
import { useToast } from '../toast'
import './ChatPage.css'
import wrenchIcon from '../assets/icons/wrench.svg'
import dashboardIcon from '../assets/icons/dashboard.svg'
import navigationIcon from '../assets/icons/navigation.svg'


const QUICK_ICONS = [wrenchIcon, dashboardIcon, navigationIcon]

// ---------------------------------------------------------------------------
// Vehicle-specific questions based on segment
// ---------------------------------------------------------------------------
const SEGMENT_QUESTIONS = {
  fr: {
    citadine: [
      'Quels sont les dimensions et le rayon de braquage de {vehicle} ?',
      'Comment fonctionne le système Start/Stop de {vehicle} ?',
      'Quelle est la consommation en ville de {vehicle} ?',
    ],
    suv: [
      'Comment fonctionne le système de traction de {vehicle} ?',
      'Quelle est la capacité de remorquage de {vehicle} ?',
      'Quels sont les modes de conduite disponibles sur {vehicle} ?',
    ],
    berline: [
      'Comment utiliser le régulateur de vitesse de {vehicle} ?',
      'Quels sont les systèmes de sécurité de {vehicle} ?',
      'Comment fonctionne la climatisation automatique de {vehicle} ?',
    ],
    sportive: [
      'Quels sont les modes de conduite de {vehicle} ?',
      'Quelles sont les performances moteur de {vehicle} ?',
      'Comment fonctionne le système de freinage de {vehicle} ?',
    ],
    classique: [
      "Quels sont les intervalles d'entretien de {vehicle} ?",
      'Comment fonctionne le moteur de {vehicle} ?',
      'Quelles huiles et fluides utiliser pour {vehicle} ?',
    ],
    utilitaire: [
      'Quelle est la charge utile de {vehicle} ?',
      "Quelles sont les dimensions de l'espace de chargement de {vehicle} ?",
      "Quels sont les intervalles d'entretien de {vehicle} ?",
    ],
    autre: [
      "Quels sont les intervalles d'entretien de {vehicle} ?",
      'Que signifient les voyants du tableau de bord de {vehicle} ?',
      'Quelles sont les spécifications techniques de {vehicle} ?',
    ],
  },
  en: {
    citadine: [
      'What are the dimensions and turning radius of {vehicle}?',
      'How does the Start/Stop system work on {vehicle}?',
      'What is the city fuel consumption of {vehicle}?',
    ],
    suv: [
      'How does the traction system work on {vehicle}?',
      'What is the towing capacity of {vehicle}?',
      'What driving modes are available on {vehicle}?',
    ],
    berline: [
      'How do I use cruise control on {vehicle}?',
      'What are the safety systems in {vehicle}?',
      'How does the automatic climate control work on {vehicle}?',
    ],
    sportive: [
      'What driving modes does {vehicle} offer?',
      'What are the engine performance specs of {vehicle}?',
      'How does the braking system work on {vehicle}?',
    ],
    classique: [
      'What are the maintenance intervals for {vehicle}?',
      'How does the engine work on {vehicle}?',
      'What oils and fluids should I use for {vehicle}?',
    ],
    utilitaire: [
      'What is the payload capacity of {vehicle}?',
      'What are the cargo dimensions of {vehicle}?',
      'What are the maintenance intervals for {vehicle}?',
    ],
    autre: [
      'What are the maintenance intervals for {vehicle}?',
      'What do the dashboard warning lights mean on {vehicle}?',
      'What are the technical specifications of {vehicle}?',
    ],
  },
  ko: {
    citadine: [
      '{vehicle}의 차량 제원과 회전 반경은 어떻게 되나요?',
      '{vehicle}의 스타트/스톱 시스템은 어떻게 작동하나요?',
      '{vehicle}의 도심 연비는 어떻게 되나요?',
    ],
    suv: [
      '{vehicle}의 구동 시스템은 어떻게 작동하나요?',
      '{vehicle}의 견인 능력은 얼마인가요?',
      '{vehicle}에서 사용 가능한 주행 모드는 무엇인가요?',
    ],
    berline: [
      '{vehicle}의 크루즈 컨트롤은 어떻게 사용하나요?',
      '{vehicle}의 안전 시스템은 무엇이 있나요?',
      '{vehicle}의 자동 에어컨은 어떻게 작동하나요?',
    ],
    sportive: [
      '{vehicle}의 주행 모드는 무엇이 있나요?',
      '{vehicle}의 엔진 성능은 어떻게 되나요?',
      '{vehicle}의 브레이크 시스템은 어떻게 작동하나요?',
    ],
    classique: [
      '{vehicle}의 정비 주기는 어떻게 되나요?',
      '{vehicle}의 엔진은 어떻게 작동하나요?',
      '{vehicle}에 어떤 오일과 유체를 사용해야 하나요?',
    ],
    utilitaire: [
      '{vehicle}의 적재 용량은 얼마인가요?',
      '{vehicle}의 화물 공간 크기는 어떻게 되나요?',
      '{vehicle}의 정비 주기는 어떻게 되나요?',
    ],
    autre: [
      '{vehicle}의 정비 주기는 어떻게 되나요?',
      '{vehicle}의 계기판 경고등은 무엇을 의미하나요?',
      '{vehicle}의 기술 사양은 어떻게 되나요?',
    ],
  },
}

const FOLLOWUP_SUGGESTIONS = {
  fr: [
    'Que signifient les voyants du tableau de bord ?',
    'Comment effectuer un entretien de base ?',
  ],
  en: [
    'What do the dashboard warning lights mean?',
    'How to perform basic maintenance?',
  ],
  ko: [
    '계기판 경고등은 무엇을 의미하나요?',
    '기본 정비는 어떻게 하나요?',
  ],
}

function getVehicleQuestions(vehicleName, segment, lang) {
  const langQuestions = SEGMENT_QUESTIONS[lang] || SEGMENT_QUESTIONS.fr
  const questions = langQuestions[segment] || langQuestions.autre
  return questions.map((q) => q.replace(/\{vehicle\}/g, vehicleName))
}
const COMPACT_MENU_BREAKPOINT = 1024
const CHAT_TTFB_TIMEOUT_MS = 8000
const CHAT_TOTAL_TIMEOUT_MS = 60000
const CHAT_END_ARTIFACT_TIMEOUT_MS = 9000
const CHAT_FALLBACK_TIMEOUT_MS = 18000
const MAX_INPUT_LENGTH = 3000
const STREAM_DRAIN_IDLE_MS = 30
const STREAM_DRAIN_BUSY_MS = 24
const KNOWN_STREAM_EVENTS = new Set([
  'start', 'chunk', 'end', 'error',
  'sources_start', 'source_item', 'sources_end',
  'video_result', 'video_none',
  'status',
])

const generateSessionId = () => {
  const arr = new Uint8Array(16)
  crypto.getRandomValues(arr)
  return Array.from(arr, (b) => b.toString(16).padStart(2, '0')).join('')
}

const generateMessageId = (prefix = 'msg') => (
  `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
)
const ASSISTANT_ALIAS_BANK = {
  fr: {
    prefix: ['Atelier', 'Circuit', 'Pitlane', 'Moteur', 'Garage', 'Turbo'],
    core: ['Nova', 'Apex', 'Vortex', 'Volt', 'Piston', 'Sprint'],
  },
  en: {
    prefix: ['Torque', 'Apex', 'Pitlane', 'Drive', 'Garage', 'Vector'],
    core: ['Nova', 'Pulse', 'Vortex', 'Volt', 'Piston', 'Sprint'],
  },
  ko: {
    prefix: ['피트', '터보', '드라이브', '모터', '레이스', '기어'],
    core: ['노바', '펄스', '벡터', '볼트', '피스톤', '스프린트'],
  },
}

const pickRandom = (items) => items[Math.floor(Math.random() * items.length)]

const generateAssistantAlias = (lang = 'en') => {
  const bank = ASSISTANT_ALIAS_BANK[lang] || ASSISTANT_ALIAS_BANK.en
  const serial = Math.floor(10 + Math.random() * 90)
  return `${pickRandom(bank.prefix)} ${pickRandom(bank.core)}-${serial}`
}

const pageVariants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: 0.35 } },
  exit: { opacity: 0, transition: { duration: 0.25 } },
}

const TOAST_COPY = {
  fr: {
    redirecting: 'Action validée. Redirection en cours...',
    copied: 'Copié dans le presse-papier',
  },
  en: {
    redirecting: 'Action confirmed. Redirecting...',
    copied: 'Copied to clipboard',
  },
  ko: {
    redirecting: '확인되었습니다. 이동 중입니다...',
    copied: '클립보드에 복사됨',
  },
}

const STREAM_RUNTIME_COPY = {
  fr: {
    partial: "Le flux s'est interrompu avant la fin. Voici la partie recue pour le moment.",
    timeoutInitial: 'La reponse prend trop de temps. Nouvelle tentative en cours...',
    timeoutPartial: "La generation a pris trop de temps. Voici la partie recue jusqu'ici.",
    timeoutFinal: 'La reponse a pris trop de temps. Reessayez dans un instant.',
  },
  en: {
    partial: 'The stream stopped before the answer finished. Here is the partial response received so far.',
    timeoutInitial: 'The response is taking too long. Retrying now...',
    timeoutPartial: 'The generation took too long. Here is the partial response received so far.',
    timeoutFinal: 'The response took too long. Please try again in a moment.',
  },
  ko: {
    partial: '응답 스트림이 끝나기 전에 중단되었습니다. 지금까지 받은 내용만 먼저 표시합니다.',
    timeoutInitial: '응답이 오래 걸리고 있습니다. 다시 시도합니다...',
    timeoutPartial: '생성이 너무 오래 걸렸습니다. 지금까지 받은 내용만 먼저 표시합니다.',
    timeoutFinal: '응답 시간이 너무 오래 걸렸습니다. 잠시 후 다시 시도해 주세요.',
  },
}

const URL_REGEX = /(https?:\/\/[^\s)]+)/g
const YOUTUBE_URL_REGEX = /(https?:\/\/(?:www\.)?(?:youtube\.com\/[^\s)]+|youtu\.be\/[^\s)]+))/i
const VIDEO_LABEL_REGEX = /^(?:video.*youtube.*|recommended youtube video|youtube recommended video)\s*:?\s*$/i
const VIDEO_UI = {
  fr: { badge: 'Vidéo conseillée', action: 'Voir la vidéo' },
  en: { badge: 'Suggested video', action: 'Watch video' },
  ko: { badge: 'Recommended video', action: 'Open video' },
}

const sanitizeUrl = (url) => {
  return String(url || '').replace(/[)\],.;!?]+$/g, '')
}

const normalizeWebHref = (url) => {
  const clean = sanitizeUrl(url).trim()
  if (!clean) return ''
  if (/^https?:\/\//i.test(clean)) return clean
  if (/^www\./i.test(clean)) return `https://${clean}`
  return ''
}

const extractYoutubeId = (urlValue) => {
  try {
    const parsed = new URL(urlValue)
    const host = parsed.hostname.replace(/^www\./i, '').toLowerCase()
    if (host === 'youtu.be') {
      return parsed.pathname.split('/').filter(Boolean)[0] || ''
    }
    if (host.endsWith('youtube.com')) {
      if (parsed.pathname === '/watch') {
        return parsed.searchParams.get('v') || ''
      }
      const parts = parsed.pathname.split('/').filter(Boolean)
      const knownPrefixes = ['shorts', 'embed', 'live']
      const prefixIndex = parts.findIndex((part) => knownPrefixes.includes(part))
      if (prefixIndex >= 0 && parts[prefixIndex + 1]) {
        return parts[prefixIndex + 1]
      }
    }
  } catch {
    return ''
  }
  return ''
}

const youtubeThumbFromUrl = (urlValue) => {
  const videoId = extractYoutubeId(urlValue).trim()
  if (!videoId || !/^[a-zA-Z0-9_-]{6,}$/.test(videoId)) {
    return ''
  }
  return `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`
}

const SOURCE_SECTION_HEADING_REGEX = /^(?:sources?|references?|r[ée]f[ée]rences?|출처)(?:\s+(?:web|manual|online|liens?|links?))?\s*[:：-]?\s*$/i
const SOURCE_LIST_PREFIX_REGEX = /^\s*(?:[-*•]|\d+[.)])\s+/
const SOURCE_PAGE_REGEX = /\b(?:page|pages|p\.)\s*(\d+(?:\s*[-–]\s*\d+)?)\b/i
const SOURCE_URL_MATCH_REGEX = /(https?:\/\/[^\s)]+)/i

const stripSourceListPrefix = (value) => String(value || '').replace(SOURCE_LIST_PREFIX_REGEX, '').trim()

const extractFirstUrl = (value) => {
  const match = String(value || '').match(SOURCE_URL_MATCH_REGEX)
  return match ? sanitizeUrl(match[1]) : ''
}

const extractSourcePage = (value) => {
  const match = String(value || '').match(SOURCE_PAGE_REGEX)
  return match ? match[1].replace(/\s+/g, '') : ''
}

const formatWebSourceDisplay = (label, url) => {
  const safeLabel = String(label || '').trim()
  const host = (() => {
    try {
      return new URL(url).hostname.replace(/^www\./i, '')
    } catch {
      return ''
    }
  })()

  if (safeLabel) {
    return safeLabel.startsWith('Web:') ? safeLabel : `Web: ${safeLabel}`
  }

  return host ? `Web: ${host}` : url
}

const normalizeSourceObject = (source, guideCtx) => {
  if (!source) {
    return null
  }

  const guideSlug = String(guideCtx?.slug || '').trim()
  const guideName = String(guideCtx?.name || '').trim()

  if (typeof source === 'string') {
    return normalizeSourceObject({ display: source }, guideCtx)
  }

  if (typeof source !== 'object') {
    return null
  }

  const kind = String(source.kind || '').trim().toLowerCase()
  const display = String(source.display || '').trim()
  const label = String(source.label || '').trim()
  const url = normalizeWebHref(extractFirstUrl(source.url || source.display || display || label))
  const page = String(source.page || '').trim() || extractSourcePage(display || label)
  const pdfUrl = String(source.pdf_url || '').trim()
  const excerpt = String(source.excerpt || '').trim()
  const domain = String(source.domain || '').trim()

  if (kind === 'manual') {
    const manualLabel = label
      || display.replace(/^manual\s*:\s*/i, '').replace(SOURCE_PAGE_REGEX, '').trim()
      || guideName
      || 'Manual'
    const manualDisplay = display || `Manual: ${manualLabel}${page ? `, page ${page}` : ''}`
    return {
      kind: 'manual',
      label: manualLabel,
      page: page || '?',
      slug: guideSlug || String(source.slug || '').trim(),
      ...(pdfUrl ? { pdf_url: pdfUrl } : {}),
      ...(excerpt ? { excerpt } : {}),
      display: manualDisplay,
    }
  }

  if (kind === 'web') {
    const webLabel = label || display || formatWebSourceDisplay('', url || domain || 'Web')
    const webUrl = normalizeWebHref(url || String(source.url || '').trim())
    if (!webUrl) {
      return null
    }
    return {
      kind: 'web',
      label: webLabel.replace(/^Web:\s*/i, '').trim() || webLabel,
      domain: domain || '',
      url: webUrl,
      display: display || formatWebSourceDisplay(webLabel, webUrl),
    }
  }

  const manualPage = page || extractSourcePage(display || label)
  if (/^manual\s*:/i.test(display) || /^manual\s*:/i.test(label) || manualPage) {
    const manualLabel = (display || label)
      .replace(/^manual\s*:\s*/i, '')
      .replace(SOURCE_PAGE_REGEX, '')
      .replace(/\s*[,;:-]\s*$/, '')
      .trim() || guideName || 'Manual'
    const maybePdfUrl = url && /\.pdf(?:$|[?#])/i.test(url) ? url : pdfUrl
    return {
      kind: 'manual',
      label: manualLabel,
      page: manualPage || '?',
      slug: guideSlug || String(source.slug || '').trim(),
      ...(maybePdfUrl ? { pdf_url: sanitizeUrl(maybePdfUrl) } : {}),
      ...(excerpt ? { excerpt } : {}),
      display: display || `Manual: ${manualLabel}${manualPage ? `, page ${manualPage}` : ''}`,
    }
  }

  if (url) {
    const webLabel = (display || label || domain || formatWebSourceDisplay('', url))
      .replace(/^web\s*:\s*/i, '')
      .trim()
    return {
      kind: 'web',
      label: webLabel || formatWebSourceDisplay('', url),
      domain,
      url,
      display: display || formatWebSourceDisplay(webLabel, url),
    }
  }

  return null
}

const normalizeSourceArray = (sources, guideCtx) => {
  const normalized = []
  const seen = new Set()
  const sourceList = Array.isArray(sources)
    ? sources
    : sources
      ? [sources]
      : []

  sourceList.forEach((source) => {
    const item = normalizeSourceObject(source, guideCtx)
    if (!item) {
      return
    }

    const key = item.kind === 'manual'
      ? `manual:${item.slug}:${item.page}:${item.label}`
      : `web:${item.url}`

    if (seen.has(key)) {
      return
    }

    seen.add(key)
    normalized.push(item)
  })

  return normalized
}

const splitAssistantResponseArtifacts = (rawText, guideCtx) => {
  const cleanText = normalizeAssistantText(rawText || '')
  if (!cleanText) {
    return { bodyText: '', sources: [] }
  }

  const lines = cleanText.replace(/\r\n/g, '\n').split('\n')

  const isProbableSourceLine = (line) => {
    const normalized = stripSourceListPrefix(line)
    if (!normalized) return false
    return Boolean(
      /^manual\s*:/i.test(normalized)
        || /^web\s*:/i.test(normalized)
        || SOURCE_SECTION_HEADING_REGEX.test(normalized)
        || SOURCE_PAGE_REGEX.test(normalized)
        || extractFirstUrl(normalized),
    )
  }

  let sourceStartIndex = -1
  let sourceHasHeading = false

  for (let index = 0; index < lines.length; index += 1) {
    const normalized = stripSourceListPrefix(lines[index])
    if (!SOURCE_SECTION_HEADING_REGEX.test(normalized)) {
      continue
    }

    const tailHasSourceLines = lines.slice(index + 1).some((line) => isProbableSourceLine(line))
    if (tailHasSourceLines) {
      sourceStartIndex = index
      sourceHasHeading = true
      break
    }
  }

  if (sourceStartIndex < 0) {
    let scanIndex = lines.length
    while (scanIndex > 0 && !lines[scanIndex - 1].trim()) {
      scanIndex -= 1
    }

    let trailingCount = 0
    while (scanIndex > 0) {
      const normalized = stripSourceListPrefix(lines[scanIndex - 1])
      if (!normalized || !isProbableSourceLine(normalized)) {
        break
      }
      trailingCount += 1
      scanIndex -= 1
    }

    if (trailingCount >= 2) {
      sourceStartIndex = scanIndex
      sourceHasHeading = false
    }
  }

  if (sourceStartIndex < 0) {
    return {
      bodyText: cleanText,
      sources: [],
    }
  }

  const bodyText = lines.slice(0, sourceStartIndex).join('\n').trimEnd()
  const sourceLines = lines.slice(sourceHasHeading ? sourceStartIndex + 1 : sourceStartIndex)
  const parsedSources = []
  const sourceHint = {
    slug: guideCtx?.slug || '',
    name: guideCtx?.name || '',
  }

  sourceLines.forEach((line) => {
    const normalized = stripSourceListPrefix(line)
    if (!normalized) {
      return
    }

    if (SOURCE_SECTION_HEADING_REGEX.test(normalized)) {
      return
    }

    const exactManualMatch = normalized.match(/^manual\s*:\s*(.+?)(?:,\s*page(?:s)?\s+(.+))?$/i)
    if (exactManualMatch) {
      const label = exactManualMatch[1].trim() || sourceHint.name || 'Manual'
      const page = (exactManualMatch[2] || extractSourcePage(normalized) || '').trim() || '?'
      const pdfUrl = extractFirstUrl(normalized)
      parsedSources.push({
        kind: 'manual',
        label,
        page,
        slug: sourceHint.slug,
        ...(pdfUrl && /\.pdf(?:$|[?#])/i.test(pdfUrl) ? { pdf_url: pdfUrl } : {}),
        display: `Manual: ${label}${page ? `, page ${page}` : ''}`,
        excerpt: normalized,
      })
      return
    }

    const exactWebMatch = normalized.match(/^web\s*:\s*(.+?)(?:\s*-\s*(https?:\/\/\S+))?$/i)
    if (exactWebMatch) {
      const label = exactWebMatch[1].trim() || formatWebSourceDisplay('', extractFirstUrl(normalized))
      const url = normalizeWebHref(exactWebMatch[2] || extractFirstUrl(normalized))
      if (url) {
        parsedSources.push({
          kind: 'web',
          label: label.replace(/\s*\([^)]+\)\s*$/, '').trim() || label,
          url,
          display: `Web: ${label}`,
        })
      }
      return
    }

    const url = extractFirstUrl(normalized)
    if (url) {
      parsedSources.push({
        kind: 'web',
        label: formatWebSourceDisplay('', url).replace(/^Web:\s*/i, ''),
        url,
        display: formatWebSourceDisplay('', url),
      })
      return
    }

    const page = extractSourcePage(normalized)
    if (page) {
      const label = normalized
        .replace(/^manual\s*:\s*/i, '')
        .replace(SOURCE_PAGE_REGEX, '')
        .replace(/\s*[,;:-]\s*$/, '')
        .trim() || sourceHint.name || 'Manual'
      parsedSources.push({
        kind: 'manual',
        label,
        page: page || '?',
        slug: sourceHint.slug,
        display: `Manual: ${label}${page ? `, page ${page}` : ''}`,
        excerpt: normalized,
      })
    }
  })

  return {
    bodyText,
    sources: normalizeSourceArray(parsedSources, sourceHint),
  }
}

const extractResponseArtifacts = (payload, guideCtx) => {
  if (payload && typeof payload === 'object' && !Array.isArray(payload)) {
    const rawText = String(payload.text || payload.response || '')
    const parsedText = splitAssistantResponseArtifacts(rawText, guideCtx)
    const structuredSources = normalizeSourceArray(
      payload.sources_structured || payload.sources || [],
      guideCtx,
    )
    const parsedVideo = normalizeVideoArtifact(payload.video)

    return {
      text: parsedText.bodyText,
      sources: structuredSources.length > 0 ? structuredSources : parsedText.sources,
      video: parsedVideo,
      confidence: String(payload.confidence || ''),
      metrics: payload.metrics && typeof payload.metrics === 'object' ? payload.metrics : null,
    }
  }

  const parsedText = splitAssistantResponseArtifacts(payload, guideCtx)
  return {
    text: parsedText.bodyText,
    sources: parsedText.sources,
    video: null,
    confidence: '',
    metrics: null,
  }
}

const normalizeVideoArtifact = (video) => {
  if (!video || typeof video !== 'object') {
    return null
  }

  const url = String(video.url || '').trim()
  if (!/^https:\/\//.test(url)) {
    return null
  }

  return {
    title: String(video.title || 'YouTube').trim() || 'YouTube',
    url,
    thumb: String(video.thumb || video.thumbnail || '').trim() || youtubeThumbFromUrl(url),
  }
}

const renderTextWithLinks = (text, keyPrefix) => {
  const chunks = String(text || '').split(URL_REGEX)
  return chunks.map((chunk, index) => {
    if (/^https?:\/\/[^\s)]+$/i.test(chunk)) {
      return (
        <a key={`${keyPrefix}-u-${index}`} href={chunk} target="_blank" rel="noopener noreferrer">
          {chunk}
        </a>
      )
    }
    return <span key={`${keyPrefix}-t-${index}`}>{chunk}</span>
  })
}

const formatInline = (text) => {
  const segments = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return segments.map((segment, index) => {
    if (segment.startsWith('**') && segment.endsWith('**')) {
      return <strong key={`s-${index}`}>{segment.slice(2, -2)}</strong>
    }

    if (segment.startsWith('`') && segment.endsWith('`')) {
      return <code key={`c-${index}`}>{segment.slice(1, -1)}</code>
    }

    return <span key={`t-${index}`}>{renderTextWithLinks(segment, `lnk-${index}`)}</span>
  })
}

const normalizeAssistantText = (rawText) => {
  const clean = (rawText || '').trim()
  // Only strip leading whitespace and quotes, NOT asterisks (breaks bold markdown)
  return clean.replace(/^[\s"]+/u, '').trim()
}

const parseSseEventBlock = (rawBlock) => {
  const lines = String(rawBlock || '').split('\n')
  let event = 'message'
  const dataLines = []

  lines.forEach((line) => {
    if (!line || line.startsWith(':')) return
    if (line.startsWith('event:')) {
      event = line.slice(6).trim().toLowerCase() || 'message'
      return
    }
    if (line.startsWith('data:')) {
      let value = line.slice(5)
      if (value.startsWith(' ')) {
        value = value.slice(1)
      }
      dataLines.push(value)
    }
  })

  const rawData = dataLines.join('\n')
  if (!rawData) {
    return { event, data: '' }
  }

  try {
    return { event, data: JSON.parse(rawData) }
  } catch {
    return { event, data: rawData }
  }
}

const normalizeStreamEventName = (eventName, payload) => {
  const normalizedEvent = String(eventName || '').toLowerCase()
  if (KNOWN_STREAM_EVENTS.has(normalizedEvent)) {
    return normalizedEvent
  }

  if (payload && typeof payload === 'object') {
    const hintedEvent = String(payload.event || payload.type || '').toLowerCase()
    if (KNOWN_STREAM_EVENTS.has(hintedEvent)) {
      return hintedEvent
    }
  }

  return normalizedEvent || 'message'
}

const extractStreamText = (payload) => {
  if (typeof payload === 'string') {
    return payload
  }
  if (!payload || typeof payload !== 'object') {
    return ''
  }

  const textCandidates = [payload.text, payload.chunk, payload.delta, payload.content, payload.response]
  const firstText = textCandidates.find((value) => typeof value === 'string')
  return firstText || ''
}

const extractStreamError = (payload) => {
  if (typeof payload === 'string') {
    return payload.trim()
  }
  if (!payload || typeof payload !== 'object') {
    return ''
  }

  const errorCandidates = [payload.error, payload.message, payload.detail]
  const firstError = errorCandidates.find((value) => typeof value === 'string' && value.trim())
  return firstError ? firstError.trim() : ''
}

const STREAM_STATUS_LABELS = {
  fr: {
    manual_search: 'Recherche dans le manuel…',
    web_search: 'Recherche sur le web…',
    deep_web_search: 'Recherche web approfondie…',
    generating: 'Génération de la réponse…',
    finalizing_artifacts: 'Finalisation des sources…',
  },
  en: {
    manual_search: 'Searching manual...',
    web_search: 'Searching the web...',
    deep_web_search: 'Running deeper web search...',
    generating: 'Generating response...',
    finalizing_artifacts: 'Finalizing sources and video...',
  },
  ko: {
    manual_search: '매뉴얼 검색 중...',
    web_search: '웹 검색 중...',
    deep_web_search: '심화 웹 검색 중...',
    generating: '응답 생성 중...',
  },
}

const THINKING_STEPS_DEF = {
  fr: [
    { key: 'manual_search', label: 'Consultation du manuel' },
    { key: 'web_search', label: 'Recherche internet', triggers: ['web_search', 'deep_web_search'] },
    { key: 'generating', label: 'Rédaction de la réponse' },
  ],
  en: [
    { key: 'manual_search', label: 'Searching the manual' },
    { key: 'web_search', label: 'Web search', triggers: ['web_search', 'deep_web_search'] },
    { key: 'generating', label: 'Writing response' },
  ],
  ko: [
    { key: 'manual_search', label: '매뉴얼 검색' },
    { key: 'web_search', label: '웹 검색', triggers: ['web_search', 'deep_web_search'] },
    { key: 'generating', label: '응답 생성' },
  ],
}

const ThinkingSteps = memo(function ThinkingSteps({ currentStep, visitedSteps, lang }) {
  const steps = THINKING_STEPS_DEF[lang] || THINKING_STEPS_DEF.fr

  return (
    <div className="thinking-steps">
      {steps.map((step) => {
        const triggers = step.triggers || [step.key]
        const isTriggered = triggers.some((t) => visitedSteps.has(t)) || triggers.includes(currentStep)
        if (step.key === 'web_search' && !isTriggered) return null
        const isActive = triggers.includes(currentStep)
        const isDone = !isActive && triggers.some((t) => visitedSteps.has(t))
        return (
          <div
            key={step.key}
            className={`thinking-step${isActive ? ' thinking-step--active' : isDone ? ' thinking-step--done' : ' thinking-step--pending'}`}
          >
            <span className="thinking-step-dot" />
            <span className="thinking-step-label">{step.label}</span>
          </div>
        )
      })}
    </div>
  )
})

const createEmptyStreamArtifacts = () => ({
  sources: [],
  video: null,
  confidence: '',
  metrics: null,
  finalText: '',
})

const normalizeAndMergeSources = (primary, secondary, guideCtx) => {
  const merged = [...(primary || []), ...(secondary || [])]
  if (!merged.length) return []
  return normalizeSourceArray(merged, guideCtx)
}

const looksAbruptlyTruncated = (value) => {
  const text = String(value || '').trim()
  if (!text || text.length < 60) return false
  return !/[.!?…)\]]$/.test(text)
}

const shouldPreferFinalResponse = (currentText, finalText) => {
  const current = String(currentText || '').trim()
  const finalValue = String(finalText || '').trim()
  if (!finalValue) return false
  if (!current) return true
  if (current === finalValue) return false
  // If what we already rendered is a clean prefix of the final text, the
  // drain queue just hasn't caught up yet — do NOT swap, let the remaining
  // slices arrive on their own. Swapping here caused the visible flicker
  // where the bot message jumped to the full answer mid-typing.
  if (finalValue.startsWith(current)) return false
  // Only swap when the streamed text clearly diverged from the final and
  // the streamed text looks abruptly truncated (mid-sentence / mid-word).
  if (looksAbruptlyTruncated(current) && finalValue.length >= current.length) return true
  return false
}

const sliceStreamChunkForDisplay = (chunkText) => {
  const chars = Array.from(String(chunkText || ''))
  if (chars.length === 0) {
    return []
  }

  const sliceSize = chars.length > 360 ? 4 : chars.length > 180 ? 3 : 2
  const slices = []
  for (let index = 0; index < chars.length; index += sliceSize) {
    slices.push(chars.slice(index, index + sliceSize).join(''))
  }
  return slices
}

const pickStreamDrainProfile = (queueLength) => {
  // Keep the interval steady so the typing rhythm stays uniform. The previous
  // implementation flipped the interval per tick based on queue length, which
  // made the animation visibly accelerate and decelerate ("skipping"). Only
  // scale slicesPerTick when the queue backs up so we still catch up without
  // changing the cadence.
  const intervalMs = STREAM_DRAIN_IDLE_MS
  if (queueLength > 240) {
    return { intervalMs, slicesPerTick: 6 }
  }
  if (queueLength > 120) {
    return { intervalMs, slicesPerTick: 4 }
  }
  if (queueLength > 48) {
    return { intervalMs, slicesPerTick: 2 }
  }
  return { intervalMs, slicesPerTick: 1 }
}

const SOURCE_I18N = {
  fr: { title: 'Sources', newTab: 'Nouvel onglet', unavailable: 'PDF non disponible pour le moment', externalPdf: 'Ce PDF est hébergé sur un site externe. Cliquez ci-dessous pour le consulter.', openPdf: 'Ouvrir le PDF' },
  en: { title: 'Sources', newTab: 'New tab', unavailable: 'PDF not available at the moment', externalPdf: 'This PDF is hosted externally. Click below to view it.', openPdf: 'Open PDF' },
  ko: { title: '\uCD9C\uCC98', newTab: '\uC0C8 \uD0ED', unavailable: 'PDF\uB97C \uD604\uC7AC \uC0AC\uC6A9\uD560 \uC218 \uC5C6\uC2B5\uB2C8\uB2E4', externalPdf: '\uC774 PDF\uB294 \uC678\uBD80 \uC0AC\uC774\uD2B8\uC5D0 \uD638\uC2A4\uD305\uB418\uC5B4 \uC788\uC2B5\uB2C8\uB2E4.', openPdf: 'PDF \uC5F4\uAE30' },
}

function SourcesList({ sources, lang }) {
  const [proofIndex, setProofIndex] = useState(null)
  const [pdfError, setPdfError] = useState(false)
  const proofSrc = proofIndex !== null ? sources[proofIndex] : null
  const i = SOURCE_I18N[lang] || SOURCE_I18N.fr

  const openProof = (index) => {
    setPdfError(false)
    setProofIndex(index)
  }

  return (
    <div className="bot-sources-section">
      <h4 className="bot-heading">{i.title}</h4>
      <ul className="bot-sources-list">
        {sources.map((src, idx) => (
          <li key={`src-${idx}`} className={`bot-source-item bot-source-${src.kind}`}>
            {src.kind === 'manual' && src.slug ? (
              <button type="button" className="bot-source-link" onClick={() => openProof(idx)}>
                {src.display || `${src.label}, page ${src.page}`}
              </button>
            ) : src.kind === 'web' && src.url ? (() => {
              const safeHref = normalizeWebHref(src.url)
              if (!safeHref) {
                return <span>{src.display || src.label}</span>
              }
              return (
                <a href={safeHref} target="_blank" rel="noopener noreferrer" className="bot-source-link">
                  {src.display || src.label}
                </a>
              )
            })() : (
              <span>{src.display || src.label}</span>
            )}
          </li>
        ))}
      </ul>
      {proofSrc && (proofSrc.slug || proofSrc.pdf_url) && createPortal(
        <div className="proof-overlay" onClick={() => setProofIndex(null)}>
          <div className="proof-popup proof-popup--pdf" onClick={(e) => e.stopPropagation()}>
            <div className="proof-header">
              <span className="proof-label">{proofSrc.label}, page {proofSrc.page}</span>
              {!pdfError && (
                <a
                  href={proofSrc.pdf_url
                    ? `${proofSrc.pdf_url}#page=${String(proofSrc.page).split('-')[0]}`
                    : `${API_URL}/guides/${proofSrc.slug}/pdf#page=${String(proofSrc.page).split('-')[0]}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="proof-newtab"
                >
                  {i.newTab}
                </a>
              )}
              <button type="button" className="proof-close" onClick={() => setProofIndex(null)}>&times;</button>
            </div>
            {(() => {
              const pdfSrc = proofSrc.pdf_url
                ? `${proofSrc.pdf_url}#page=${String(proofSrc.page).split('-')[0]}`
                : `${API_URL}/guides/${proofSrc.slug}/pdf#page=${String(proofSrc.page).split('-')[0]}`
              const isMobileOrIOS = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent)

              if (pdfError) {
                return (
                  <div className="proof-unavailable">
                    <p>{i.unavailable}</p>
                    {proofSrc.excerpt && <p className="proof-excerpt">{proofSrc.excerpt}</p>}
                  </div>
                )
              }

              if (isMobileOrIOS) {
                return (
                  <div className="proof-mobile-fallback">
                    <p>{i.externalPdf || 'Ce PDF est hébergé sur un site externe.'}</p>
                    <a href={pdfSrc} target="_blank" rel="noopener noreferrer" className="proof-mobile-link">
                      {i.openPdf || 'Ouvrir le PDF'}
                    </a>
                  </div>
                )
              }

              return (
                <iframe
                  className="proof-iframe"
                  src={pdfSrc}
                  title={`${proofSrc.label} - page ${proofSrc.page}`}
                  onError={() => setPdfError(true)}
                  onLoad={(e) => {
                    try {
                      const doc = e.target.contentDocument
                      if (doc && doc.body && doc.body.textContent.includes('PDF not found')) {
                        setPdfError(true)
                      }
                    } catch { /* cross-origin, PDF loaded fine */ }
                  }}
                />
              )
            })()}
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}

const RichBotMessage = memo(function RichBotMessage({ text, lang = 'fr', video, confidence, sources }) {
  const lines = normalizeAssistantText(text).replace(/\r\n/g, '\n').split('\n')
  const blocks = []
  let listBuffer = null
  let pendingVideoLabel = ''
  const videoUi = VIDEO_UI[lang] || VIDEO_UI.fr

  const flushList = () => {
    if (listBuffer && listBuffer.items.length > 0) {
      blocks.push(listBuffer)
    }
    listBuffer = null
  }

  lines.forEach((rawLine) => {
    const line = rawLine.trim()

    if (!line) {
      flushList()
      pendingVideoLabel = ''
      return
    }

    if (VIDEO_LABEL_REGEX.test(line)) {
      flushList()
      pendingVideoLabel = line.replace(/:\s*$/, '')
      return
    }

    const youtubeMatch = line.match(YOUTUBE_URL_REGEX)
    if (youtubeMatch) {
      flushList()
      const url = sanitizeUrl(youtubeMatch[1])
      let title = line
        .replace(/^[-*]\s+/, '')
        .replace(youtubeMatch[1], '')
        .replace(/[:\s-]+$/, '')
        .trim()

      if (!title && pendingVideoLabel) {
        title = pendingVideoLabel.replace(/:\s*$/, '').trim()
      }
      if (!title || VIDEO_LABEL_REGEX.test(title)) {
        title = 'YouTube'
      }

      blocks.push({
        type: 'video',
        content: {
          title,
          url,
          thumb: youtubeThumbFromUrl(url),
        },
      })
      pendingVideoLabel = ''
      return
    }

    const headingMatch = line.match(/^#{1,3}\s+(.+)/)
    if (headingMatch) {
      flushList()
      blocks.push({ type: 'heading', content: headingMatch[1] })
      return
    }

    if (line.length <= 50 && line.endsWith(':') && !line.startsWith('- ') && !/[.!?,;]/.test(line.slice(0, -1))) {
      flushList()
      blocks.push({ type: 'heading', content: line.slice(0, -1) })
      pendingVideoLabel = ''
      return
    }

    const bulletMatch = line.match(/^[-*]\s+(.+)/)
    const numberedMatch = line.match(/^\d+\.\s+(.+)/)
    if (bulletMatch || numberedMatch) {
      const item = bulletMatch ? bulletMatch[1] : numberedMatch[1]
      const listType = numberedMatch ? 'ordered' : 'unordered'

      if (!listBuffer || listBuffer.listType !== listType) {
        flushList()
        listBuffer = { type: 'list', listType, items: [] }
      }

      listBuffer.items.push(item)
      return
    }

    flushList()
    blocks.push({ type: 'paragraph', content: line })
    pendingVideoLabel = ''
  })

  flushList()

  return (
    <div className="bot-rich-message">
      {confidence && (
        <span className={`confidence-badge confidence-${confidence}`}>
          {{ fr: { high: 'Fiabilité élevée', medium: 'Fiabilité moyenne', low: 'Fiabilité limitée' },
             en: { high: 'High confidence', medium: 'Medium confidence', low: 'Low confidence' },
             ko: { high: '\uB192\uC740 \uC2E0\uB8B0\uB3C4', medium: '\uC911\uAC04 \uC2E0\uB8B0\uB3C4', low: '\uB0AE\uC740 \uC2E0\uB8B0\uB3C4' },
          }[lang]?.[confidence] || confidence}
        </span>
      )}
      {blocks.map((block, index) => {
        if (block.type === 'heading') {
          return (
            <h4 className="bot-heading" key={`h-${index}`}>
              {formatInline(block.content)}
            </h4>
          )
        }

        if (block.type === 'video') {
          return (
            <div className="bot-video-card" key={`v-${index}`}>
              <a className="bot-video-thumb" href={block.content.url} target="_blank" rel="noopener noreferrer">
                {block.content.thumb ? (
                  <img src={block.content.thumb} alt={block.content.title} loading="lazy" />
                ) : (
                  <div className="bot-video-thumb-fallback">
                    <span>YouTube</span>
                  </div>
                )}
                <span className="bot-video-play-icon" aria-hidden="true">&#9654;</span>
                <span className="bot-video-badge">{videoUi.badge}</span>
              </a>
              <div className="bot-video-content">
                <p className="bot-video-title">{block.content.title}</p>
              </div>
              <a className="bot-video-action" href={block.content.url} target="_blank" rel="noreferrer">
                {videoUi.action}
              </a>
            </div>
          )
        }

        if (block.type === 'list') {
          if (block.listType === 'ordered') {
            return (
              <ol className="bot-list" key={`l-${index}`}>
                {block.items.map((item, i) => (
                  <li key={`${i}-${item.slice(0, 30)}`}>{formatInline(item)}</li>
                ))}
              </ol>
            )
          }

          return (
            <ul className="bot-list" key={`l-${index}`}>
              {block.items.map((item) => (
                <li key={item}>{formatInline(item)}</li>
              ))}
            </ul>
          )
        }

        return (
          <p className="bot-paragraph" key={`p-${index}`}>
            {formatInline(block.content)}
          </p>
        )
      })}
      {sources && sources.length > 0 && (
        <SourcesList sources={sources} lang={lang} />
      )}
      {video && video.url && (
        <div className="bot-video-card" key="stream-video">
          <a className="bot-video-thumb" href={video.url} target="_blank" rel="noopener noreferrer">
            {video.thumb ? (
              <img src={video.thumb} alt={video.title} loading="lazy" />
            ) : (
              <div className="bot-video-thumb-fallback"><span>YouTube</span></div>
            )}
            <span className="bot-video-play-icon" aria-hidden="true">&#9654;</span>
            <span className="bot-video-badge">{videoUi.badge}</span>
          </a>
          <div className="bot-video-content">
            <p className="bot-video-title">{video.title}</p>
          </div>
          <a className="bot-video-action" href={video.url} target="_blank" rel="noreferrer">
            {videoUi.action}
          </a>
        </div>
      )}
    </div>
  )
})

const stripUnclosedMarkdownPairs = (text) => {
  // During streaming, chunks arrive with partial markdown markers like
  // "**drivi" (opening bold, closing will come in a later chunk). When
  // the parser sees an odd number of ** or ` markers it means one pair
  // is unclosed — hide the last opener so "**drivi" shows as "drivi"
  // rather than literal "**drivi" until the closing ** arrives and the
  // next re-render wraps it in <strong>.
  let result = text
  const boldCount = (result.match(/\*\*/g) || []).length
  if (boldCount % 2 === 1) {
    result = result.replace(/\*\*([^*]*)$/, '$1')
  }
  const tickCount = (result.match(/`/g) || []).length
  if (tickCount % 2 === 1) {
    result = result.replace(/`([^`]*)$/, '$1')
  }
  return result
}

const normalizeStreamingLine = (line) => {
  const raw = String(line || '')
  if (!raw.trim()) return ''

  let cleaned = raw
    .replace(/^\s*#{1,6}\s+/, '')
    .replace(/^\s*[-*]\s+(?=\S)/, '• ')
    .replace(/^\s*\*\s+/, '• ')

  cleaned = stripUnclosedMarkdownPairs(cleaned)
  cleaned = cleaned.replace(/\s{2,}/g, ' ').trim()
  return cleaned
}

const StreamingBotMessage = memo(function StreamingBotMessage({ text }) {
  const lines = normalizeAssistantText(text)
    .replace(/\r\n/g, '\n')
    .split('\n')
    .map(normalizeStreamingLine)

  const visibleLines = lines.map((line) => line || '')
  let lastContentIndex = -1
  for (let i = visibleLines.length - 1; i >= 0; i -= 1) {
    if (visibleLines[i]) {
      lastContentIndex = i
      break
    }
  }

  return (
    <div className="bot-rich-message bot-rich-message--streaming" aria-live="polite" aria-atomic="false">
      {visibleLines.map((line, index) => {
        if (!line) return null
        const isLast = index === lastContentIndex
        return (
          <p
            key={`stream-line-${index}`}
            className={`bot-paragraph${line.startsWith('• ') ? ' bot-stream-bullet' : ''}`}
          >
            {formatInline(line)}
            {isLast && <span className="stream-cursor" aria-hidden="true" />}
          </p>
        )
      })}
      {lastContentIndex < 0 && (
        <p className="bot-paragraph">
          <span className="stream-cursor" aria-hidden="true" />
        </p>
      )}
    </div>
  )
})

function ChatPage() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [lang, setLang] = useAppLanguage()
  const [guide, setGuide] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamStatus, setStreamStatus] = useState('')
  const [visitedSteps, setVisitedSteps] = useState(() => new Set())
  const [errorKey, setErrorKey] = useState('')
  const [langOpen, setLangOpen] = useState(false)
  const [navMenuOpen, setNavMenuOpen] = useState(false)
  const [showExitConfirm, setShowExitConfirm] = useState(false)
  const [pendingExitPath, setPendingExitPath] = useState('')
  const [isCompactNav, setIsCompactNav] = useState(
    typeof window !== 'undefined' ? window.innerWidth <= COMPACT_MENU_BREAKPOINT : false,
  )
  const [sessionId] = useState(() => generateSessionId())
  const [assistantAliases] = useState(() => ({
    fr: generateAssistantAlias('fr'),
    en: generateAssistantAlias('en'),
    ko: generateAssistantAlias('ko'),
  }))
  const [showScrollBtn, setShowScrollBtn] = useState(false)
  const chatContainerRef = useRef(null)
  const langDropdownRef = useRef(null)
  const inputRef = useRef(null)
  const displayQueueRef = useRef([])
  const drainTimerRef = useRef(null)
  const streamDoneRef = useRef(false)
  const pendingStreamArtifactsRef = useRef(createEmptyStreamArtifacts())
  const artifactMergeTimerRef = useRef(null)
  const userScrolledUpRef = useRef(false)
  const abortControllerRef = useRef(null)
  const abortReasonRef = useRef('')
  const t = UI_TEXT[lang] || UI_TEXT.fr
  const toastCopy = TOAST_COPY[lang] || TOAST_COPY.en
  const streamRuntimeCopy = STREAM_RUNTIME_COPY[lang] || STREAM_RUNTIME_COPY.en
  const coverageLabel = t.chat.coverageLabel || '{coverage}'
  const exitConfirmTitle = t.chat.exitConfirmTitle || 'End this chat?'
  const exitConfirmText = t.chat.exitConfirmText || 'Are you sure you want to leave this conversation?'
  const exitConfirmCancel = t.chat.exitConfirmCancel || 'Cancel'
  const exitConfirmAccept = t.chat.exitConfirmAccept || 'Leave'
  const exitConfirmKicker = lang === 'fr' ? 'TERMINER LA LIAISON ?' : lang === 'ko' ? '링크를 종료하시겠습니까?' : 'TERMINATE NEURAL LINK?'
  const exitNodeLabel = lang === 'fr' ? 'NOEUD.ACTIF' : lang === 'ko' ? '활성 노드' : 'ACTIVE.NODE'
  const currentLang = LANGUAGES.find((entry) => entry.code === lang) || LANGUAGES[0]
  const terminalSystemLabel = assistantAliases[lang] || assistantAliases.en
  const terminalProtocolLabel = 'PROTOCOL_SECURE_LINE'

  const quickQuestions = useMemo(() => {
    if (!guide) return []
    const questions = getVehicleQuestions(guide.name, guide.segment || 'autre', lang)
    return questions.map((text, index) => ({
      text,
      icon: QUICK_ICONS[index % QUICK_ICONS.length],
    }))
  }, [guide, lang])
  const isIntroMode = messages.length === 0 && !isLoading
  const showFollowUp = messages.length > 0 && !isLoading && !isStreaming
    && messages[messages.length - 1]?.type === 'bot'

  useEffect(() => {
    const loadGuide = async () => {
      try {
        const res = await fetch(`${API_URL}/guides/${slug}`)
        const data = await res.json()
        if (!data.success) {
          setErrorKey('guideNotFound')
          return
        }
        setGuide(data.guide)
        try {
          localStorage.setItem('mechora_last_vehicle', JSON.stringify({
            slug: slug,
            name: data.guide.name,
            brand: data.guide.brand || '',
            segment: data.guide.segment || '',
          }))
        } catch {
          // Ignore localStorage failures in restricted environments.
        }
      } catch {
        setErrorKey('guideLoadError')
      }
    }

    void loadGuide()
  }, [slug])

  useEffect(() => {
    if (streamStatus) {
      setVisitedSteps((prev) => {
        if (prev.has(streamStatus)) return prev
        return new Set([...prev, streamStatus])
      })
    }
  }, [streamStatus])

  /* -- detect user scrolling up (don't force scroll during streaming) -- */
  const isAutoScrollingRef = useRef(false)
  useEffect(() => {
    const el = chatContainerRef.current
    if (!el) return
    const handleScroll = () => {
      // Ignore scroll events triggered by our own auto-scroll
      if (isAutoScrollingRef.current) return
      const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
      userScrolledUpRef.current = distanceFromBottom > 120
      setShowScrollBtn(distanceFromBottom > 200)
    }
    el.addEventListener('scroll', handleScroll, { passive: true })
    return () => el.removeEventListener('scroll', handleScroll)
  }, [])

  /* -- auto-scroll only if user is near bottom ------------------------- */
  const lastAutoScrollAtRef = useRef(0)
  const autoScrollFrameRef = useRef(null)
  useEffect(() => {
    if (userScrolledUpRef.current) return
    // Throttle mid-stream scroll updates so we don't thrash layout on every
    // drain tick (drainTick fires every ~30ms). Non-streaming updates still
    // scroll immediately.
    const now = performance.now()
    const minIntervalMs = isStreaming ? 90 : 0
    const elapsed = now - lastAutoScrollAtRef.current
    const delay = elapsed >= minIntervalMs ? 0 : minIntervalMs - elapsed
    const timer = window.setTimeout(() => {
      autoScrollFrameRef.current = requestAnimationFrame(() => {
        if (chatContainerRef.current) {
          isAutoScrollingRef.current = true
          lastAutoScrollAtRef.current = performance.now()
          chatContainerRef.current.scrollTo({
            top: chatContainerRef.current.scrollHeight,
            behavior: isStreaming ? 'auto' : 'smooth',
          })
          requestAnimationFrame(() => { isAutoScrollingRef.current = false })
        }
      })
    }, delay)
    return () => {
      window.clearTimeout(timer)
      if (autoScrollFrameRef.current) cancelAnimationFrame(autoScrollFrameRef.current)
    }
  }, [messages, isLoading, isStreaming])

  /* -- reset scroll flag when user sends a new message ----------------- */
  useEffect(() => {
    if (isLoading) {
      userScrolledUpRef.current = false
    }
  }, [isLoading])

  const markUserScrollIntent = () => {
    const el = chatContainerRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    if (distanceFromBottom > 40) {
      userScrolledUpRef.current = true
      setShowScrollBtn(true)
    }
  }

  useEffect(() => {
    if (!langOpen) return undefined

    const handleOutsideClick = (event) => {
      if (langDropdownRef.current && !langDropdownRef.current.contains(event.target)) {
        setLangOpen(false)
      }
    }

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setLangOpen(false)
      }
    }

    document.addEventListener('mousedown', handleOutsideClick)
    document.addEventListener('keydown', handleEscape)

    return () => {
      document.removeEventListener('mousedown', handleOutsideClick)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [langOpen])

  useEffect(() => {
    const handleResize = () => {
      const compact = window.innerWidth <= COMPACT_MENU_BREAKPOINT
      setIsCompactNav(compact)
      if (!compact) {
        setNavMenuOpen(false)
      }
    }

    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  useEffect(() => {
    if (!navMenuOpen) return undefined

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setNavMenuOpen(false)
      }
    }

    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [navMenuOpen])

  useEffect(() => {
    if (!showExitConfirm) return undefined

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setShowExitConfirm(false)
      }
    }

    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [showExitConfirm])

  const closeExitConfirm = () => {
    setShowExitConfirm(false)
    setPendingExitPath('')
  }

  const openExitConfirm = (targetPath = '/') => {
    setLangOpen(false)
    setNavMenuOpen(false)
    setPendingExitPath(targetPath)
    setShowExitConfirm(true)
  }

  const handleLangSelect = (nextLang) => {
    setLang(nextLang)
    setLangOpen(false)
    setNavMenuOpen(false)
  }

  const confirmExitChat = () => {
    const targetPath = pendingExitPath || '/'
    closeExitConfirm()
    showToast({ type: 'success', message: toastCopy.redirecting })
    navigate(targetPath)
  }

  useEffect(() => {
    return () => {
      if (drainTimerRef.current !== null) {
        window.clearTimeout(drainTimerRef.current)
      }
      if (artifactMergeTimerRef.current !== null) {
        window.clearTimeout(artifactMergeTimerRef.current)
      }
    }
  }, [])

  const resetPendingStreamArtifacts = () => {
    pendingStreamArtifactsRef.current = createEmptyStreamArtifacts()
  }

  const cancelDrain = () => {
    if (drainTimerRef.current !== null) {
      window.clearTimeout(drainTimerRef.current)
      drainTimerRef.current = null
    }
  }

  const scheduleArtifactMerge = () => {
    if (artifactMergeTimerRef.current !== null) {
      window.clearTimeout(artifactMergeTimerRef.current)
    }
    artifactMergeTimerRef.current = window.setTimeout(() => {
      artifactMergeTimerRef.current = null
      // Mid-stream merges only update sidecar artifacts (sources, video,
      // metrics, confidence). The main content is NEVER swapped while the
      // drain queue is still flushing — that was the visible flicker.
      mergeBufferedArtifactsIntoLastBot({ allowContentSwap: false })
    }, 120)
  }

  const mergeBufferedArtifactsIntoLastBot = ({ allowContentSwap = false } = {}) => {
    const pendingArtifacts = pendingStreamArtifactsRef.current
    const hasArtifacts = Boolean(
      pendingArtifacts.finalText
      || pendingArtifacts.confidence
      || pendingArtifacts.metrics
      || pendingArtifacts.video?.url
      || pendingArtifacts.sources.length,
    )

    if (!hasArtifacts) {
      return
    }

    setMessages((previous) => {
      if (previous.length === 0) return previous
      const updated = [...previous]
      const lastMessage = updated[updated.length - 1]
      if (!lastMessage || lastMessage.type !== 'bot') {
        return previous
      }

      updated[updated.length - 1] = {
        ...lastMessage,
        ...(allowContentSwap && shouldPreferFinalResponse(lastMessage.content, pendingArtifacts.finalText)
          ? { content: pendingArtifacts.finalText }
          : {}),
        ...(pendingArtifacts.confidence ? { confidence: pendingArtifacts.confidence } : {}),
        ...(pendingArtifacts.metrics ? { metrics: pendingArtifacts.metrics } : {}),
        ...(pendingArtifacts.video?.url
          ? (
              lastMessage.video?.url && lastMessage.video.url === pendingArtifacts.video.url
                ? {}
                : { video: pendingArtifacts.video }
            )
          : {}),
        ...(pendingArtifacts.sources.length || (Array.isArray(lastMessage.sources) && lastMessage.sources.length)
          ? {
              sources: normalizeAndMergeSources(lastMessage.sources || [], pendingArtifacts.sources, {
                slug: guide?.slug || '',
                name: guide?.name || '',
              }),
            }
          : {}),
      }
      return updated
    })
  }

  const finalizeStreamingPresentation = () => {
    cancelDrain()
    if (artifactMergeTimerRef.current !== null) {
      window.clearTimeout(artifactMergeTimerRef.current)
      artifactMergeTimerRef.current = null
    }
    // Drain is fully flushed here, so it's safe to reconcile the streamed
    // text against the final response (only swaps on true divergence).
    mergeBufferedArtifactsIntoLastBot({ allowContentSwap: true })
    resetPendingStreamArtifacts()
    displayQueueRef.current = []
    streamDoneRef.current = false
    setStreamStatus('')
    setIsStreaming(false)
  }

  const appendTextToLastBotMessage = (textDelta) => {
    if (!textDelta) return

    setMessages((previous) => {
      if (!previous.length) return [{ id: generateMessageId('bot'), type: 'bot', content: textDelta }]
      const updated = [...previous]
      const lastMessage = updated[updated.length - 1]

      if (!lastMessage || lastMessage.type !== 'bot') {
        return [...previous, { id: generateMessageId('bot'), type: 'bot', content: textDelta }]
      }

      updated[updated.length - 1] = {
        ...lastMessage,
        content: `${lastMessage.content || ''}${textDelta}`,
      }
      return updated
    })
  }

  const flushQueuedStreamText = () => {
    if (displayQueueRef.current.length === 0) {
      return
    }

    const pendingText = displayQueueRef.current.join('')
    displayQueueRef.current = []
    appendTextToLastBotMessage(pendingText)
  }

  const appendFinalBotResponse = (responsePayload) => {
    const parsed = extractResponseArtifacts(responsePayload, {
      slug: guide?.slug || '',
      name: guide?.name || '',
    })

    const hasRenderableContent = Boolean(
      parsed.text || parsed.sources.length > 0 || parsed.video,
    )
    const finalText = parsed.text || (hasRenderableContent ? '' : t.chat.unavailable)

    cancelDrain()
    displayQueueRef.current = []

    setMessages((previous) => {
      const nextBotMessage = {
        id: generateMessageId('bot'),
        type: 'bot',
        content: finalText,
        ...(parsed.sources.length ? { sources: parsed.sources } : {}),
        ...(parsed.video ? { video: parsed.video } : {}),
        ...(parsed.confidence ? { confidence: parsed.confidence } : {}),
        ...(parsed.metrics ? { metrics: parsed.metrics } : {}),
      }

      if (previous.length === 0) {
        return [nextBotMessage]
      }

      const updated = [...previous]
      const lastMessage = updated[updated.length - 1]

      if (lastMessage && lastMessage.type === 'bot' && !lastMessage.content && !lastMessage.sources && !lastMessage.video && !lastMessage.confidence && !lastMessage.metrics) {
        updated[updated.length - 1] = { ...lastMessage, ...nextBotMessage, id: lastMessage.id || nextBotMessage.id }
        return updated
      }

      updated.push(nextBotMessage)
      return updated
    })

    setIsStreaming(false)
  }

  const drainTick = () => {
    if (displayQueueRef.current.length === 0) {
      drainTimerRef.current = null
      if (streamDoneRef.current) {
        finalizeStreamingPresentation()
      }
      return
    }

    const { intervalMs, slicesPerTick } = pickStreamDrainProfile(displayQueueRef.current.length)
    const nextSlices = displayQueueRef.current.splice(0, slicesPerTick)
    appendTextToLastBotMessage(nextSlices.join(''))
    drainTimerRef.current = window.setTimeout(drainTick, intervalMs)
  }

  const startDrain = () => {
    if (drainTimerRef.current !== null) return
    drainTimerRef.current = window.setTimeout(drainTick, STREAM_DRAIN_IDLE_MS)
  }

  const appendBotChunk = (chunkText) => {
    const nextChunk = String(chunkText || '')
    if (!nextChunk) return
    displayQueueRef.current.push(...sliceStreamChunkForDisplay(nextChunk))
    startDrain()
  }


  const requestChatJson = async ({ text, signal, timeoutMs = CHAT_FALLBACK_TIMEOUT_MS }) => {
    const controller = new AbortController()
    let timeoutId = null
    let detachParentAbort = null

    if (signal) {
      const relay = () => {
        if (!controller.signal.aborted) {
          controller.abort()
        }
      }
      if (signal.aborted) {
        relay()
      } else {
        signal.addEventListener('abort', relay, { once: true })
        detachParentAbort = () => signal.removeEventListener('abort', relay)
      }
    }

    if (timeoutMs > 0) {
      timeoutId = window.setTimeout(() => {
        if (!controller.signal.aborted) {
          controller.abort()
        }
      }, timeoutMs)
    }

    try {
      const response = await fetch(`${API_URL}/guides/${slug}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, lang, session_id: sessionId }),
        signal: controller.signal,
      })

      let data = null
      let rawText = ''
      try {
        rawText = await response.text()
        data = rawText ? JSON.parse(rawText) : null
      } catch {
        data = null
      }

      if (response.ok && data?.success) {
        return data.response || ''
      }

      if (response.ok && rawText && !data) {
        return rawText.trim() || t.chat.unavailable
      }

      if (!response.ok) {
        throw new Error(`fallback_http_${response.status}`)
      }

      return String(data?.error || '').trim() || t.chat.unavailable
    } finally {
      if (timeoutId) {
        window.clearTimeout(timeoutId)
      }
      detachParentAbort?.()
    }
  }

  const consumeChatStream = async ({ text, signal, onFirstActivity, onFirstChunk, onChunkReceived, onEndReceived }) => {
    let hasChunkContent = false
    let hasStreamActivity = false
    let sawEndEvent = false

    const response = await fetch(`${API_URL}/guides/${slug}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify({ message: text, lang, session_id: sessionId }),
      signal,
    })

    if (!response.ok) {
      const streamError = new Error(`stream endpoint unavailable (${response.status})`)
      streamError.allowFallback = true
      throw streamError
    }

    const contentType = (response.headers.get('content-type') || '').toLowerCase()
    if (!contentType.includes('text/event-stream') || !response.body) {
      const streamError = new Error('invalid stream response')
      streamError.allowFallback = true
      throw streamError
    }

    const ensureStreamingMessage = () => {
      // Mark the pipeline as "generating" at the moment we first see chunks
      // so the ThinkingSteps exit animation shows the final state cleanly
      // (manual_search done → generating active) instead of jumping.
      setStreamStatus((prev) => prev || 'generating')
      setVisitedSteps((prev) => {
        const next = new Set(prev)
        next.add('manual_search')
        next.add('generating')
        return next
      })
      setIsStreaming(true)
      setMessages((previous) => {
        const lastMessage = previous[previous.length - 1]
        if (lastMessage && lastMessage.type === 'bot') {
          return previous
        }
        return [...previous, { id: generateMessageId('bot'), type: 'bot', content: '' }]
      })
    }

    const registerFirstChunk = () => {
      if (!hasChunkContent) {
        onFirstChunk?.()
      }
      hasChunkContent = true
      onChunkReceived?.()
    }

    const registerStreamActivity = () => {
      if (hasStreamActivity) return
      hasStreamActivity = true
      onFirstActivity?.()
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    const handleStreamEvent = ({ event, data }) => {
      const eventName = normalizeStreamEventName(event, data)

      if (eventName === 'start') {
        registerStreamActivity()
        return
      }

      if (eventName === 'status') {
        registerStreamActivity()
        const step = (data && typeof data === 'object') ? data.step : ''
        setStreamStatus(step || '')
        return
      }

      if (eventName === 'chunk') {
        registerStreamActivity()
        const chunkText = extractStreamText(data)
        if (!chunkText) return
        ensureStreamingMessage()
        registerFirstChunk()
        appendBotChunk(chunkText)
        return
      }

      if (eventName === 'end') {
        registerStreamActivity()
        sawEndEvent = true
        onEndReceived?.()
        setStreamStatus('finalizing_artifacts')
        if (!hasChunkContent) {
          appendFinalBotResponse(data)
        }
        if (data && typeof data === 'object') {
          const finalResponseText = String(data.response || '').trim()
          // Pass the full end payload so sources_structured and video are
          // preserved — previously we only forwarded the response text and
          // every source / YouTube card was silently dropped.
          const parsedFinal = extractResponseArtifacts(
            {
              response: finalResponseText,
              sources_structured: data.sources_structured,
              sources: data.sources,
              video: data.video,
              confidence: data.confidence,
              metrics: data.metrics,
            },
            {
              slug: guide?.slug || '',
              name: guide?.name || '',
            },
          )
          pendingStreamArtifactsRef.current = {
            ...pendingStreamArtifactsRef.current,
            confidence: parsedFinal.confidence || String(data.confidence || ''),
            metrics: parsedFinal.metrics
              || (data.metrics && typeof data.metrics === 'object' ? data.metrics : pendingStreamArtifactsRef.current.metrics),
            finalText: parsedFinal.text || finalResponseText || pendingStreamArtifactsRef.current.finalText,
            video: pendingStreamArtifactsRef.current.video?.url
              ? pendingStreamArtifactsRef.current.video
              : (parsedFinal.video || pendingStreamArtifactsRef.current.video),
            sources: normalizeAndMergeSources(
              pendingStreamArtifactsRef.current.sources,
              parsedFinal.sources,
              {
                slug: guide?.slug || '',
                name: guide?.name || '',
              },
            ),
          }
        }
        return
      }

      if (eventName === 'sources_start') {
        registerStreamActivity()
        pendingStreamArtifactsRef.current = {
          ...pendingStreamArtifactsRef.current,
          sources: [],
        }
        return
      }

      if (eventName === 'source_item') {
        registerStreamActivity()
        const src = (data && typeof data === 'object') ? data.source : null
        if (src) {
          pendingStreamArtifactsRef.current = {
            ...pendingStreamArtifactsRef.current,
            sources: [...pendingStreamArtifactsRef.current.sources, src],
          }
          if (sawEndEvent) {
            scheduleArtifactMerge()
          }
        }
        return
      }

      if (eventName === 'sources_end') {
        registerStreamActivity()
        if (sawEndEvent) {
          scheduleArtifactMerge()
        }
        return
      }

      if (eventName === 'video_result') {
        registerStreamActivity()
        const videoData = (data && typeof data === 'object') ? data : {}
        const url = String(videoData.url || '').trim()
        if (!url || !/^https:\/\//.test(url)) return
        pendingStreamArtifactsRef.current = {
          ...pendingStreamArtifactsRef.current,
          video: {
            title: String(videoData.title || 'YouTube'),
            url,
            thumb: String(videoData.thumbnail || '') || youtubeThumbFromUrl(url),
          },
        }
        if (sawEndEvent) {
          scheduleArtifactMerge()
        }
        return
      }

      if (eventName === 'video_none') {
        registerStreamActivity()
        return
      }

      if (eventName === 'error') {
        const message = extractStreamError(data) || t.chat.serverUnavailable
        const streamError = new Error(message)
        streamError.allowFallback = !hasChunkContent
        streamError.hasChunkContent = hasChunkContent
        streamError.streamErrorMessage = message
        throw streamError
      }

      const fallbackChunk = extractStreamText(data)
      if (!fallbackChunk) return
      ensureStreamingMessage()
      registerFirstChunk()
      appendBotChunk(fallbackChunk)
    }

    try {
      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true }).replace(/\r/g, '')
        let separatorIndex = buffer.indexOf('\n\n')

        while (separatorIndex >= 0) {
          const rawBlock = buffer.slice(0, separatorIndex)
          buffer = buffer.slice(separatorIndex + 2)

          if (rawBlock.trim()) {
            handleStreamEvent(parseSseEventBlock(rawBlock))
          }

          separatorIndex = buffer.indexOf('\n\n')
        }
      }

      buffer += decoder.decode().replace(/\r/g, '')
      if (buffer.trim()) {
        handleStreamEvent(parseSseEventBlock(buffer))
      }

      if (hasChunkContent && !sawEndEvent) {
        const streamError = new Error('stream closed before end event')
        streamError.allowFallback = false
        streamError.hasChunkContent = true
        streamError.streamErrorMessage = streamRuntimeCopy.partial
        throw streamError
      }

      if (!sawEndEvent) {
        const streamError = new Error('empty stream response')
        streamError.allowFallback = true
        streamError.hasChunkContent = false
        throw streamError
      }

      streamDoneRef.current = true
      startDrain()
    } finally {
      reader.releaseLock()
    }
  }

  const sendMessage = async (messageText) => {
    const text = (messageText || input).trim()
    if (!text || isLoading || isStreaming) return
    setStreamStatus('manual_search')
    // Pre-mark manual_search as visited so the first step is always shown as
    // active-then-done even on backends that skip the intermediate status.
    setVisitedSteps(new Set(['manual_search']))

    cancelDrain()
    displayQueueRef.current = []
    streamDoneRef.current = false
    resetPendingStreamArtifacts()
    abortReasonRef.current = ''

    setMessages((previous) => [...previous, { id: generateMessageId('user'), type: 'user', content: text }])
    setInput('')
    window.requestAnimationFrame(() => {
      if (inputRef.current) {
        inputRef.current.style.height = 'auto'
      }
    })
    setIsLoading(true)
    setLangOpen(false)

    let ttfbTimeoutId = null
    let totalTimeoutId = null
    let endArtifactsTimeoutId = null
    let receivedChunk = false
    let receivedStreamActivity = false

    const controller = new AbortController()
    abortControllerRef.current = controller

    const abortWithReason = (reason) => {
      if (controller.signal.aborted) return
      abortReasonRef.current = reason
      controller.abort()
    }

    const clearTtfbTimeout = () => {
      if (ttfbTimeoutId) {
        window.clearTimeout(ttfbTimeoutId)
        ttfbTimeoutId = null
      }
    }

    const clearTotalTimeout = () => {
      if (totalTimeoutId) {
        window.clearTimeout(totalTimeoutId)
        totalTimeoutId = null
      }
    }

    const clearEndArtifactsTimeout = () => {
      if (endArtifactsTimeoutId) {
        window.clearTimeout(endArtifactsTimeoutId)
        endArtifactsTimeoutId = null
      }
    }

    try {
      ttfbTimeoutId = window.setTimeout(() => abortWithReason('timeout_ttfb'), CHAT_TTFB_TIMEOUT_MS)
      totalTimeoutId = window.setTimeout(() => abortWithReason('timeout_total'), CHAT_TOTAL_TIMEOUT_MS)

      try {
        await consumeChatStream({
          text,
          signal: controller.signal,
          onFirstActivity: () => {
            receivedStreamActivity = true
            clearTtfbTimeout()
          },
          onFirstChunk: clearTtfbTimeout,
          onChunkReceived: () => {
            receivedChunk = true
          },
          onEndReceived: () => {
            clearTtfbTimeout()
            clearTotalTimeout()
            clearEndArtifactsTimeout()
            endArtifactsTimeoutId = window.setTimeout(
              () => abortWithReason('timeout_end_artifacts'),
              CHAT_END_ARTIFACT_TIMEOUT_MS,
            )
          },
        })
      } catch (streamError) {
        if (streamError?.name === 'AbortError') {
          throw streamError
        }

        // Any failure BEFORE we saw a chunk is eligible for the JSON
        // fallback — including raw network errors (e.g. gunicorn killing
        // the worker mid-stream, Traefik dropping an idle connection).
        // Previously only errors with an explicit allowFallback flag
        // tried the fallback, so a dead worker would surface as
        // "serveur indisponible" with no retry.
        const shouldTryFallback = streamError?.allowFallback || !receivedChunk
        if (shouldTryFallback) {
          setStreamStatus('deep_web_search')
          try {
            const fallbackResponse = await requestChatJson({
              text,
              signal: controller.signal,
              timeoutMs: CHAT_FALLBACK_TIMEOUT_MS,
            })
            setStreamStatus('generating')
            appendFinalBotResponse(fallbackResponse)
            setStreamStatus('')
            return
          } catch (fallbackError) {
            if (fallbackError?.name === 'AbortError') throw fallbackError
            appendFinalBotResponse(t.chat.serverUnavailable)
            setStreamStatus('')
            return
          }
        }

        if (streamError?.hasChunkContent) {
          streamDoneRef.current = true
          startDrain()
          setStreamStatus('')
        } else {
          appendFinalBotResponse(t.chat.serverUnavailable)
          setStreamStatus('')
        }
      }
    } catch (error) {
      if (error?.name === 'AbortError') {
        const abortReason = abortReasonRef.current
        if (abortReason === 'manual_stop') {
          return
        }

        if (abortReason === 'timeout_end_artifacts') {
          streamDoneRef.current = true
          startDrain()
          setStreamStatus('')
          return
        }

        if (abortReason === 'timeout_ttfb' && !receivedChunk) {
          setStreamStatus('deep_web_search')
          try {
            const fallbackResponse = await requestChatJson({
              text,
              signal: null,
              timeoutMs: CHAT_FALLBACK_TIMEOUT_MS,
            })
            setStreamStatus('generating')
            appendFinalBotResponse(fallbackResponse)
            setStreamStatus('')
            return
          } catch (fallbackError) {
            if (fallbackError?.name === 'AbortError') {
              appendFinalBotResponse(streamRuntimeCopy.timeoutFinal)
              setStreamStatus('')
              return
            }
            appendFinalBotResponse(t.chat.serverUnavailable)
            setStreamStatus('')
            return
          }
        }

        if (abortReason === 'timeout_total') {
          if (receivedStreamActivity && !receivedChunk) {
            appendFinalBotResponse(t.chat.serverUnavailable)
            setStreamStatus('')
            return
          }
            appendFinalBotResponse(streamRuntimeCopy.timeoutFinal)
            setStreamStatus('')
            return
        }

        streamDoneRef.current = true
        startDrain()
        setStreamStatus('')
        return
      }
      appendFinalBotResponse(t.chat.serverUnavailable)
      setStreamStatus('')
    } finally {
      clearTtfbTimeout()
      clearTotalTimeout()
      clearEndArtifactsTimeout()
      setIsLoading(false)
      abortControllerRef.current = null
      abortReasonRef.current = ''
      if (drainTimerRef.current === null) {
        setIsStreaming(false)
      }
      inputRef.current?.focus()
    }
  }

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortReasonRef.current = 'manual_stop'
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    if (artifactMergeTimerRef.current !== null) {
      window.clearTimeout(artifactMergeTimerRef.current)
      artifactMergeTimerRef.current = null
    }
    cancelDrain()
    flushQueuedStreamText()
    resetPendingStreamArtifacts()
    streamDoneRef.current = false
    setIsStreaming(false)
    setIsLoading(false)
  }

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void sendMessage()
    }
  }

  if (errorKey) {
    return (
      <Motion.div className="chat-page" variants={pageVariants} initial="initial" animate="animate" exit="exit">
        <div className="chat-empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--error)" strokeWidth="1.5">
            <circle cx="12" cy="12" r="10" />
            <line x1="15" y1="9" x2="9" y2="15" />
            <line x1="9" y1="9" x2="15" y2="15" />
          </svg>
          <h2>{t.chat[errorKey] || t.chat.guideLoadError}</h2>
          <button className="btn-secondary" onClick={() => navigate('/guides')}>{t.chat.guides}</button>
        </div>
      </Motion.div>
    )
  }

  if (!guide) {
    return (
      <Motion.div className="chat-page" variants={pageVariants} initial="initial" animate="animate" exit="exit">
        <div className="chat-empty-state">
          <div className="loader-ring" />
          <p>{t.chat.loadingChat}</p>
        </div>
      </Motion.div>
    )
  }

  return (
    <Motion.div className="chat-page" variants={pageVariants} initial="initial" animate="animate" exit="exit">
      <div className="chat-bg-image" />
      <header className="chat-header">
        {isCompactNav ? (
          <div className="chat-brand chat-brand-static" aria-hidden>
            <img src="/carchat-logo.png" alt="CarChat" width="122" height="36" loading="lazy" />
            <div className="chat-brand-copy">
              <span className="chat-brand-system">{terminalSystemLabel}</span>
              <p>{guide.name}</p>
              {guide.coverage_note ? (
                <small className="chat-brand-note">{formatText(coverageLabel, { coverage: guide.coverage_note })}</small>
              ) : null}
            </div>
          </div>
        ) : (
          <button
            type="button"
            className="chat-brand chat-brand-link"
            onClick={() => openExitConfirm('/')}
            aria-label={(UI_TEXT[lang] || UI_TEXT.fr).guides.home}
          >
            <img src="/carchat-logo.png" alt="CarChat" width="122" height="36" loading="lazy" />
            <div className="chat-brand-copy">
              <span className="chat-brand-system">{terminalSystemLabel}</span>
              <p>{guide.name}</p>
              {guide.coverage_note ? (
                <small className="chat-brand-note">{formatText(coverageLabel, { coverage: guide.coverage_note })}</small>
              ) : null}
            </div>
          </button>
        )}

        <div className="chat-header-right">
          <span className="chat-header-protocol">{terminalProtocolLabel}</span>
          {isCompactNav ? (
            <button
              type="button"
              className="chat-burger-trigger"
              onClick={() => {
                setLangOpen(false)
                setNavMenuOpen((prev) => !prev)
              }}
              aria-label="Menu"
              aria-expanded={navMenuOpen}
              aria-haspopup="dialog"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
          ) : (
            <div className="lang-switcher" ref={langDropdownRef}>
              <Motion.button
                type="button"
                className="lang-toggle"
                onClick={() => setLangOpen((prev) => !prev)}
                whileHover={{ y: -1 }}
                whileTap={{ scale: 0.96 }}
              >
                <img
                  className="chat-lang-flag"
                  src={FLAG_BY_LANG[currentLang?.code] || FLAG_BY_LANG.en}
                  alt={`${currentLang?.label || 'EN'} flag`}
                />
                {currentLang?.label}
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </Motion.button>

              <AnimatePresence>
                {langOpen && (
                  <Motion.div
                    className="chat-lang-dropdown"
                    initial={{ opacity: 0, y: -6, scale: 0.96 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -6, scale: 0.96 }}
                    transition={{ duration: 0.18 }}
                  >
                    {LANGUAGES.map((entry) => (
                      <button
                        key={entry.code}
                        type="button"
                        className={`chat-lang-option${entry.code === lang ? ' chat-lang-option--active' : ''}`}
                        onClick={() => handleLangSelect(entry.code)}
                      >
                        <img
                          className="chat-lang-flag"
                          src={FLAG_BY_LANG[entry.code] || FLAG_BY_LANG.en}
                          alt={`${entry.label} flag`}
                        />
                        <span>{entry.label}</span>
                      </button>
                    ))}
                  </Motion.div>
                )}
              </AnimatePresence>
            </div>
          )}
        </div>
      </header>

      <AnimatePresence>
        {isCompactNav && navMenuOpen && (
          <Motion.div
            className="chat-nav-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setNavMenuOpen(false)}
          >
            <Motion.div
              className="chat-nav-menu"
              initial={{ opacity: 0, y: -10, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.98 }}
              transition={{ duration: 0.18 }}
              onClick={(event) => event.stopPropagation()}
            >
              <button type="button" className="chat-nav-home" onClick={() => openExitConfirm('/')}>
                {(UI_TEXT[lang] || UI_TEXT.fr).guides.home}
              </button>
              <div className="chat-nav-languages">
                {LANGUAGES.map((entry) => (
                  <button
                    key={entry.code}
                    type="button"
                    className={`chat-nav-lang-option${entry.code === lang ? ' chat-nav-lang-option--active' : ''}`}
                    onClick={() => handleLangSelect(entry.code)}
                  >
                    <img
                      className="chat-lang-flag"
                      src={FLAG_BY_LANG[entry.code] || FLAG_BY_LANG.en}
                      alt={`${entry.label} flag`}
                    />
                    <span>{entry.label}</span>
                  </button>
                ))}
              </div>
            </Motion.div>
          </Motion.div>
        )}
      </AnimatePresence>

      <main
        className="chat-body"
        ref={chatContainerRef}
        onWheelCapture={(event) => {
          if (!isLoading && !isStreaming) return
          if (event.deltaY < 0) {
            markUserScrollIntent()
          }
        }}
        onTouchMoveCapture={() => {
          if (!isLoading && !isStreaming) return
          markUserScrollIntent()
        }}
      >
          {!isIntroMode && (
            <div className="chat-vehicle-banner">
              <p>{terminalSystemLabel}</p>
              <h1>{guide.name}</h1>
            </div>
          )}

          <div className={`chat-messages${isIntroMode ? ' chat-messages--empty' : ''}`}>
            <AnimatePresence>
              {messages.length === 0 && !isLoading && (
                <Motion.div
                  className="chat-intro-card"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.45 }}
                >
                  <h2>{t.chat.askFirst}</h2>
                  <p>{formatText(t.chat.askFirstDesc, { vehicle: guide.name })}</p>

                  <div className="chat-suggestions chat-suggestions--inline">
                    {quickQuestions.map((item, index) => (
                      <Motion.button
                        key={item.text}
                        className="suggestion-pill"
                        onClick={() => sendMessage(item.text)}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.22 + (index * 0.08) }}
                        whileHover={{ scale: 1.01 }}
                        whileTap={{ scale: 0.98 }}
                      >
                        <img src={item.icon} alt="" loading="lazy" />
                        <span>{item.text}</span>
                      </Motion.button>
                    ))}
                  </div>
                </Motion.div>
              )}
            </AnimatePresence>

            <AnimatePresence initial={false}>
              {messages.map((msg, index) => {
                const isLastBotStreaming = isStreaming && msg.type === 'bot' && index === messages.length - 1
                return (
                  <Motion.div
                    key={msg.id || `${msg.type}-${index}`}
                    className={`msg ${msg.type}`}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.28 }}
                  >
                    <div className="msg-avatar">
                      <span className="msg-avatar-tag">{msg.type === 'user' ? 'USR' : 'AI'}</span>
                    </div>

                    <div className="msg-bubble">
                      {msg.type === 'bot' ? (
                        isLastBotStreaming ? (
                          <StreamingBotMessage text={msg.content} />
                        ) : (
                          <RichBotMessage
                            text={msg.content}
                            lang={lang}
                            video={msg.video}
                            confidence={msg.confidence}
                            sources={msg.sources}
                          />
                        )
                      ) : msg.content}
                    </div>

                    {msg.type === 'bot' && !isLastBotStreaming && (
                      <button
                        className="msg-copy-btn"
                        onClick={() => {
                          navigator.clipboard.writeText(msg.content || '')
                          showToast(toastCopy.copied || (lang === 'fr' ? 'Copié' : 'Copied'))
                        }}
                        title={lang === 'fr' ? 'Copier' : lang === 'ko' ? '복사' : 'Copy'}
                        aria-label="Copy message"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <rect x="9" y="9" width="13" height="13" rx="2" />
                          <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
                        </svg>
                      </button>
                    )}
                  </Motion.div>
                )
              })}
            </AnimatePresence>

            <AnimatePresence>
              {showFollowUp && (
                <Motion.div
                  className="chat-followup"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.3, delay: 0.4 }}
                >
                  <p className="chat-followup-label">
                    {lang === 'fr' ? 'Une autre question ?' : lang === 'ko' ? '다른 질문이 있으신가요?' : 'Any other questions?'}
                  </p>
                  <div className="chat-followup-pills">
                    {(FOLLOWUP_SUGGESTIONS[lang] || FOLLOWUP_SUGGESTIONS.fr).map((text) => (
                      <button
                        key={text}
                        className="followup-pill"
                        onClick={() => sendMessage(text)}
                      >
                        {text}
                      </button>
                    ))}
                  </div>
                </Motion.div>
              )}
            </AnimatePresence>

            <AnimatePresence>
              {isLoading && !isStreaming && (
                <Motion.div
                  className="msg bot"
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6, transition: { duration: 0.2 } }}
                >
                  <div className="msg-avatar">
                    <span className="msg-avatar-tag">AI</span>
                  </div>
                  <div className="msg-bubble">
                    <ThinkingSteps currentStep={streamStatus} visitedSteps={visitedSteps} lang={lang} />
                  </div>
                </Motion.div>
              )}
            </AnimatePresence>
          </div>

          <AnimatePresence>
            {showScrollBtn && !isIntroMode && (
              <Motion.button
                className="scroll-to-bottom-btn"
                aria-label="Scroll to bottom"
                onClick={() => {
                  chatContainerRef.current?.scrollTo({ top: chatContainerRef.current.scrollHeight, behavior: 'smooth' })
                  userScrolledUpRef.current = false
                  setShowScrollBtn(false)
                }}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </Motion.button>
            )}
          </AnimatePresence>
      </main>

      <footer className="chat-footer">
        <div className="chat-prompt-bar">
          <div className="chat-prompt-glow" />
          <div className="chat-prompt-inner">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(event) => {
                setInput(event.target.value)
                event.target.style.height = 'auto'
                event.target.style.height = Math.min(event.target.scrollHeight, 140) + 'px'
              }}
              onKeyDown={handleKeyDown}
              placeholder={formatText(t.chat.placeholder, { vehicle: guide.name })}
              disabled={isLoading || isStreaming}
              maxLength={MAX_INPUT_LENGTH}
              aria-label={formatText(t.chat.placeholder, { vehicle: guide.name })}
              rows={1}
            />
            <div className="chat-prompt-actions">
              {(isLoading || isStreaming) ? (
                <Motion.button
                  className="chat-action-btn chat-action-btn--stop"
                  onClick={handleStopGeneration}
                  whileHover={{ scale: 1.08 }}
                  whileTap={{ scale: 0.92 }}
                  title={lang === 'fr' ? 'Arrêter' : lang === 'ko' ? '중지' : 'Stop'}
                  aria-label="Stop generation"
                >
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <rect x="3" y="3" width="10" height="10" rx="2" />
                  </svg>
                </Motion.button>
              ) : (
                <Motion.button
                  className="chat-action-btn chat-action-btn--send"
                  onClick={() => sendMessage()}
                  disabled={!input.trim()}
                  whileHover={{ scale: 1.08 }}
                  whileTap={{ scale: 0.92 }}
                  title={t.chat.send}
                  aria-label={t.chat.send}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="12" y1="19" x2="12" y2="5" />
                    <polyline points="5 12 12 5 19 12" />
                  </svg>
                </Motion.button>
              )}
            </div>
          </div>
        </div>
        {isStreaming && streamStatus && (
          <p className="chat-runtime-status">
            {(STREAM_STATUS_LABELS[lang] || STREAM_STATUS_LABELS.en)?.[streamStatus] || ''}
          </p>
        )}
      </footer>

      <AnimatePresence>
        {showExitConfirm && (
          <Motion.div
            className="chat-exit-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closeExitConfirm}
          >
            <Motion.div
              className="chat-exit-popup"
              initial={{ opacity: 0, y: 10, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.98 }}
              transition={{ duration: 0.2 }}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="chat-exit-top">
                <span className="chat-exit-sigil" aria-hidden>{'\u25CE'}</span>
                <p className="chat-exit-kicker">{exitConfirmKicker}</p>
                <h2>{exitConfirmTitle}</h2>
                <p className="chat-exit-text">{exitConfirmText}</p>
              </div>

              <div className="chat-exit-actions">
                <button type="button" className="chat-exit-cancel" onClick={closeExitConfirm}>
                  {exitConfirmCancel}
                </button>
                <button type="button" className="chat-exit-accept" onClick={confirmExitChat}>
                  {exitConfirmAccept}
                </button>
              </div>

              <div className="chat-exit-foot">
                <span>SYS.ID: AURIS-V3</span>
                <span>{exitNodeLabel}: {guide.name}</span>
              </div>
            </Motion.div>
          </Motion.div>
        )}
      </AnimatePresence>
    </Motion.div>
  )
}

export default ChatPage
