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
    aboutBio: "Étudiant en école d'ingénieur, passionné d'automobile. Après un stage ingénieur en automobile, j'ai voulu rendre accessibles les informations techniques des véhicules pour tous.",
    contactLabel: 'Contact',
    contactTitle: 'Contactez-nous',
    contactSubtitle: 'Une question ? Un retour ? Écrivez-nous.',
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
    footerGuides: 'Guides',
    footerFaq: 'FAQ',
    footerContact: 'Contact',
    footerAbout: 'À propos',
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
    aboutBio: 'Engineering student, passionate about cars. After an automotive engineering internship, I wanted to make vehicle technical information accessible to everyone.',
    contactLabel: 'Contact',
    contactTitle: 'Contact us',
    contactSubtitle: 'Have a question? Feedback? Write to us.',
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
    footerGuides: 'Guides',
    footerFaq: 'FAQ',
    footerContact: 'Contact',
    footerAbout: 'About',
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
    aboutBio: '공학도이자 자동차 마니아. 자동차 공학 인턴십을 마친 후, 모든 사람이 차량 기술 정보에 쉽게 접근할 수 있도록 만들고 싶었습니다.',
    contactLabel: '문의',
    contactTitle: '문의하기',
    contactSubtitle: '질문이나 피드백이 있으신가요?',
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
    footerGuides: '가이드',
    footerFaq: 'FAQ',
    footerContact: '문의',
    footerAbout: '소개',
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

const FEATURE_ICONS = [IconBook, IconChat, IconShield, IconGlobe];

/* ============================================================
   Animation Variants
   ============================================================ */

const fadeInUp = {
  hidden: { opacity: 0, y: 30 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: 'easeOut' } },
};

const stagger = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.12 } },
};

/* ============================================================
   Animated Counter (for stats section)
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
        <div className="chat-demo__dot" />
        <div className="chat-demo__dot" />
        <div className="chat-demo__dot" />
        <span className="chat-demo__title">Mechora</span>
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
            {sourceMsg}
          </Motion.div>
        )}
      </div>
    </div>
  );
}

/* ============================================================
   Feature Card Animations (CSS-only micro-illustrations)
   ============================================================ */

const FeatureBookAnim = () => (
  <div className="feat-anim feat-anim--book">
    <div className="feat-book__page feat-book__page--1" />
    <div className="feat-book__page feat-book__page--2" />
    <div className="feat-book__spine" />
  </div>
);

const FeatureTypingAnim = () => (
  <div className="feat-anim feat-anim--typing">
    <span className="feat-typing__dot" />
    <span className="feat-typing__dot" />
    <span className="feat-typing__dot" />
  </div>
);

const FeatureCheckAnim = () => (
  <div className="feat-anim feat-anim--check">
    <svg viewBox="0 0 32 32" className="feat-check__svg">
      <circle cx="16" cy="16" r="14" className="feat-check__circle" />
      <polyline points="10 16 14 20 22 12" className="feat-check__tick" />
    </svg>
  </div>
);

const FeatureLangAnim = () => (
  <div className="feat-anim feat-anim--lang">
    <span className="feat-lang__text">FR</span>
    <span className="feat-lang__text">EN</span>
    <span className="feat-lang__text">KO</span>
  </div>
);

const FEATURE_ANIMS = [FeatureBookAnim, FeatureTypingAnim, FeatureCheckAnim, FeatureLangAnim];

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
      <span className="how-preview__send-icon">
        <IconSend />
      </span>
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
   Component
   ============================================================ */

