import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion as Motion, AnimatePresence, useInView } from 'framer-motion';
import { LANGUAGES, useAppLanguage } from '../i18n';
import './LandingPage.css';

/* ============================================================
   Translations
   ============================================================ */

const FLAG_BY_LANG = {
  fr: '/flags/fr.svg',
  en: '/flags/en.svg',
  ko: '/flags/ko.svg',
};

const COPY = {
  fr: {
    navFeatures: 'Fonctionnalites',
    navPricing: 'Tarifs',
    navFaq: 'FAQ',
    navContact: 'Contact',
    heroTitle: 'Mechora',
    heroSubtitle: 'Votre assistant technique automobile intelligent',
    heroStats: ['130+ véhicules', 'Manuels officiels', 'Réponses instantanées'],
    ctaPrimary: 'Commencer gratuitement',
    ctaSecondary: 'En savoir plus',
    featuresLabel: 'Fonctionnalités',
    featuresTitle: 'Tout ce dont vous avez besoin',
    features: [
      { title: 'Manuels officiels', desc: "Accès aux notices d'utilisation de 30+ marques automobiles." },
      { title: 'IA conversationnelle', desc: 'Posez vos questions en langage naturel et obtenez des réponses claires.' },
      { title: 'Sources vérifiées', desc: 'Chaque réponse cite la page exacte du manuel technique.' },
      { title: 'Multilingue', desc: 'Disponible en français, anglais et coréen.' },
    ],
    howLabel: 'Comment ça marche',
    howTitle: 'Simple comme 1, 2, 3',
    howSteps: [
      { title: 'Choisissez votre véhicule', desc: 'Sélectionnez parmi 130+ modèles disponibles.' },
      { title: 'Posez votre question', desc: 'Décrivez votre problème en langage naturel.' },
      { title: 'Obtenez une réponse sourcée', desc: 'Recevez une réponse avec les pages exactes du manuel.' },
    ],
    pricingLabel: 'Tarifs',
    pricingTitle: 'Choisissez votre formule',
    freePlan: {
      badge: 'GRATUIT',
      name: 'Gratuit',
      price: '0\u20AC / mois',
      features: ['10 questions par jour', '30+ marques disponibles', 'Sources du manuel', 'Publicités'],
      cta: 'Commencer gratuitement',
    },
    premiumPlan: {
      badge: 'PREMIUM',
      name: 'Premium',
      price: '9.99\u20AC / mois',
      features: ['Questions illimitées', 'Sans publicités', 'Sources PDF directes', 'Vidéo YouTube', 'Support prioritaire'],
      cta: 'Passer Premium',
    },
    faqLabel: 'FAQ',
    faqTitle: 'Questions fréquentes',
    faq: [
      { q: 'Comment ça marche ?', a: "L'IA analyse le manuel officiel de votre véhicule pour vous fournir des réponses précises et sourcées. Sélectionnez votre modèle, posez votre question, et obtenez une réponse avec les références exactes du manuel." },
      { q: 'Les réponses sont-elles fiables ?', a: 'Oui, chaque réponse cite la page exacte du manuel officiel du constructeur. Vous pouvez vérifier chaque information directement dans le document source.' },
      { q: 'Quels véhicules sont disponibles ?', a: 'Plus de 130 véhicules de 30+ marques sont disponibles, incluant les principales marques européennes, japonaises et coréennes.' },
      { q: "C'est gratuit ?", a: "Oui, la version gratuite donne accès à 10 questions par jour avec les sources du manuel. La version Premium offre un accès illimité sans publicités." },
      { q: 'Comment devenir Premium ?', a: "Cliquez sur \"Passer Premium\" pour un accès illimité à toutes les fonctionnalités, sans publicités et avec le support prioritaire." },
    ],
    aboutLabel: 'À propos',
    aboutName: 'Lakhdar Berache',
    aboutRole: 'Créateur de Mechora',
    aboutBio: "Passionn\u00e9 d'automobile et \u00e9tudiant en \u00e9cole d'ing\u00e9nieur, j'ai cr\u00e9\u00e9 Mechora apr\u00e8s un stage en ing\u00e9nierie automobile. Mon objectif : rendre l'information technique automobile accessible \u00e0 tous, gratuitement. Chaque r\u00e9ponse est sourc\u00e9e directement depuis les manuels officiels des constructeurs.",
    contactLabel: 'Contact',
    contactTitle: 'Contactez-nous',
    contactSubtitle: 'Une question, une suggestion, ou un partenariat ?',
    contactName: 'Nom',
    contactEmail: 'Email',
    contactMessage: 'Message',
    contactSend: 'Envoyer',
    chatDemoUser: 'Comment changer les plaquettes de frein sur ma Peugeot 308 ?',
    chatDemoAi: "Pour remplacer les plaquettes de frein de votre Peugeot 308 (2022):\n\n**Outils nécessaires**: Cric, clé de 13mm, repousse-piston\n\n**Étapes**:\n1. Soulevez le véhicule et retirez la roue\n2. Dévissez les deux boulons de l'étrier...",
    chatDemoSource: 'Sources: Manuel Peugeot 308, page 142',
    statsVehicles: 'véhicules',
    statsBrands: 'marques',
    statsPages: 'pages analysées',
    statsLangs: 'langues',
    enterprisePlan: {
      badge: 'ENTREPRISE',
      name: 'Entreprise',
      subtitle: 'Sur devis',
      features: [
        'Accès illimité pour toute l\'équipe',
        'Intégration API dédiée',
        'Support prioritaire 24/7',
        'Manuels personnalisés',
        'Tableau de bord analytics',
        'Partenariats constructeurs',
      ],
      cta: 'Nous contacter',
    },
    footerBio: 'Créé par Lakhdar Berache. Étudiant ingénieur, passionné d\'automobile.',
    footerNavTitle: 'Navigation',
    footerResTitle: 'Ressources',
    footerContactTitle: 'Contact',
    footerGuides: 'Guides véhicules',
    footerFaq: 'FAQ',
    footerContact: 'Contact',
    footerAbout: 'À propos',
    footerFeatures: 'Fonctionnalités',
    footerPricing: 'Tarifs',
    footerTerms: 'Conditions d\'utilisation',
    footerPrivacy: 'Politique de confidentialité',
  },
  en: {
    navFeatures: 'Features',
    navPricing: 'Pricing',
    navFaq: 'FAQ',
    navContact: 'Contact',
    heroTitle: 'Mechora',
    heroSubtitle: 'Your intelligent automotive technical assistant',
    heroStats: ['130+ vehicles', 'Official manuals', 'Instant answers'],
    ctaPrimary: 'Start for free',
    ctaSecondary: 'Learn more',
    featuresLabel: 'Features',
    featuresTitle: 'Everything you need',
    features: [
      { title: 'Official manuals', desc: "Access owner's manuals from 30+ automotive brands." },
      { title: 'Conversational AI', desc: 'Ask your questions in natural language and get clear answers.' },
      { title: 'Verified sources', desc: 'Every answer cites the exact page from the technical manual.' },
      { title: 'Multilingual', desc: 'Available in French, English, and Korean.' },
    ],
    howLabel: 'How it works',
    howTitle: 'Simple as 1, 2, 3',
    howSteps: [
      { title: 'Choose your vehicle', desc: 'Select from 130+ available models.' },
      { title: 'Ask your question', desc: 'Describe your issue in natural language.' },
      { title: 'Get a sourced answer', desc: 'Receive an answer with exact manual page references.' },
    ],
    pricingLabel: 'Pricing',
    pricingTitle: 'Choose your plan',
    freePlan: {
      badge: 'FREE',
      name: 'Free',
      price: '\u20AC0 / month',
      features: ['10 questions per day', '30+ brands available', 'Manual sources', 'Advertisements'],
      cta: 'Start for free',
    },
    premiumPlan: {
      badge: 'PREMIUM',
      name: 'Premium',
      price: '\u20AC9.99 / month',
      features: ['Unlimited questions', 'No advertisements', 'Direct PDF sources', 'YouTube videos', 'Priority support'],
      cta: 'Go Premium',
    },
    faqLabel: 'FAQ',
    faqTitle: 'Frequently asked questions',
    faq: [
      { q: 'How does it work?', a: "The AI analyzes your vehicle's official manual to provide precise, sourced answers. Select your model, ask your question, and get an answer with exact manual references." },
      { q: 'Are the answers reliable?', a: "Yes, every answer cites the exact page from the manufacturer's official manual. You can verify each piece of information directly in the source document." },
      { q: 'Which vehicles are available?', a: 'Over 130 vehicles from 30+ brands are available, including major European, Japanese, and Korean manufacturers.' },
      { q: 'Is it free?', a: 'Yes, the free version gives access to 10 questions per day with manual sources. The Premium version offers unlimited access without ads.' },
      { q: 'How to become Premium?', a: 'Click "Go Premium" for unlimited access to all features, no ads, and priority support.' },
    ],
    aboutLabel: 'About',
    aboutName: 'Lakhdar Berache',
    aboutRole: 'Creator of Mechora',
    aboutBio: 'Passionate about cars and studying engineering, I created Mechora after an automotive engineering internship. My goal: make technical automotive information accessible to everyone, for free. Every answer is sourced directly from official manufacturer manuals.',
    contactLabel: 'Contact',
    contactTitle: 'Contact us',
    contactSubtitle: 'A question, a suggestion, or a partnership?',
    contactName: 'Name',
    contactEmail: 'Email',
    contactMessage: 'Message',
    contactSend: 'Send',
    chatDemoUser: 'How to change the brake pads on my Peugeot 308?',
    chatDemoAi: "To replace the brake pads on your Peugeot 308 (2022):\n\n**Tools needed**: Jack, 13mm wrench, piston compressor\n\n**Steps**:\n1. Raise the vehicle and remove the wheel\n2. Unscrew the two caliper bolts...",
    chatDemoSource: 'Sources: Peugeot 308 Manual, page 142',
    statsVehicles: 'vehicles',
    statsBrands: 'brands',
    statsPages: 'pages analyzed',
    statsLangs: 'languages',
    enterprisePlan: {
      badge: 'ENTERPRISE',
      name: 'Enterprise',
      subtitle: 'Custom pricing',
      features: [
        'Unlimited access for the whole team',
        'Dedicated API integration',
        '24/7 priority support',
        'Custom manuals',
        'Analytics dashboard',
        'Manufacturer partnerships',
      ],
      cta: 'Contact us',
    },
    footerBio: 'Created by Lakhdar Berache. Engineering student, passionate about cars.',
    footerNavTitle: 'Navigation',
    footerResTitle: 'Resources',
    footerContactTitle: 'Contact',
    footerGuides: 'Vehicle guides',
    footerFaq: 'FAQ',
    footerContact: 'Contact',
    footerAbout: 'About',
    footerFeatures: 'Features',
    footerPricing: 'Pricing',
    footerTerms: 'Terms of use',
    footerPrivacy: 'Privacy policy',
  },
  ko: {
    navFeatures: '기능',
    navPricing: '요금',
    navFaq: 'FAQ',
    navContact: '문의',
    heroTitle: 'Mechora',
    heroSubtitle: '당신의 지능형 자동차 기술 어시스턴트',
    heroStats: ['130+ 차량', '공식 매뉴얼', '즉각적인 답변'],
    ctaPrimary: '무료로 시작하기',
    ctaSecondary: '자세히 보기',
    featuresLabel: '기능',
    featuresTitle: '필요한 모든 것',
    features: [
      { title: '공식 매뉴얼', desc: '30개 이상의 자동차 브랜드 사용 설명서에 접근하세요.' },
      { title: '대화형 AI', desc: '자연어로 질문하고 명확한 답변을 받으세요.' },
      { title: '검증된 출처', desc: '모든 답변은 기술 매뉴얼의 정확한 페이지를 인용합니다.' },
      { title: '다국어 지원', desc: '프랑스어, 영어, 한국어로 이용 가능합니다.' },
    ],
    howLabel: '이용 방법',
    howTitle: '간단한 3단계',
    howSteps: [
      { title: '차량 선택', desc: '130개 이상의 모델 중 선택하세요.' },
      { title: '질문하기', desc: '자연어로 문제를 설명하세요.' },
      { title: '출처가 포함된 답변 받기', desc: '매뉴얼 페이지 참조가 포함된 답변을 받으세요.' },
    ],
    pricingLabel: '요금',
    pricingTitle: '플랜을 선택하세요',
    freePlan: {
      badge: '무료',
      name: '무료',
      price: '월 \u20AC0',
      features: ['하루 10개 질문', '30+ 브랜드', '매뉴얼 출처', '광고 포함'],
      cta: '무료로 시작',
    },
    premiumPlan: {
      badge: '프리미엄',
      name: '프리미엄',
      price: '월 \u20AC9.99',
      features: ['무제한 질문', '광고 없음', 'PDF 직접 출처', 'YouTube 동영상', '우선 지원'],
      cta: '프리미엄으로 전환',
    },
    faqLabel: 'FAQ',
    faqTitle: '자주 묻는 질문',
    faq: [
      { q: '어떻게 작동하나요?', a: 'AI가 차량의 공식 매뉴얼을 분석하여 정확하고 출처가 있는 답변을 제공합니다. 모델을 선택하고 질문하면 매뉴얼 참조가 포함된 답변을 받습니다.' },
      { q: '답변이 신뢰할 수 있나요?', a: '네, 모든 답변은 제조사 공식 매뉴얼의 정확한 페이지를 인용합니다. 원본 문서에서 직접 확인할 수 있습니다.' },
      { q: '어떤 차량이 이용 가능한가요?', a: '유럽, 일본, 한국 주요 제조사를 포함한 30개 이상 브랜드의 130개 이상 차량이 이용 가능합니다.' },
      { q: '무료인가요?', a: '네, 무료 버전은 하루 10개 질문과 매뉴얼 출처를 제공합니다. 프리미엄 버전은 광고 없이 무제한 이용이 가능합니다.' },
      { q: '프리미엄은 어떻게 이용하나요?', a: '"프리미엄으로 전환"을 클릭하면 모든 기능에 무제한 접근, 광고 없음, 우선 지원을 받을 수 있습니다.' },
    ],
    aboutLabel: '소개',
    aboutName: 'Lakhdar Berache',
    aboutRole: 'Mechora 제작자',
    aboutBio: '자동차에 대한 열정과 공학을 공부하면서, 자동차 엔지니어링 인턴십 후에 Mechora를 만들었습니다. 목표: 기술적인 자동차 정보를 모두에게 무료로 제공하는 것입니다.',
    contactLabel: '문의',
    contactTitle: '문의하기',
    contactSubtitle: '질문, 제안 또는 파트너십이 있으신가요?',
    contactName: '이름',
    contactEmail: '이메일',
    contactMessage: '메시지',
    contactSend: '보내기',
    chatDemoUser: '푸조 308의 브레이크 패드를 어떻게 교체하나요?',
    chatDemoAi: "푸조 308 (2022)의 브레이크 패드 교체:\n\n**필요 도구**: 잭, 13mm 렌치, 피스톤 압축기\n\n**단계**:\n1. 차량을 들어올리고 바퀴를 제거합니다\n2. 캘리퍼 볼트 두 개를 풀어주세요...",
    chatDemoSource: '출처: 푸조 308 매뉴얼, 142페이지',
    statsVehicles: '차량',
    statsBrands: '브랜드',
    statsPages: '분석된 페이지',
    statsLangs: '언어',
    enterprisePlan: {
      badge: '기업',
      name: '기업',
      subtitle: '맞춤 가격',
      features: [
        '팀 전체 무제한 접근',
        '전용 API 통합',
        '24/7 우선 지원',
        '맞춤형 매뉴얼',
        '분석 대시보드',
        '제조사 파트너십',
      ],
      cta: '문의하기',
    },
    footerBio: 'Lakhdar Berache가 제작. 공학 학생, 자동차 열정가.',
    footerNavTitle: '탐색',
    footerResTitle: '리소스',
    footerContactTitle: '연락처',
    footerGuides: '차량 가이드',
    footerFaq: 'FAQ',
    footerContact: '문의',
    footerAbout: '소개',
    footerFeatures: '기능',
    footerPricing: '요금',
    footerTerms: '이용 약관',
    footerPrivacy: '개인정보 처리방침',
  },
};

