import { useEffect, useState } from 'react'

export const LANGUAGE_STORAGE_KEY = 'cc_lang'

export const LANGUAGES = [
  { code: 'fr', label: 'FR', flag: '\uD83C\uDDEB\uD83C\uDDF7' },
  { code: 'en', label: 'EN', flag: '\uD83C\uDDEC\uD83C\uDDE7' },
  { code: 'ko', label: 'KO', flag: '\uD83C\uDDF0\uD83C\uDDF7' },
]

export const UI_TEXT = {
  fr: {
    landing: {
      subtitle: 'Votre assistant auto qui répond à vos questions à partir de votre manuel.',
      accessChat: 'Accéder au chat',
      features: [
        {
          title: '1. Choisissez votre véhicule',
          desc: 'Sélectionnez un guide déjà indexé. Aucun import, aucune attente.',
        },
        {
          title: '2. Posez vos questions',
          desc: 'Obtenez des réponses précises sur l\'entretien, les voyants, les spécifications et l\'utilisation.',
        },
        {
          title: '3. Multilingue',
          desc: 'Discutez en français, anglais ou coréen.',
        },
      ],
      footerTagline: 'Assistant IA pour les manuels de véhicules.',
      loadingGuides: 'Chargement des guides...',
      linkedin: 'LinkedIn',
      github: 'GitHub',
      rights: 'Tous droits réservés.',
    },
    guides: {
      home: 'Accueil',
      title: 'Choisissez votre assistant véhicule',
      subtitle: 'Ouvrez un assistant déjà entraîné sur le manuel.',
      loading: 'Chargement des guides disponibles...',
      loadError: 'Impossible de charger les guides',
      serverError: 'Connexion serveur indisponible',
      retry: 'Réessayer',
      emptyTitle: 'Aucun guide indexé disponible.',
      emptyHint: "Lancez le script d'indexation pour ajouter des manuels.",
      openPreview: 'Ouvrir',
      confirmTitle: 'Confirmer le véhicule',
      confirmText: 'Vous avez sélectionné {vehicle}. Voulez-vous ouvrir ce chat ?',
      cancel: 'Annuler',
      confirm: 'Oui, ouvrir le chat',
      loadingAssistant: "Ouverture de l'assistant...",
    },
    chat: {
      guides: 'Guides',
      loadingChat: 'Chargement du chat...',
      askFirst: 'Posez votre première question',
      askFirstDesc: 'Votre assistant est prêt pour {vehicle}. Posez des questions sur l\'entretien, les voyants, l\'usage ou les spécifications.',
      placeholder: 'Question sur {vehicle}...',
      unavailable: 'Réponse indisponible.',
      serverUnavailable: 'Connexion serveur indisponible.',
      guideNotFound: 'Guide introuvable',
      guideLoadError: 'Impossible de charger le guide',
      send: 'Envoyer',
      quickQuestions: [
        'Comment faire la vidange ?',
        "Quels sont les intervalles d'entretien ?",
        'Où se trouve le filtre à air ?',
      ],
    },
  },
  en: {
    landing: {
      subtitle: "Your car assistant answers questions from your owner's manual.",
      accessChat: 'Open chat',
      features: [
        {
          title: '1. Choose your vehicle',
          desc: 'Select a pre-indexed guide. No upload, no waiting.',
        },
        {
          title: '2. Ask your questions',
          desc: 'Get precise answers about maintenance, warning lights, specifications, and usage.',
        },
        {
          title: '3. Multilingual',
          desc: 'Chat in French, English, or Korean.',
        },
      ],
      footerTagline: 'AI assistant for vehicle owner manuals.',
      loadingGuides: 'Loading guides...',
      linkedin: 'LinkedIn',
      github: 'GitHub',
      rights: 'All rights reserved.',
    },
    guides: {
      home: 'Home',
      title: 'Choose your vehicle assistant',
      subtitle: 'Open an assistant already trained on the manual.',
      loading: 'Loading available guides...',
      loadError: 'Unable to load guides',
      serverError: 'Server connection unavailable',
      retry: 'Retry',
      emptyTitle: 'No indexed guides available yet.',
      emptyHint: 'Run the indexing script to add vehicle manuals.',
      openPreview: 'Open',
      confirmTitle: 'Confirm vehicle',
      confirmText: 'You selected {vehicle}. Do you want to open this chat?',
      cancel: 'Cancel',
      confirm: 'Yes, open the chat',
      loadingAssistant: 'Loading assistant...',
    },
    chat: {
      guides: 'Guides',
      loadingChat: 'Loading chat...',
      askFirst: 'Ask your first question',
      askFirstDesc: 'Your assistant is ready for {vehicle}. Ask about maintenance, warning lights, usage, or specifications.',
      placeholder: 'Question about {vehicle}...',
      unavailable: 'Response unavailable.',
      serverUnavailable: 'Server connection unavailable.',
      guideNotFound: 'Guide not found',
      guideLoadError: 'Unable to load guide',
      send: 'Send',
      quickQuestions: [
        'How do I do an oil change?',
        'What are the maintenance intervals?',
        'Where is the air filter located?',
      ],
    },
  },
  ko: {
    landing: {
      subtitle: '차량 매뉴얼을 기반으로 질문에 답하는 자동차 어시스턴트입니다.',
      accessChat: '채팅 시작',
      features: [
        {
          title: '1. 차량 선택',
          desc: '사전 인덱싱된 가이드를 선택하세요. 업로드나 대기 없이 바로 시작할 수 있습니다.',
        },
        {
          title: '2. 질문하기',
          desc: '정비, 경고등, 제원, 사용법에 대한 정확한 답변을 받아보세요.',
        },
        {
          title: '3. 다국어 지원',
          desc: '프랑스어, 영어, 한국어로 대화할 수 있습니다.',
        },
      ],
      footerTagline: '차량 매뉴얼 전용 AI 어시스턴트.',
      loadingGuides: '가이드를 불러오는 중...',
      linkedin: 'LinkedIn',
      github: 'GitHub',
      rights: '모든 권리 보유.',
    },
    guides: {
      home: '홈',
      title: '차량 어시스턴트 선택',
      subtitle: '매뉴얼로 학습된 어시스턴트를 바로 열어보세요.',
      loading: '사용 가능한 가이드를 불러오는 중...',
      loadError: '가이드를 불러올 수 없습니다',
      serverError: '서버에 연결할 수 없습니다',
      retry: '다시 시도',
      emptyTitle: '아직 인덱싱된 가이드가 없습니다.',
      emptyHint: '인덱싱 스크립트를 실행해 차량 매뉴얼을 추가하세요.',
      openPreview: '열기',
      confirmTitle: '차량 확인',
      confirmText: '{vehicle}을(를) 선택했습니다. 이 채팅을 여시겠습니까?',
      cancel: '취소',
      confirm: '네, 채팅 열기',
      loadingAssistant: '어시스턴트를 여는 중...',
    },
    chat: {
      guides: '가이드',
      loadingChat: '채팅을 불러오는 중...',
      askFirst: '첫 질문을 입력하세요',
      askFirstDesc: '{vehicle} 어시스턴트가 준비되었습니다. 정비, 경고등, 사용법, 제원을 물어보세요.',
      placeholder: '{vehicle}에 대한 질문...',
      unavailable: '응답을 생성할 수 없습니다.',
      serverUnavailable: '서버에 연결할 수 없습니다.',
      guideNotFound: '가이드를 찾을 수 없습니다',
      guideLoadError: '가이드를 불러올 수 없습니다',
      send: '전송',
      quickQuestions: [
        '오일 교환은 어떻게 하나요?',
        '정비 주기는 어떻게 되나요?',
        '에어필터 위치는 어디인가요?',
      ],
    },
  },
}

export const getStoredLanguage = () => {
  if (typeof window === 'undefined') return 'fr'
  const stored = window.localStorage.getItem(LANGUAGE_STORAGE_KEY)
  if (stored && LANGUAGES.some((lang) => lang.code === stored)) {
    return stored
  }
  return 'fr'
}

export const formatText = (template, values = {}) => {
  if (typeof template !== 'string') return ''
  return Object.entries(values).reduce((acc, [key, value]) => {
    return acc.replaceAll(`{${key}}`, String(value))
  }, template)
}

export const useAppLanguage = () => {
  const [lang, setLangState] = useState(getStoredLanguage)

  useEffect(() => {
    const onStorage = (event) => {
      if (event.key === LANGUAGE_STORAGE_KEY && event.newValue) {
        if (LANGUAGES.some((entry) => entry.code === event.newValue)) {
          setLangState(event.newValue)
        }
      }
    }

    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  const setLang = (nextLang) => {
    const safeLang = LANGUAGES.some((entry) => entry.code === nextLang) ? nextLang : 'fr'
    setLangState(safeLang)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(LANGUAGE_STORAGE_KEY, safeLang)
    }
  }

  return [lang, setLang]
}
