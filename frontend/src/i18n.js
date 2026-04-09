import { useEffect, useState } from 'react'

export const LANGUAGE_STORAGE_KEY = 'cc_lang'

export const LANGUAGES = [
  { code: 'fr', label: 'FR', flag: '\uD83C\uDDEB\uD83C\uDDF7' },
  { code: 'en', label: 'EN', flag: '\uD83C\uDDEC\uD83C\uDDE7' },
  { code: 'ko', label: 'KO', flag: '\uD83C\uDDF0\uD83C\uDDF7' },
]

export const FLAG_BY_LANG = {
  fr: '/flags/fr.svg',
  en: '/flags/en.svg',
  ko: '/flags/ko.svg',
}

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
          desc: "Obtenez des réponses précises sur l'entretien, les voyants, les spécifications et l'utilisation.",
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
      subtitle: 'Ouvrez votre assistant personnel.',
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
      brandFilterLabel: 'Filtrer par marque',
      allBrands: 'Toutes',
      modelFilterLabel: 'Choisir le modèle',
      modelFilterPlaceholder: 'Sélectionner un modèle',
      swipeHint: 'Glissez sur mobile ou utilisez les flèches sur tablette et ordinateur.',
      previousModel: 'Modèle précédent',
      nextModel: 'Modèle suivant',
      noBrandMatch: 'Aucun véhicule pour cette marque.',
      brandUnknown: 'Marque non renseignée',
      coverageLabel: 'Versions couvertes : {coverage}',
      exitConfirmTitle: 'Quitter cette page ?',
      exitConfirmText: "Voulez-vous vraiment revenir à l'accueil ?",
      exitConfirmCancel: 'Rester ici',
      exitConfirmAccept: 'Oui, quitter',
      searchPlaceholder: 'Rechercher un vehicule...',
      allSegments: 'Tous',
      segments: {
        citadine: 'Citadine',
        suv: 'SUV',
        berline: 'Berline',
        sportive: 'Sportive',
        classique: 'Classique',
        utilitaire: 'Utilitaire',
        autre: 'Autre',
      },
    },
    chat: {
      guides: 'Guides',
      home: 'Accueil',
      loadingChat: 'Chargement du chat...',
      askFirst: 'Posez votre première question',
      askFirstDesc: "Votre assistant est prêt pour {vehicle}. Posez des questions sur l'entretien, les voyants, l'usage ou les spécifications.",
      placeholder: 'Question sur {vehicle}...',
      unavailable: 'Réponse indisponible.',
      serverUnavailable: 'Connexion serveur indisponible.',
      guideNotFound: 'Guide introuvable',
      guideLoadError: 'Impossible de charger le guide',
      coverageLabel: 'Versions couvertes : {coverage}',
      exitConfirmTitle: 'Terminer ce chat ?',
      exitConfirmText: 'Voulez-vous vraiment quitter cette conversation ?',
      exitConfirmCancel: 'Continuer le chat',
      exitConfirmAccept: 'Oui, quitter',
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
      subtitle: 'Open your personal assistant.',
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
      brandFilterLabel: 'Filter by brand',
      allBrands: 'All',
      modelFilterLabel: 'Choose model',
      modelFilterPlaceholder: 'Select a model',
      swipeHint: 'Swipe on mobile or use arrows on tablet and desktop.',
      previousModel: 'Previous model',
      nextModel: 'Next model',
      noBrandMatch: 'No vehicle for this brand.',
      brandUnknown: 'Unknown brand',
      coverageLabel: 'Covered versions: {coverage}',
      exitConfirmTitle: 'Leave this page?',
      exitConfirmText: 'Are you sure you want to go back home?',
      exitConfirmCancel: 'Stay here',
      exitConfirmAccept: 'Yes, leave',
      searchPlaceholder: 'Search a vehicle...',
      allSegments: 'All',
      segments: {
        citadine: 'City car',
        suv: 'SUV',
        berline: 'Sedan',
        sportive: 'Sports',
        classique: 'Classic',
        utilitaire: 'Utility',
        autre: 'Other',
      },
    },
    chat: {
      guides: 'Guides',
      home: 'Home',
      loadingChat: 'Loading chat...',
      askFirst: 'Ask your first question',
      askFirstDesc: 'Your assistant is ready for {vehicle}. Ask about maintenance, warning lights, usage, or specifications.',
      placeholder: 'Question about {vehicle}...',
      unavailable: 'Response unavailable.',
      serverUnavailable: 'Server connection unavailable.',
      guideNotFound: 'Guide not found',
      guideLoadError: 'Unable to load guide',
      coverageLabel: 'Covered versions: {coverage}',
      exitConfirmTitle: 'End this chat?',
      exitConfirmText: 'Are you sure you want to leave this conversation?',
      exitConfirmCancel: 'Keep chatting',
      exitConfirmAccept: 'Yes, leave',
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
      subtitle: '개인 맞춤 어시스턴트를 열어보세요.',
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
      brandFilterLabel: '브랜드 필터',
      allBrands: '전체',
      modelFilterLabel: '모델 선택',
      modelFilterPlaceholder: '모델을 선택하세요',
      swipeHint: '모바일에서는 스와이프하고 태블릿/데스크톱에서는 화살표를 사용하세요.',
      previousModel: '이전 모델',
      nextModel: '다음 모델',
      noBrandMatch: '해당 브랜드의 차량이 없습니다.',
      brandUnknown: '브랜드 정보 없음',
      coverageLabel: '지원 버전: {coverage}',
      exitConfirmTitle: '이 페이지를 나가시겠습니까?',
      exitConfirmText: '정말로 홈으로 돌아가시겠습니까?',
      exitConfirmCancel: '여기에 머무르기',
      exitConfirmAccept: '예, 나가기',
      searchPlaceholder: '차량 검색...',
      allSegments: '전체',
      segments: {
        citadine: '소형차',
        suv: 'SUV',
        berline: '세단',
        sportive: '스포츠카',
        classique: '클래식',
        utilitaire: '상용차',
        autre: '기타',
      },
    },
    chat: {
      guides: '가이드',
      home: '홈',
      loadingChat: '채팅을 불러오는 중...',
      askFirst: '첫 질문을 입력하세요',
      askFirstDesc: '{vehicle} 어시스턴트가 준비되었습니다. 정비, 경고등, 사용법 또는 제원을 물어보세요.',
      placeholder: '{vehicle}에 대한 질문...',
      unavailable: '응답을 생성할 수 없습니다.',
      serverUnavailable: '서버에 연결할 수 없습니다.',
      guideNotFound: '가이드를 찾을 수 없습니다',
      guideLoadError: '가이드를 불러올 수 없습니다',
      coverageLabel: '지원 버전: {coverage}',
      exitConfirmTitle: '이 채팅을 종료할까요?',
      exitConfirmText: '정말로 이 대화에서 나가시겠습니까?',
      exitConfirmCancel: '채팅 계속',
      exitConfirmAccept: '예, 나가기',
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