/* ============================================================
   SVG Icon Components
   ============================================================ */

const IconBook = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    <line x1="8" y1="7" x2="16" y2="7" />
    <line x1="8" y1="11" x2="13" y2="11" />
  </svg>
);

const IconChat = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);

const IconShield = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    <polyline points="9 12 11 14 15 10" />
  </svg>
);

const IconGlobe = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <line x1="2" y1="12" x2="22" y2="12" />
    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
  </svg>
);

const IconCheck = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const IconPlus = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

const IconArrowRight = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="5" y1="12" x2="19" y2="12" />
    <polyline points="12 5 19 12 12 19" />
  </svg>
);

const IconChevronDown = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="6 9 12 15 18 9" />
  </svg>
);

const IconSend = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13" />
    <polygon points="22 2 15 22 11 13 2 9 22 2" />
  </svg>
);

const IconSparkle = () => (
  <svg viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2L13.09 8.26L18 6L14.74 10.91L21 12L14.74 13.09L18 18L13.09 15.74L12 22L10.91 15.74L6 18L9.26 13.09L3 12L9.26 10.91L6 6L10.91 8.26L12 2Z" />
  </svg>
);

const FEATURE_ICONS = [IconBook, IconChat, IconShield, IconGlobe];

/* ============================================================
   Animation Variants
   ============================================================ */

