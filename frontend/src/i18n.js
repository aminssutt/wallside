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

// Ask flow (question first, vehicle only when the answer depends on it).
const ASK_TEXT = {
  fr: {
    title: 'Posez votre question',
    lede: "Décrivez votre problème. Nous vous demandons votre véhicule seulement quand la réponse en dépend.",
    placeholder: 'Comment changer ma batterie ?',
    askAbout: 'Votre question sur la',
    send: 'Envoyer',
    home: 'Accueil',
    change: 'changer',
    myVehicle: 'Mon véhicule :',
    whichVehicle: 'Quel est votre véhicule ?',
    whichModel: 'Quel modèle de',
    whichVersion: 'Quelle version exactement ?',
    orSearch: 'Choisissez ci-dessous ou cherchez votre modèle.',
    searchPlaceholder: 'Rechercher un véhicule…',
    allVehicles: 'Tous les véhicules',
    brandVehicles: 'Véhicules',
    noManualSource: 'Réponse générale : aucun passage du manuel ne traite ce point.',
    noMatch: 'Aucun véhicule ne correspond. Essayez la marque ou le modèle.',
    noManualForBrand: ": nous n'avons pas encore ce manuel.",
    browseCatalog: 'Voir les véhicules disponibles dans le',
    catalog: 'catalogue',
    switchedTo: 'Je passe au manuel de la',
    sources: 'Sources',
    page: 'page',
    thinking: 'Recherche dans le manuel…',
    streamError: "La réponse n'a pas pu être générée. Réessayez dans un instant.",
    close: 'Fermer',
    suggestions: [
      'Comment changer ma batterie ?',
      'Que signifie le voyant moteur ?',
      'Quelle pression pour les pneus de ma Peugeot 208 ?',
    ],
  },
  en: {
    title: 'Ask your question',
    lede: 'Describe your problem. We only ask which vehicle you have when the answer depends on it.',
    placeholder: 'How do I change my battery?',
    askAbout: 'Your question about the',
    send: 'Send',
    home: 'Home',
    change: 'change',
    myVehicle: 'My vehicle:',
    whichVehicle: 'Which vehicle do you have?',
    whichModel: 'Which model of',
    whichVersion: 'Which version exactly?',
    orSearch: 'Pick one below or search for your model.',
    searchPlaceholder: 'Search for a vehicle…',
    allVehicles: 'All vehicles',
    brandVehicles: 'Vehicles',
    noManualSource: 'General answer: no passage of the manual covers this point.',
    noMatch: 'No vehicle matches. Try the brand or the model.',
    noManualForBrand: ': we do not have that manual yet.',
    browseCatalog: 'Browse the available vehicles in the',
    catalog: 'catalog',
    switchedTo: 'Switching to the manual of the',
    sources: 'Sources',
    page: 'page',
    thinking: 'Searching the manual…',
    streamError: 'The answer could not be generated. Please try again.',
    close: 'Close',
    suggestions: [
      'How do I change my battery?',
      'What does the engine warning light mean?',
      'What is the tire pressure on my Peugeot 208?',
    ],
  },
  ko: {
    title: '\uC9C8\uBB38\uC744 \uC785\uB825\uD558\uC138\uC694',
    lede: '\uBB38\uC81C\uB97C \uC124\uBA85\uD574 \uC8FC\uC138\uC694. \uB2F5\uBCC0\uC5D0 \uD544\uC694\uD560 \uB54C\uB9CC \uCC28\uB7C9\uC744 \uC5EC\uCB64\uBD05\uB2C8\uB2E4.',
    placeholder: '\uBC30\uD130\uB9AC\uB97C \uC5B4\uB5BB\uAC8C \uAD50\uCCB4\uD558\uB098\uC694?',
    askAbout: '\uC9C8\uBB38 \u00B7',
    send: '\uBCF4\uB0B4\uAE30',
    home: '\uD648',
    change: '\uBCC0\uACBD',
    myVehicle: '\uB0B4 \uCC28\uB7C9:',
    whichVehicle: '\uC5B4\uB5A4 \uCC28\uB7C9\uC744 \uD0C0\uC2DC\uB098\uC694?',
    whichModel: '\uC5B4\uB5A4 \uBAA8\uB378\uC778\uAC00\uC694 \u00B7',
    whichVersion: '\uC815\uD655\uD55C \uBC84\uC804\uC740 \uBB34\uC5C7\uC778\uAC00\uC694?',
    orSearch: '\uC544\uB798\uC5D0\uC11C \uC120\uD0DD\uD558\uAC70\uB098 \uBAA8\uB378\uC744 \uAC80\uC0C9\uD558\uC138\uC694.',
    searchPlaceholder: '\uCC28\uB7C9 \uAC80\uC0C9\u2026',
    allVehicles: '\uBAA8\uB4E0 \uCC28\uB7C9',
    brandVehicles: '\uCC28\uB7C9',
    noManualSource: '\uC77C\uBC18 \uB2F5\uBCC0: \uB9E4\uB274\uC5BC\uC5D0 \uD574\uB2F9 \uB0B4\uC6A9\uC774 \uC5C6\uC2B5\uB2C8\uB2E4.',
    noMatch: '\uC77C\uCE58\uD558\uB294 \uCC28\uB7C9\uC774 \uC5C6\uC2B5\uB2C8\uB2E4.',
    noManualForBrand: ': \uD574\uB2F9 \uB9E4\uB274\uC5BC\uC774 \uC544\uC9C1 \uC5C6\uC2B5\uB2C8\uB2E4.',
    browseCatalog: '\uC0AC\uC6A9 \uAC00\uB2A5\uD55C \uCC28\uB7C9\uC740 \uC5EC\uAE30\uC5D0\uC11C:',
    catalog: '\uCE74\uD0C8\uB85C\uADF8',
    switchedTo: '\uB2E4\uC74C \uB9E4\uB274\uC5BC\uB85C \uC804\uD658\uD569\uB2C8\uB2E4:',
    sources: '\uCD9C\uCC98',
    page: '\uD398\uC774\uC9C0',
    thinking: '\uB9E4\uB274\uC5BC \uAC80\uC0C9 \uC911\u2026',
    streamError: '\uB2F5\uBCC0\uC744 \uC0DD\uC131\uD558\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4. \uB2E4\uC2DC \uC2DC\uB3C4\uD574 \uC8FC\uC138\uC694.',
    close: '\uB2EB\uAE30',
    suggestions: [
      '\uBC30\uD130\uB9AC\uB97C \uC5B4\uB5BB\uAC8C \uAD50\uCCB4\uD558\uB098\uC694?',
      '\uC5D4\uC9C4 \uACBD\uACE0\uB4F1\uC740 \uBB34\uC5C7\uC744 \uC758\uBBF8\uD558\uB098\uC694?',
      '\uD0C0\uC774\uC5B4 \uACF5\uAE30\uC555\uC740 \uC5BC\uB9C8\uC778\uAC00\uC694?',
    ],
  },
}

for (const code of Object.keys(UI_TEXT)) {
  UI_TEXT[code].ask = ASK_TEXT[code] || ASK_TEXT.fr
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