export default function LandingPage() {
  const navigate = useNavigate();
  const [lang, setLang] = useAppLanguage();
  const t = COPY[lang] || COPY.fr;

  const [langOpen, setLangOpen] = useState(false);
  const [navScrolled, setNavScrolled] = useState(false);
  const [openFaq, setOpenFaq] = useState(null);
  const langDropdownRef = useRef(null);

  const currentLang = LANGUAGES.find((entry) => entry.code === lang) || LANGUAGES[0];

  // Restore scroll on mount
  useEffect(() => {
    document.body.style.overflow = 'auto';
    document.documentElement.style.overflow = 'auto';
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  }, []);

  // Nav scroll effect
  useEffect(() => {
    const handleScroll = () => setNavScrolled(window.scrollY > 40);
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Close language dropdown on outside click or Escape
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

  return (
    <main className="landing-page">

      {/* ---- NAVIGATION ---- */}
      <nav className={`landing-nav${navScrolled ? ' nav-scrolled' : ''}`}>
        <div className="landing-container">
          <button type="button" className="nav-brand" onClick={() => navigate('/')} aria-label="Home">
            <img className="nav-brand__mark nav-brand__mark--wide" src="/logo top left.png" alt="Mechora" />
          </button>

          <ul className="nav-links">
            <li><button type="button" className="nav-link" onClick={() => scrollTo('features')}>{t.navFeatures}</button></li>
            <li><button type="button" className="nav-link" onClick={() => scrollTo('pricing')}>{t.navPricing}</button></li>
            <li><button type="button" className="nav-link" onClick={() => scrollTo('faq')}>{t.navFaq}</button></li>
            <li><button type="button" className="nav-link" onClick={() => scrollTo('contact')}>{t.navContact}</button></li>
          </ul>

          <div className="nav-right">
            <div className="lang-dropdown" ref={langDropdownRef}>
              <button
                type="button"
                className="lang-btn"
                onClick={() => setLangOpen((prev) => !prev)}
                aria-expanded={langOpen}
                aria-haspopup="menu"
              >
                <img
                  className="lang-flag"
                  src={FLAG_BY_LANG[currentLang?.code] || FLAG_BY_LANG.fr}
                  alt={`${currentLang?.label || 'FR'} flag`}
                />
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
                    transition={{ duration: 0.12 }}
                  >
                    {LANGUAGES.map((entry) => (
                      <button
                        key={entry.code}
                        type="button"
                        className={`lang-menu-item${entry.code === lang ? ' active' : ''}`}
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
          </div>
        </div>
      </nav>

      {/* ---- HERO ---- */}
      <section className="landing-section hero-section">
        {/* Abstract automotive lines */}
        <div className="hero-lines" aria-hidden="true">
          <div className="hero-line" />
          <div className="hero-line" />
          <div className="hero-line" />
        </div>

        {/* CSS car silhouette */}
        <div className="hero-car-art" aria-hidden="true">
          <div className="hero-car-body">
            <div className="hero-car-wheel hero-car-wheel--front" />
            <div className="hero-car-wheel hero-car-wheel--rear" />
          </div>
        </div>

        <div className="hero-split">
          <Motion.div
            className="hero-content"
            variants={stagger}
            initial="hidden"
            animate="visible"
          >
            <Motion.h1 variants={fadeInUp} className="hero-title">
              <span className="hero-title-accent">{t.heroTitle}</span>
            </Motion.h1>

            <Motion.p variants={fadeInUp} className="hero-subtitle">
              {t.heroSubtitle}
            </Motion.p>

            <Motion.div variants={fadeInUp} className="hero-stats">
              {t.heroStats.map((stat, idx) => (
                <React.Fragment key={idx}>
                  {idx > 0 && <span className="hero-stats-separator" />}
                  <span>{stat}</span>
                </React.Fragment>
              ))}
            </Motion.div>

            <Motion.div variants={fadeInUp} className="hero-actions">
              <button className="btn-gold" onClick={goToGuides}>
                <span>{t.ctaPrimary}</span>
                <IconArrowRight />
              </button>
              <button className="btn-ghost" onClick={() => scrollTo('features')}>
                {t.ctaSecondary}
              </button>
            </Motion.div>
          </Motion.div>

          <Motion.div
            className="hero-chat-wrapper"
            initial={{ opacity: 0, x: 40 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.6, duration: 0.8 }}
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
          className="hero-scroll-hint"
          onClick={() => scrollTo('features')}
          aria-label={t.ctaSecondary}
        >
          <IconChevronDown />
        </button>
      </section>

      {/* ---- STATS BAR ---- */}
      <section className="landing-section stats-section">
        <div className="landing-container">
          <Motion.div
            className="stats-bar"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.5 }}
            variants={stagger}
          >
            <Motion.div className="stat-item" variants={fadeInUp}>
              <AnimatedCounter target={130} suffix="+" />
              <span className="stat-label">{t.statsVehicles}</span>
            </Motion.div>
            <span className="stats-divider" />
            <Motion.div className="stat-item" variants={fadeInUp}>
              <AnimatedCounter target={30} suffix="+" />
              <span className="stat-label">{t.statsBrands}</span>
            </Motion.div>
            <span className="stats-divider" />
            <Motion.div className="stat-item" variants={fadeInUp}>
              <AnimatedCounter target={50000} suffix="+" duration={2500} />
              <span className="stat-label">{t.statsPages}</span>
            </Motion.div>
            <span className="stats-divider" />
            <Motion.div className="stat-item" variants={fadeInUp}>
              <AnimatedCounter target={3} />
              <span className="stat-label">{t.statsLangs}</span>
            </Motion.div>
          </Motion.div>
        </div>
      </section>

      {/* ---- FEATURES ---- */}
      <section id="features" className="landing-section features-section">
        <div className="landing-container">
          <Motion.div
            className="features-header"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.3 }}
            variants={fadeInUp}
          >
            <span className="section-label">{t.featuresLabel}</span>
            <h2 className="section-title">{t.featuresTitle}</h2>
          </Motion.div>

          <Motion.div
            className="features-grid"
            variants={stagger}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.2 }}
          >
            {t.features.map((feature, idx) => {
              const Icon = FEATURE_ICONS[idx] || IconBook;
              const Anim = FEATURE_ANIMS[idx] || null;
              return (
                <Motion.div key={idx} className="glass-card" variants={fadeInUp}>
                  <div className="feature-icon-wrap">
                    <Icon />
                  </div>
                  {Anim && <Anim />}
                  <h3 className="feature-title">{feature.title}</h3>
                  <p className="feature-desc">{feature.desc}</p>
                </Motion.div>
              );
            })}
          </Motion.div>
        </div>
      </section>

      {/* ---- HOW IT WORKS ---- */}
      <section id="how" className="landing-section how-section">
        <div className="landing-container">
          <Motion.div
            className="how-header"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.3 }}
            variants={fadeInUp}
          >
            <span className="section-label">{t.howLabel}</span>
            <h2 className="section-title">{t.howTitle}</h2>
          </Motion.div>

          <Motion.div
            className="how-steps"
            variants={stagger}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.3 }}
          >
            {t.howSteps.map((step, idx) => {
              const Preview = HOW_PREVIEWS[idx] || null;
              return (
                <Motion.div key={idx} className="how-step" variants={fadeInUp}>
                  <div className="how-step-number">{idx + 1}</div>
                  {idx < t.howSteps.length - 1 && <div className="how-step-connector" />}
                  {Preview && <div className="how-step-preview"><Preview /></div>}
                  <h3 className="how-step-title">{step.title}</h3>
                  <p className="how-step-desc">{step.desc}</p>
                </Motion.div>
              );
            })}
          </Motion.div>
        </div>
      </section>

      {/* ---- PRICING ---- */}
      <section id="pricing" className="landing-section pricing-section">
        <div className="landing-container">
          <Motion.div
            className="pricing-header"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.3 }}
            variants={fadeInUp}
          >
            <span className="section-label">{t.pricingLabel}</span>
            <h2 className="section-title">{t.pricingTitle}</h2>
          </Motion.div>

          <Motion.div
            className="pricing-grid"
            variants={stagger}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.2 }}
          >
            {/* Free Plan */}
            <Motion.div className="pricing-card" variants={fadeInUp}>
              <span className="pricing-badge pricing-badge--free">{t.freePlan.badge}</span>
              <h3 className="pricing-plan-name">{t.freePlan.name}</h3>
              <p className="pricing-price">{t.freePlan.price}</p>
              <ul className="pricing-features">
                {t.freePlan.features.map((f, i) => (
                  <li key={i}><IconCheck />{f}</li>
                ))}
              </ul>
              <button className="pricing-cta pricing-cta--free" onClick={goToGuides}>
                {t.freePlan.cta}
              </button>
            </Motion.div>

            {/* Premium Plan */}
            <Motion.div className="pricing-card pricing-card--premium" variants={fadeInUp}>
              <span className="pricing-badge pricing-badge--premium">{t.premiumPlan.badge}</span>
              <h3 className="pricing-plan-name">{t.premiumPlan.name}</h3>
              <p className="pricing-price">{t.premiumPlan.price}</p>
              <ul className="pricing-features">
                {t.premiumPlan.features.map((f, i) => (
                  <li key={i}><IconCheck />{f}</li>
                ))}
              </ul>
              <button className="pricing-cta pricing-cta--premium" onClick={goToGuides}>
                {t.premiumPlan.cta}
              </button>
            </Motion.div>
          </Motion.div>
        </div>
      </section>

      {/* ---- FAQ ---- */}
      <section id="faq" className="landing-section faq-section">
        <div className="landing-container">
          <Motion.div
            className="faq-header"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.3 }}
            variants={fadeInUp}
          >
            <span className="section-label">{t.faqLabel}</span>
            <h2 className="section-title">{t.faqTitle}</h2>
          </Motion.div>

          <Motion.div
            className="faq-list"
            variants={stagger}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.1 }}
          >
            {t.faq.map((item, idx) => (
              <Motion.div
                key={idx}
                className={`faq-item${openFaq === idx ? ' faq-item--open' : ''}`}
                variants={fadeInUp}
              >
                <button
                  type="button"
                  className="faq-question"
                  onClick={() => setOpenFaq(openFaq === idx ? null : idx)}
                  aria-expanded={openFaq === idx}
                >
                  <span>{item.q}</span>
                  <IconPlus />
                </button>
                <AnimatePresence>
                  {openFaq === idx && (
                    <Motion.div
                      className="faq-answer"
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.25, ease: 'easeInOut' }}
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

      {/* ---- ABOUT ---- */}
      <section id="about" className="landing-section about-section">
        <div className="landing-container">
          <Motion.div
            className="about-content"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.3 }}
            variants={fadeInUp}
          >
            <div className="about-avatar">LB</div>
            <div className="about-text">
              <h3>{t.aboutName}</h3>
              <span className="about-role">{t.aboutRole}</span>
              <p>{t.aboutBio}</p>
            </div>
          </Motion.div>
        </div>
      </section>

      {/* ---- CONTACT ---- */}
      <section id="contact" className="landing-section contact-section">
        <div className="landing-container">
          <Motion.div
            className="contact-header"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.3 }}
            variants={fadeInUp}
          >
            <span className="section-label">{t.contactLabel}</span>
            <h2 className="section-title">{t.contactTitle}</h2>
            <p className="section-subtitle">{t.contactSubtitle}</p>
          </Motion.div>

          <Motion.form
            className="contact-form"
            onSubmit={handleContactSubmit}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.2 }}
            variants={fadeInUp}
          >
            <div className="contact-field">
              <label htmlFor="contact-name">{t.contactName}</label>
              <input id="contact-name" name="name" type="text" required autoComplete="name" />
            </div>
            <div className="contact-field">
              <label htmlFor="contact-email">{t.contactEmail}</label>
              <input id="contact-email" name="email" type="email" required autoComplete="email" />
            </div>
            <div className="contact-field">
              <label htmlFor="contact-message">{t.contactMessage}</label>
              <textarea id="contact-message" name="message" required rows={5} />
            </div>
            <button type="submit" className="contact-submit">
              <span>{t.contactSend}</span>
              <IconSend />
            </button>
          </Motion.form>
        </div>
      </section>

      {/* ---- FOOTER ---- */}
      <footer className="landing-footer">
        <div className="landing-container">
          <div className="footer-inner">
            <div className="footer-brand">
              <span className="footer-logo">Mechora</span>
              <span className="footer-copy">&copy; 2026</span>
            </div>

            <ul className="footer-links">
              <li><button type="button" className="footer-link" onClick={goToGuides}>{t.footerGuides}</button></li>
              <li><button type="button" className="footer-link" onClick={() => scrollTo('faq')}>{t.footerFaq}</button></li>
              <li><button type="button" className="footer-link" onClick={() => scrollTo('contact')}>{t.footerContact}</button></li>
              <li><button type="button" className="footer-link" onClick={() => scrollTo('about')}>{t.footerAbout}</button></li>
            </ul>

            <div className="footer-socials">
              <a
                href="https://linkedin.com"
                target="_blank"
                rel="noopener noreferrer"
                className="footer-social"
                aria-label="LinkedIn"
              >
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zM6.84 20.452H3.834V9H6.84v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
                </svg>
              </a>
              <a
                href="https://github.com"
                target="_blank"
                rel="noopener noreferrer"
                className="footer-social"
                aria-label="GitHub"
              >
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
                </svg>
              </a>
            </div>
          </div>
        </div>
      </footer>
    </main>
  );
}