const fadeInUp = {
  hidden: { opacity: 0, y: 30, filter: 'blur(4px)' },
  visible: { opacity: 1, y: 0, filter: 'blur(0px)', transition: { duration: 0.7, ease: [0.25, 0.1, 0.25, 1] } },
};

const fadeIn = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.8, ease: 'easeOut' } },
};

const stagger = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.1, delayChildren: 0.1 } },
};

const scaleIn = {
  hidden: { opacity: 0, scale: 0.92, filter: 'blur(8px)' },
  visible: { opacity: 1, scale: 1, filter: 'blur(0px)', transition: { duration: 0.9, ease: [0.25, 0.1, 0.25, 1] } },
};

const slideInRight = {
  hidden: { opacity: 0, x: 60, filter: 'blur(6px)' },
  visible: { opacity: 1, x: 0, filter: 'blur(0px)', transition: { duration: 0.9, delay: 0.3, ease: [0.25, 0.1, 0.25, 1] } },
};

/* ============================================================
   Word-by-word blur reveal
   ============================================================ */

function WordReveal({ text, baseDelay = 0, className = '' }) {
  const words = text.split(' ');
  return (
    <span className={`word-reveal ${className}`}>
      {words.map((word, i) => (
        <Motion.span
          key={i}
          className="word-reveal__word"
          initial={{ opacity: 0, filter: 'blur(10px)', y: 12 }}
          animate={{ opacity: 1, filter: 'blur(0px)', y: 0 }}
          transition={{ duration: 0.5, delay: baseDelay + i * 0.07, ease: [0.25, 0.1, 0.25, 1] }}
        >
          {word}
        </Motion.span>
      ))}
    </span>
  );
}

