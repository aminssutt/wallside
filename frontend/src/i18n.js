import { useEffect, useState } from 'react'

export const LANGUAGE_STORAGE_KEY = 'cc_lang'

export const LANGUAGES = [
  { code: 'fr', label: 'FR' },
  { code: 'en', label: 'EN' },
  { code: 'ko', label: 'KO' },
]

export const UI_TEXT = {
  fr: {
    landing: {
      subtitle: 'Votre assistant auto qui repond a vos questions basees sur votre manuel.',
      accessChat: 'Acceder au chat',
      features: [
        {
          title: '1. Choisissez votre vehicule',
          desc: 'Selectionnez un guide deja indexe. Aucun upload, aucune attente.',
        },
        {
          title: '2. Posez vos questions',
          desc: 'Obtenez des reponses precises sur entretien, voyants, specs et usage.',
        },
        {
          title: '3. Multilingue',
          desc: 'Discutez en francais, anglais ou coreen.',
        },
      ],
      footerTagline: 'Assistant IA pour manuels de vehicules.',
      loadingGuides: 'Chargement des guides...',
      linkedin: 'LinkedIn',
      github: 'GitHub',
      rights: 'Tous droits reserves.',
    },
    guides: {
      home: 'Accueil',
      title: 'Choisissez votre chat vehicule',
      subtitle: 'Ouvrez un assistant deja entraine sur le manuel.',
      loading: 'Chargement des guides disponibles...',
      loadError: 'Impossible de charger les guides',
      serverError: 'Connexion serveur indisponible',
      retry: 'Reessayer',
      emptyTitle: 'Aucun guide indexe disponible.',
      emptyHint: "Lancez le script d'indexation pour ajouter des manuels.",
      openPreview: 'Ouvrir',
      confirmTitle: 'Confirmer le vehicule',
      confirmText: 'Vous avez selectionne {vehicle}. Voulez-vous ouvrir ce chat ?',
      cancel: 'Annuler',
      confirm: 'Oui, ouvrir le chat',
      loadingAssistant: "Ouverture de l'assistant...",
    },
    chat: {
      guides: 'Guides',
      loadingChat: 'Chargement du chat...',
      askFirst: 'Posez votre premiere question',
      askFirstDesc: 'Votre assistant est pret pour {vehicle}. Posez des questions sur entretien, voyants, usage ou specifications.',
      placeholder: 'Question sur {vehicle}...',
      unavailable: 'Reponse indisponible.',
      serverUnavailable: 'Connexion serveur indisponible.',
      guideNotFound: 'Guide introuvable',
      guideLoadError: 'Impossible de charger le guide',
      send: 'Envoyer',
      quickQuestions: [
        'Comment faire la vidange ?',
        "Quels sont les intervalles d'entretien ?",
        'Ou se trouve le filtre a air ?',
      ],
    },
  },
  en: {
    landing: {
      subtitle: "Your car assistant that answers questions based on your owner's manual.",
      accessChat: 'Access chat',
      features: [
        {
          title: '1. Choose your vehicle',
          desc: 'Select a pre-indexed guide. No upload, no waiting.',
        },
        {
          title: '2. Ask anything',
          desc: 'Get precise answers about maintenance, warnings, specs and usage.',
        },
        {
          title: '3. Multilingual',
          desc: 'Chat in French, English or Korean.',
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
      title: 'Choose your vehicle chat',
      subtitle: 'Open a live assistant already trained on the manual.',
      loading: 'Loading available guides...',
      loadError: 'Unable to load guides',
      serverError: 'Server connection unavailable',
      retry: 'Retry',
      emptyTitle: 'No indexed guides available yet.',
      emptyHint: 'Run the indexing script to add vehicle manuals.',
      openPreview: 'Open',
      confirmTitle: 'Confirm vehicle',
      confirmText: 'You selected {vehicle}. Are you sure you want to open this chat?',
      cancel: 'Cancel',
      confirm: 'Yes, open chat',
      loadingAssistant: 'Loading assistant...',
    },
    chat: {
      guides: 'Guides',
      loadingChat: 'Loading chat...',
      askFirst: 'Ask your first question',
      askFirstDesc: 'Your assistant is ready for {vehicle}. Ask about maintenance, warnings, usage or specs.',
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
      subtitle: "차량 매뉴얼 기반으로 질문에 답하는 자동차 어시스턴트입니다.",
      accessChat: '채팅 시작',
      features: [
        {
          title: '1. 차량 선택',
          desc: '사전 인덱싱된 가이드를 선택하세요. 업로드와 대기 없이 바로 시작합니다.',
        },
        {
          title: '2. 무엇이든 질문',
          desc: '정비, 경고등, 제원, 사용법에 대해 정확한 답변을 받으세요.',
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
      rights: 'All rights reserved.',
    },
    guides: {
      home: '홈',
      title: '차량 채팅 선택',
      subtitle: '매뉴얼로 학습된 어시스턴트를 바로 열어보세요.',
      loading: '사용 가능한 가이드를 불러오는 중...',
      loadError: '가이드를 불러올 수 없습니다',
      serverError: '서버에 연결할 수 없습니다',
      retry: '다시 시도',
      emptyTitle: '인덱싱된 가이드가 아직 없습니다.',
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
        '에어 필터 위치는 어디인가요?',
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