/* ============================================================
   Animated Counter (stats section)
   ============================================================ */

function AnimatedCounter({ target, suffix = '', duration = 2000 }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, amount: 0.5 });
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!inView) return;
    let start = 0;
    const step = Math.max(1, Math.floor(target / (duration / 16)));
    const timer = setInterval(() => {
      start += step;
      if (start >= target) {
        setCount(target);
        clearInterval(timer);
      } else {
        setCount(start);
      }
    }, 16);
    return () => clearInterval(timer);
  }, [inView, target, duration]);

  return (
    <span ref={ref} className="stat-number">
      {count.toLocaleString()}{suffix}
    </span>
  );
}

/* ============================================================
   Chat Demo (hero animated conversation)
   ============================================================ */

function ChatDemo({ userMsg, aiMsg, sourceMsg }) {
  const TYPING_SPEED = 28;
  const PAUSE_BEFORE_AI = 800;
  const PAUSE_BEFORE_SOURCE = 600;
  const LOOP_DELAY = 5000;

  const [phase, setPhase] = useState('user');
  const [charIndex, setCharIndex] = useState(0);
  const [showSource, setShowSource] = useState(false);
  const [showUser, setShowUser] = useState(false);

  const resetCycle = useCallback(() => {
    setPhase('user');
    setCharIndex(0);
    setShowSource(false);
    setShowUser(false);
  }, []);

  useEffect(() => {
    resetCycle();
  }, [userMsg, aiMsg, sourceMsg, resetCycle]);

  useEffect(() => {
    let timeout;
    if (phase === 'user') {
      timeout = setTimeout(() => {
        setShowUser(true);
        setPhase('pause');
      }, 400);
    } else if (phase === 'pause') {
      timeout = setTimeout(() => setPhase('typing'), PAUSE_BEFORE_AI);
    } else if (phase === 'typing') {
      if (charIndex < aiMsg.length) {
        timeout = setTimeout(() => setCharIndex((i) => i + 1), TYPING_SPEED);
      } else {
        timeout = setTimeout(() => {
          setShowSource(true);
          setPhase('done');
        }, PAUSE_BEFORE_SOURCE);
      }
    } else if (phase === 'done') {
      timeout = setTimeout(() => resetCycle(), LOOP_DELAY);
    }
    return () => clearTimeout(timeout);
  }, [phase, charIndex, aiMsg, resetCycle]);

  const formatAiText = (text) => {
    return text.split('\n').map((line, i) => {
      const boldParts = line.split(/(\*\*[^*]+\*\*)/g);
      return (
        <React.Fragment key={i}>
          {i > 0 && <br />}
          {boldParts.map((part, j) =>
            part.startsWith('**') && part.endsWith('**')
              ? <strong key={j}>{part.slice(2, -2)}</strong>
              : part
          )}
        </React.Fragment>
      );
    });
  };

  return (
    <div className="chat-demo">
      <div className="chat-demo__header">
        <div className="chat-demo__dots">
          <span /><span /><span />
        </div>
        <img src="/mechora-writing.png" alt="Mechora" className="chat-demo__logo" />
      </div>
      <div className="chat-demo__body">
        {showUser && (
          <Motion.div
            className="chat-demo__msg chat-demo__msg--user"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <span className="chat-demo__label">Vous</span>
            <p>{userMsg}</p>
          </Motion.div>
        )}
        {(phase === 'typing' || phase === 'done') && (
          <Motion.div
            className="chat-demo__msg chat-demo__msg--ai"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <span className="chat-demo__label">Mechora AI</span>
            <p>{formatAiText(aiMsg.slice(0, charIndex))}</p>
            {phase === 'typing' && <span className="chat-demo__cursor" />}
          </Motion.div>
        )}
        {showSource && (
          <Motion.div
            className="chat-demo__source"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            <IconSparkle />
            {sourceMsg}
          </Motion.div>
        )}
      </div>
    </div>
  );
}

/* ============================================================
   How-step preview illustrations
   ============================================================ */

const HowPreviewBrands = () => (
  <div className="how-preview how-preview--brands">
    {['Peugeot', 'BMW', 'Toyota', 'Hyundai', 'Audi', 'Renault'].map((b) => (
      <div key={b} className="how-preview__brand">{b.slice(0, 2).toUpperCase()}</div>
    ))}
  </div>
);

const HowPreviewQuestion = () => (
  <div className="how-preview how-preview--question">
    <div className="how-preview__input">
      <span className="how-preview__placeholder">Comment changer...</span>
      <span className="how-preview__send-icon"><IconSend /></span>
    </div>
  </div>
);

const HowPreviewAnswer = () => (
  <div className="how-preview how-preview--answer">
    <div className="how-preview__line how-preview__line--title" />
    <div className="how-preview__line how-preview__line--text" />
    <div className="how-preview__line how-preview__line--text how-preview__line--short" />
    <div className="how-preview__source-tag">p.142</div>
  </div>
);

const HOW_PREVIEWS = [HowPreviewBrands, HowPreviewQuestion, HowPreviewAnswer];

/* ============================================================
   Main Component
   ============================================================ */

export default function LandingPage() {
  const navigate = useNavigate();
  const [lang, setLang] = useAppLanguage();
  const t = COPY[lang] || COPY.fr;

  const [langOpen, setLangOpen] = useState(false);
  const [navScrolled, setNavScrolled] = useState(false);
  const [openFaq, setOpenFaq] = useState(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const langDropdownRef = useRef(null);

  const currentLang = LANGUAGES.find((entry) => entry.code === lang) || LANGUAGES[0];

  useEffect(() => {
    document.body.style.overflow = 'auto';
    document.documentElement.style.overflow = 'auto';
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  }, []);

  useEffect(() => {
    const handleScroll = () => setNavScrolled(window.scrollY > 40);
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    if (!langOpen) return undefined;
    const handleOutsideClick = (event) => {
      if (langDropdownRef.current && !langDropdownRef.current.contains(event.target)) {
        setLangOpen(false);
      }
    };
    const handleEscape = (event) => {
      if (event.key === 'Escape') setLangOpen(false);
    };
    document.addEventListener('mousedown', handleOutsideClick);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [langOpen]);

  const scrollTo = (id) => {
    const el = document.getElementById(id);
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    setMobileMenuOpen(false);
  };

  const goToGuides = () => navigate('/guides');

  const handleContactSubmit = (e) => {
    e.preventDefault();
    const form = e.target;
    const name = form.elements.name.value;
    const email = form.elements.email.value;
    const message = form.elements.message.value;
    const subject = encodeURIComponent(`Mechora Contact - ${name}`);
    const body = encodeURIComponent(`From: ${name}\nEmail: ${email}\n\n${message}`);
    window.location.href = `mailto:lakhdarberache@gmail.com?subject=${subject}&body=${body}`;
  };

  const handleCardSpotlight = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    e.currentTarget.style.setProperty('--spot-x', `${e.clientX - rect.left}px`);
    e.currentTarget.style.setProperty('--spot-y', `${e.clientY - rect.top}px`);
  };

  return (
    <main className="landing">

      {/* ======== NAVIGATION ======== */}
      <nav className={`nav${navScrolled ? ' nav--scrolled' : ''}`}>
        <div className="nav__inner">
          <button type="button" className="nav__brand" onClick={() => navigate('/')} aria-label="Home">
            <img className="nav__logo" src="/logo-mechora.png" alt="Mechora" />
          </button>

          <ul className="nav__links">
            <li><button type="button" onClick={() => scrollTo('features')}>{t.navFeatures}</button></li>
            <li><button type="button" onClick={() => scrollTo('pricing')}>{t.navPricing}</button></li>
            <li><button type="button" onClick={() => scrollTo('faq')}>{t.navFaq}</button></li>
            <li><button type="button" onClick={() => scrollTo('contact')}>{t.navContact}</button></li>
          </ul>

          <div className="nav__right">
            {/* Language Dropdown */}
            <div className="lang-dropdown" ref={langDropdownRef}>
              <button
                type="button"
                className="lang-btn"
                onClick={() => setLangOpen((prev) => !prev)}
                aria-expanded={langOpen}
                aria-haspopup="menu"
              >
                <img className="lang-flag" src={FLAG_BY_LANG[currentLang?.code] || FLAG_BY_LANG.fr} alt={`${currentLang?.label || 'FR'} flag`} />
                <span className="lang-code">{currentLang?.label}</span>
                <IconChevronDown />
              </button>

              <AnimatePresence>
                {langOpen && (
                  <Motion.div
                    className="lang-menu"
                    initial={{ opacity: 0, y: -6, scale: 0.97 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -6, scale: 0.97 }}
                    transition={{ duration: 0.15 }}
                  >
                    {LANGUAGES.map((entry) => (
                      <button
                        key={entry.code}
                        type="button"
                        className={`lang-menu__item${entry.code === lang ? ' active' : ''}`}
                        onClick={() => { setLang(entry.code); setLangOpen(false); }}
                      >
                        <img className="lang-flag" src={FLAG_BY_LANG[entry.code] || FLAG_BY_LANG.fr} alt={`${entry.label} flag`} />
                        <span className="lang-code">{entry.label}</span>
                      </button>
                    ))}
                  </Motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Mobile menu toggle */}
            <button
              type="button"
              className="nav__mobile-toggle"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label="Menu"
            >
              <span className={`hamburger${mobileMenuOpen ? ' hamburger--open' : ''}`}>
                <span /><span /><span />
              </span>
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        <AnimatePresence>
          {mobileMenuOpen && (
            <Motion.div
              className="nav__mobile-menu"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.25 }}
            >
              <button type="button" onClick={() => scrollTo('features')}>{t.navFeatures}</button>
              <button type="button" onClick={() => scrollTo('pricing')}>{t.navPricing}</button>
              <button type="button" onClick={() => scrollTo('faq')}>{t.navFaq}</button>
              <button type="button" onClick={() => scrollTo('contact')}>{t.navContact}</button>
            </Motion.div>
          )}
        </AnimatePresence>
      </nav>

      {/* ======== HERO ======== */}
      <section className="hero">
        {/* Background decorations */}
        <div className="hero__bg" aria-hidden="true">
          <div className="hero__orb hero__orb--1" />
          <div className="hero__orb hero__orb--2" />
          <div className="hero__orb hero__orb--3" />
          <div className="hero__grid" />
          <div className="hero__vignette" />
        </div>

        {/* Speed lines */}
        <div className="hero__lines" aria-hidden="true">
          <div className="hero__line" />
          <div className="hero__line" />
          <div className="hero__line" />
          <div className="hero__line" />
          <div className="hero__line" />
        </div>

        <div className="hero__content">
          <div className="hero__text">
            {/* Logo reveal */}
            <Motion.div
              className="hero__title-wrap"
              initial={{ opacity: 0, scale: 0.9, filter: 'blur(20px)' }}
              animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }}
              transition={{ duration: 1.2, ease: [0.25, 0.1, 0.25, 1] }}
            >
              <img src="/mechora-writing.png" alt="Mechora" className="hero__title-logo" />
            </Motion.div>

            {/* Subtitle with word reveal */}
            <div className="hero__subtitle">
              <WordReveal text={t.heroSubtitle} baseDelay={0.6} />
            </div>

            {/* Floating stat badges */}
            <Motion.div
              className="hero__badges"
              initial="hidden"
              animate="visible"
              variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.1, delayChildren: 1.2 } } }}
            >
              {t.heroStats.map((stat, idx) => (
                <Motion.span
                  key={idx}
                  className="hero__badge"
                  variants={{
                    hidden: { opacity: 0, y: 16, filter: 'blur(6px)' },
                    visible: { opacity: 1, y: 0, filter: 'blur(0px)', transition: { duration: 0.5 } },
                  }}
                >
                  {stat}
                </Motion.span>
              ))}
            </Motion.div>

            {/* CTAs */}
            <Motion.div
              className="hero__actions"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 1.6 }}
            >
              <button className="btn-gold" onClick={goToGuides}>
                <span>{t.ctaPrimary}</span>
                <IconArrowRight />
              </button>
              <button className="btn-ghost" onClick={() => scrollTo('features')}>
                {t.ctaSecondary}
              </button>
            </Motion.div>
          </div>

          {/* Chat demo */}
          <Motion.div
            className="hero__demo"
            variants={slideInRight}
            initial="hidden"
            animate="visible"
          >
            <ChatDemo
              userMsg={t.chatDemoUser}
              aiMsg={t.chatDemoAi}
              sourceMsg={t.chatDemoSource}
            />
          </Motion.div>
        </div>

        <button
          type="button"
          className="hero__scroll"
          onClick={() => scrollTo('stats')}
          aria-label={t.ctaSecondary}
        >
          <Motion.div
            animate={{ y: [0, 8, 0] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          >
            <IconChevronDown />
          </Motion.div>
        </button>
      </section>

      {/* ======== STATS BAR ======== */}
      <section id="stats" className="section stats">
        <div className="container">
          <Motion.div
            className="stats__bar"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.5 }}
            variants={stagger}
          >
            <Motion.div className="stats__item" variants={fadeInUp}>
              <AnimatedCounter target={130} suffix="+" />
              <span className="stats__label">{t.statsVehicles}</span>
            </Motion.div>
            <span className="stats__divider" />
            <Motion.div className="stats__item" variants={fadeInUp}>
              <AnimatedCounter target={30} suffix="+" />
              <span className="stats__label">{t.statsBrands}</span>
            </Motion.div>
            <span className="stats__divider" />
            <Motion.div className="stats__item" variants={fadeInUp}>
              <AnimatedCounter target={50000} suffix="+" duration={2500} />
              <span className="stats__label">{t.statsPages}</span>
            </Motion.div>
            <span className="stats__divider" />
            <Motion.div className="stats__item" variants={fadeInUp}>
              <AnimatedCounter target={3} />
              <span className="stats__label">{t.statsLangs}</span>
            </Motion.div>
          </Motion.div>
        </div>
      </section>

      {/* ======== FEATURES ======== */}
      <section id="features" className="section features">
        <div className="container">
          <Motion.div
            className="section__header"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.3 }}
            variants={fadeInUp}
          >
            <span className="section__label">{t.featuresLabel}</span>
            <div className="section__label-line" />
            <h2 className="section__title">{t.featuresTitle}</h2>
          </Motion.div>

          <Motion.div
            className="features__grid"
            variants={stagger}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.15 }}
          >
            {t.features.map((feature, idx) => {
              const Icon = FEATURE_ICONS[idx] || IconBook;
              return (
                <Motion.div
                  key={idx}
                  className={`feature-card feature-card--${idx}`}
                  variants={fadeInUp}
                  onMouseMove={handleCardSpotlight}
                >
                  <div className="feature-card__glow" />
                  <div className="feature-card__content">
                    <div className="feature-card__icon">
                      <Icon />
                    </div>
                    <h3 className="feature-card__title">{feature.title}</h3>
                    <p className="feature-card__desc">{feature.desc}</p>
                  </div>
                </Motion.div>
              );
            })}
          </Motion.div>
        </div>
      </section>

      {/* ======== HOW IT WORKS ======== */}
      <section id="how" className="section how">
        <div className="container">
          <Motion.div
            className="section__header"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.3 }}
            variants={fadeInUp}
          >
            <span className="section__label">{t.howLabel}</span>
            <div className="section__label-line" />
            <h2 className="section__title">{t.howTitle}</h2>
          </Motion.div>

          <Motion.div
            className="how__steps"
            variants={stagger}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.2 }}
          >
            {t.howSteps.map((step, idx) => {
              const Preview = HOW_PREVIEWS[idx] || null;
              return (
                <Motion.div key={idx} className="how__step" variants={fadeInUp}>
                  <div className="how__step-number">{idx + 1}</div>
                  {idx < t.howSteps.length - 1 && <div className="how__step-connector" />}
                  {Preview && <div className="how__step-preview"><Preview /></div>}
                  <h3 className="how__step-title">{step.title}</h3>
                  <p className="how__step-desc">{step.desc}</p>
                </Motion.div>
              );
            })}
          </Motion.div>
        </div>
      </section>

      {/* ======== PRICING ======== */}
      <section id="pricing" className="section pricing">
        <div className="container">
          <Motion.div
            className="section__header"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.3 }}
            variants={fadeInUp}
          >
            <span className="section__label">{t.pricingLabel}</span>
            <div className="section__label-line" />
            <h2 className="section__title">{t.pricingTitle}</h2>
          </Motion.div>

          <Motion.div
            className="pricing__grid"
            variants={stagger}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.15 }}
          >
            {/* Free */}
            <Motion.div className="price-card" variants={fadeInUp} onMouseMove={handleCardSpotlight}>
              <div className="price-card__spotlight" />
              <span className="price-card__badge price-card__badge--free">{t.freePlan.badge}</span>
              <h3 className="price-card__name">{t.freePlan.name}</h3>
              <p className="price-card__price">{t.freePlan.price}</p>
              <ul className="price-card__features">
                {t.freePlan.features.map((f, i) => (
                  <li key={i}><IconCheck />{f}</li>
                ))}
              </ul>
              <button className="price-card__cta price-card__cta--free" onClick={goToGuides}>
                {t.freePlan.cta}
              </button>
            </Motion.div>

            {/* Premium */}
            <Motion.div className="price-card price-card--premium" variants={fadeInUp} onMouseMove={handleCardSpotlight}>
              <div className="price-card__spotlight" />
              <div className="price-card__glow-border" />
              <span className="price-card__badge price-card__badge--premium">{t.premiumPlan.badge}</span>
              <h3 className="price-card__name">{t.premiumPlan.name}</h3>
              <p className="price-card__price">{t.premiumPlan.price}</p>
              <ul className="price-card__features">
                {t.premiumPlan.features.map((f, i) => (
                  <li key={i}><IconCheck />{f}</li>
                ))}
              </ul>
              <button className="price-card__cta price-card__cta--premium" onClick={goToGuides}>
                {t.premiumPlan.cta}
              </button>
            </Motion.div>

            {/* Enterprise */}
            <Motion.div className="price-card price-card--enterprise" variants={fadeInUp} onMouseMove={handleCardSpotlight}>
              <div className="price-card__spotlight" />
              <span className="price-card__badge price-card__badge--enterprise">{t.enterprisePlan.badge}</span>
              <h3 className="price-card__name">{t.enterprisePlan.name}</h3>
              <p className="price-card__price price-card__price--custom">{t.enterprisePlan.subtitle}</p>
              <ul className="price-card__features">
                {t.enterprisePlan.features.map((f, i) => (
                  <li key={i}><IconCheck />{f}</li>
                ))}
              </ul>
              <a
                href="mailto:lakhdarberache@gmail.com?subject=Mechora%20Enterprise"
                className="price-card__cta price-card__cta--enterprise"
              >
                {t.enterprisePlan.cta}
              </a>
            </Motion.div>
          </Motion.div>
        </div>
      </section>

      {/* ======== FAQ ======== */}
      <section id="faq" className="section faq">
        <div className="container">
          <Motion.div
            className="section__header"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.3 }}
            variants={fadeInUp}
          >
            <span className="section__label">{t.faqLabel}</span>
            <div className="section__label-line" />
            <h2 className="section__title">{t.faqTitle}</h2>
          </Motion.div>

          <Motion.div
            className="faq__list"
            variants={stagger}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.1 }}
          >
            {t.faq.map((item, idx) => (
              <Motion.div
                key={idx}
                className={`faq__item${openFaq === idx ? ' faq__item--open' : ''}`}
                variants={fadeInUp}
              >
                <button
                  type="button"
                  className="faq__question"
                  onClick={() => setOpenFaq(openFaq === idx ? null : idx)}
                  aria-expanded={openFaq === idx}
                >
                  <span>{item.q}</span>
                  <span className="faq__icon"><IconPlus /></span>
                </button>
                <AnimatePresence>
                  {openFaq === idx && (
                    <Motion.div
                      className="faq__answer"
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3, ease: [0.25, 0.1, 0.25, 1] }}
                    >
                      <p>{item.a}</p>
                    </Motion.div>
                  )}
                </AnimatePresence>
              </Motion.div>
            ))}
          </Motion.div>
        </div>
      </section>

      {/* ======== CONTACT ======== */}
      <section id="contact" className="section contact">
        <div className="container">
          <Motion.div
            className="section__header"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.3 }}
            variants={fadeInUp}
          >
            <span className="section__label">{t.contactLabel}</span>
            <div className="section__label-line" />
            <h2 className="section__title">{t.contactTitle}</h2>
            <p className="section__subtitle">{t.contactSubtitle}</p>
          </Motion.div>

          <Motion.form
            className="contact__form"
            onSubmit={handleContactSubmit}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.2 }}
            variants={fadeInUp}
          >
            <div className="contact__field">
              <label htmlFor="contact-name">{t.contactName}</label>
              <input id="contact-name" name="name" type="text" required autoComplete="name" placeholder={t.contactName} />
            </div>
            <div className="contact__field">
              <label htmlFor="contact-email">{t.contactEmail}</label>
              <input id="contact-email" name="email" type="email" required autoComplete="email" placeholder={t.contactEmail} />
            </div>
            <div className="contact__field">
              <label htmlFor="contact-message">{t.contactMessage}</label>
              <textarea id="contact-message" name="message" required rows={5} placeholder={t.contactMessage} />
            </div>
            <button type="submit" className="contact__submit">
              <span>{t.contactSend}</span>
              <IconSend />
            </button>
          </Motion.form>

          <div className="contact__socials">
            <a href="#" target="_blank" rel="noopener noreferrer" className="contact__social" aria-label="LinkedIn">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zM6.84 20.452H3.834V9H6.84v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
              </svg>
              <span>LinkedIn</span>
            </a>
          </div>
        </div>
      </section>

      {/* ======== FOOTER ======== */}
      <footer className="footer">
        <div className="container">
          <div className="footer__grid">
            <div className="footer__col footer__col--brand">
              <img src="/mechora-writing.png" alt="Mechora" className="footer__logo" />
              <p className="footer__bio">{t.footerBio}</p>
              <a href="mailto:lakhdarberache@gmail.com" className="footer__email">lakhdarberache@gmail.com</a>
            </div>

            <div className="footer__col">
              <h4 className="footer__col-title">{t.footerNavTitle}</h4>
              <ul>
                <li><button type="button" onClick={() => scrollTo('features')}>{t.footerFeatures}</button></li>
                <li><button type="button" onClick={() => scrollTo('pricing')}>{t.footerPricing}</button></li>
                <li><button type="button" onClick={() => scrollTo('faq')}>{t.footerFaq}</button></li>
                <li><button type="button" onClick={() => scrollTo('contact')}>{t.footerContact}</button></li>
              </ul>
            </div>

            <div className="footer__col">
              <h4 className="footer__col-title">{t.footerResTitle}</h4>
              <ul>
                <li><button type="button" onClick={goToGuides}>{t.footerGuides}</button></li>
                <li><button type="button" onClick={() => scrollTo('contact')}>{t.footerAbout}</button></li>
                <li><span>{t.footerTerms}</span></li>
                <li><span>{t.footerPrivacy}</span></li>
              </ul>
            </div>

            <div className="footer__col">
              <h4 className="footer__col-title">{t.footerContactTitle}</h4>
              <ul>
                <li><a href="#" target="_blank" rel="noopener noreferrer">LinkedIn</a></li>
                <li><a href="mailto:lakhdarberache@gmail.com">lakhdarberache@gmail.com</a></li>
              </ul>
            </div>
          </div>

          <div className="footer__bottom">
            <span>&copy; 2026 Mechora. Tous droits r&eacute;serv&eacute;s.</span>
          </div>
        </div>
      </footer>
    </main>
  );
}
