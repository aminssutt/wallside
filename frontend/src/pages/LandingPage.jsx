import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion as Motion, AnimatePresence } from 'framer-motion';
import { LANGUAGES, useAppLanguage } from '../i18n';
import { API_URL } from '../api';
import { useToast } from '../toast';
import './LandingPage.css';

const FLAG_BY_LANG = {
  fr: '/flags/fr.svg',
  en: '/flags/en.svg',
  ko: '/flags/ko.svg',
};

const COPY = {
  en: {
    heroBadge: 'AI-Powered Vehicle Assistant',
    heroTitleHover: 'Ask your car manual',
    heroTitleMain: 'anything.',
    heroSubtitle: "Get instant answers about warning lights, maintenance, specs, and features—from indexed owner's manual content.",
    ctaPrimary: 'Try the beta for free >',
    ctaSecondary: 'See example questions',
    toastRedirecting: 'Action confirmed. Redirecting...',
    featuresTitle: 'Why Choose CarChat?',
    features: [
      { title: 'Understand warning lights', desc: 'Get real-time answers about your dashboard lights and clear, safe next steps.' },
      { title: 'Find maintenance info faster', desc: 'Know when and how to service your car without flipping through pages.' },
      { title: 'Ask in your language', desc: 'Chat in English, French, or Korean seamlessly.' }
    ],
    plansTitle: 'Choose your access',
    plansSubtitle: 'Start in beta today, then unlock deep technical guidance with Premium.',
    betaPlanBadge: 'LIVE',
    betaPlanTitle: 'Beta test',
    betaPlanDesc: 'Free early access to core chat, model selection, and indexed manual answers.',
    betaPlanCta: 'Test the beta',
    premiumPlanBadge: 'COMING SOON',
    premiumPlanTitle: 'Premium coming soon',
    premiumPlanDesc: 'Advanced technical intelligence for power users and workshops.',
    premiumPlanFeatures: [
      '+500 vehicles indexed',
      'Cross-manual spec conflict detection',
      'VIN and trim-aware procedure filtering',
      'Maintenance delta tracking by mileage and time',
      'Deep diagnostics workflow guidance',
    ],
    premiumPlanCta: 'Join premium waitlist',
    premiumPlanLocked: 'Coming soon',
    waitlistTitle: 'Join premium waitlist',
    waitlistSubtitle: 'Enter your email to be notified when premium opens.',
    waitlistPlaceholder: 'you@example.com',
    waitlistCancel: 'Cancel',
    waitlistSubmit: 'Join waitlist',
    waitlistSubmitting: 'Saving...',
    waitlistSuccess: 'Thanks, you are now on the premium waitlist.',
    waitlistInvalidEmail: 'Please enter a valid email address.',
    waitlistError: 'Unable to save your email right now.',
    chatPreview: {
      user: 'What does this warning light mean?',
      ai: "According to your manual, this is likely the Malfunction Indicator Lamp (Check Engine). Drive calmly and schedule a diagnostic if it stays on.\n\nVideo: [YouTube walkthrough placeholder]\nSources: Owner's manual p.2, p.45"
    },
    chatInputPlaceholder: 'Ask your manual...'
  },
  fr: {
    heroBadge: 'Assistant Automobile par IA',
    heroTitleHover: 'Demandez tout à',
    heroTitleMain: 'votre manuel.',
    heroSubtitle: 'Obtenez des réponses instantanées sur les voyants, l\'entretien et les caractéristiques—à partir du contenu indexé de votre manuel.',
    ctaPrimary: 'Essayer la bêta gratuitement >',
    ctaSecondary: 'Voir des exemples',
    toastRedirecting: 'Action validée. Redirection en cours...',
    featuresTitle: 'Pourquoi choisir CarChat ?',
    features: [
      { title: 'Comprendre les voyants', desc: 'Obtenez des réponses en temps réel sur les voyants de votre tableau de bord.' },
      { title: 'Trouvez l\'entretien plus vite', desc: 'Sachez quand et comment entretenir votre voiture sans chercher dans les pages.' },
      { title: 'Demandez dans votre langue', desc: 'Discutez en anglais, français ou coréen de manière fluide.' }
    ],
    plansTitle: 'Choisissez votre accès',
    plansSubtitle: 'Commencez en bêta puis débloquez un guidage technique avancé avec Premium.',
    betaPlanBadge: 'EN DIRECT',
    betaPlanTitle: 'Test bêta',
    betaPlanDesc: 'Accès gratuit aux fonctions essentielles : chat, sélection du modèle et réponses issues des manuels indexés.',
    betaPlanCta: 'Tester la bêta',
    premiumPlanBadge: 'BIENTÔT',
    premiumPlanTitle: 'Premium bientôt',
    premiumPlanDesc: 'Intelligence technique avancée pour utilisateurs exigeants et ateliers.',
    premiumPlanFeatures: [
      '+500 véhicules indexés',
      'Détection des conflits de spécifications multi-manuels',
      'Filtrage des procédures par VIN et finition',
      'Suivi des écarts d\'entretien par kilométrage et par temps',
      'Guidage de workflow de diagnostic avancé',
    ],
    premiumPlanCta: "Rejoindre la liste d'attente premium",
    premiumPlanLocked: 'Bientôt disponible',
    waitlistTitle: "Rejoindre la liste d'attente premium",
    waitlistSubtitle: 'Ajoutez votre e-mail pour être prévenu de l\'ouverture.',
    waitlistPlaceholder: 'vous@exemple.com',
    waitlistCancel: 'Annuler',
    waitlistSubmit: 'Rejoindre',
    waitlistSubmitting: 'Enregistrement...',
    waitlistSuccess: "Merci, votre e-mail est bien ajouté à la liste d'attente.",
    waitlistInvalidEmail: 'Veuillez saisir une adresse e-mail valide.',
    waitlistError: 'Impossible d\'enregistrer votre e-mail pour le moment.',
    chatPreview: {
      user: 'Que signifie ce voyant d\'avertissement ?',
      ai: 'Selon votre manuel, il s\'agit probablement du voyant moteur (Check Engine). Roulez calmement et planifiez un diagnostic s\'il reste allumé.\n\nVideo: [Placeholder lien YouTube]\nSources: Manuel p.2, p.45'
    },
    chatInputPlaceholder: 'Posez votre question...'
  },
  ko: {
    heroBadge: 'AI 기반 차량 어시스턴트',
    heroTitleHover: '차량 매뉴얼에',
    heroTitleMain: '무엇이든 물어보세요.',
    heroSubtitle: '경고등, 유지보수, 사양 및 기능에 대한 빠르고 정확한 답변—인덱싱된 매뉴얼 내용에서 제공합니다.',
    ctaPrimary: '무료 베타 체험하기 >',
    ctaSecondary: '예시 질문 보기',
    toastRedirecting: '확인되었습니다. 이동 중입니다...',
    featuresTitle: 'CarChat을 선택하는 이유?',
    features: [
      { title: '경고등 이해', desc: '대시보드 경고등에 대한 실시간 답변과 안전한 다음 단계를 확인하세요.' },
      { title: '빠른 유지보수 정보', desc: '페이지를 넘기지 않고도 차량 정비 시기와 방법을 알아보세요.' },
      { title: '당신의 언어로 질문', desc: '영어, 프랑스어 또는 한국어로 원활하게 채팅하세요.' }
    ],
    plansTitle: '이용 옵션을 선택하세요',
    plansSubtitle: '오늘 베타로 시작하고, Premium으로 더 깊은 기술 가이드를 받아보세요.',
    betaPlanBadge: '라이브',
    betaPlanTitle: '베타 테스트',
    betaPlanDesc: '핵심 채팅, 모델 선택, 인덱싱된 매뉴얼 답변을 무료로 먼저 이용하세요.',
    betaPlanCta: '베타 시작',
    premiumPlanBadge: '출시 예정',
    premiumPlanTitle: '프리미엄 곧 출시',
    premiumPlanDesc: '전문 사용자와 정비소를 위한 고급 기술 인텔리전스.',
    premiumPlanFeatures: [
      '+500개 차량 인덱싱',
      '매뉴얼 간 사양 충돌 감지',
      'VIN 및 트림 기반 정비 절차 필터링',
      '주행거리/기간 기준 정비 변화 추적',
      '딥 진단 워크플로 가이드',
    ],
    premiumPlanCta: '프리미엄 대기자 등록',
    premiumPlanLocked: '곧 공개',
    waitlistTitle: '프리미엄 대기자 등록',
    waitlistSubtitle: '프리미엄 오픈 알림을 받을 이메일을 입력하세요.',
    waitlistPlaceholder: 'you@example.com',
    waitlistCancel: '취소',
    waitlistSubmit: '대기자 등록',
    waitlistSubmitting: '저장 중...',
    waitlistSuccess: '감사합니다. 프리미엄 대기자 명단에 등록되었습니다.',
    waitlistInvalidEmail: '유효한 이메일 주소를 입력해 주세요.',
    waitlistError: '지금은 이메일을 저장할 수 없습니다.',
    chatPreview: {
      user: '이 경고등은 무슨 뜻인가요?',
      ai: '매뉴얼 기준으로 이 표시는 엔진 경고등일 가능성이 높습니다. 계속 켜져 있으면 속도를 줄이고 점검 일정을 잡아 주세요.\n\nVideo: [YouTube 가이드 자리표시자]\nSources: 매뉴얼 2페이지, 45페이지'
    },
    chatInputPlaceholder: '매뉴얼에 질문해 보세요...'
  }
};

const TypewriterText = ({ text, delay = 0 }) => {
  const [displayedText, setDisplayedText] = useState('');

  useEffect(() => {
    let index = 0;
    let timer;
    
    const startTyping = () => {
      timer = setInterval(() => {
        setDisplayedText(text.substring(0, index + 1));
        index++;
        if (index === text.length) clearInterval(timer);
      }, 30); // typing speed
    };

    const initialDelay = setTimeout(startTyping, delay);

    return () => {
      clearInterval(timer);
      clearTimeout(initialDelay);
    };
  }, [text, delay]);

  return <span>{displayedText}</span>;
};

export default function LandingPage() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [lang, setLang] = useAppLanguage();
  const t = COPY[lang] || COPY.en;
  
  const [langOpen, setLangOpen] = useState(false);
  const langDropdownRef = useRef(null);
  
  const currentLang = LANGUAGES.find((entry) => entry.code === lang) || LANGUAGES[0];
  const [chatStep, setChatStep] = useState(0);
  const [waitlistOpen, setWaitlistOpen] = useState(false);
  const [waitlistEmail, setWaitlistEmail] = useState('');
  const [waitlistStatus, setWaitlistStatus] = useState('idle');
  const [waitlistFeedback, setWaitlistFeedback] = useState('');
  const chatPreviewHasAnimatedRef = useRef(false);

  useEffect(() => {
    // Ensure the home page can always scroll after leaving full-screen chat pages.
    document.body.style.overflow = 'auto';
    document.documentElement.style.overflow = 'auto';
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  }, []);

  useEffect(() => {
    // Chat Animation Sequence
    if (chatPreviewHasAnimatedRef.current) {
      setChatStep(3);
      return undefined;
    }

    setChatStep(0);
    const t1 = setTimeout(() => setChatStep(1), 600);   // User starts typing
    const t2 = setTimeout(() => setChatStep(2), 2500);  // User done, AI thinking
    const t3 = setTimeout(() => {
      setChatStep(3);  // AI responding
      chatPreviewHasAnimatedRef.current = true;
    }, 4000);
    
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
  }, []);

  useEffect(() => {
    if (!langOpen) return undefined;

    const handleOutsideClick = (event) => {
      if (langDropdownRef.current && !langDropdownRef.current.contains(event.target)) {
        setLangOpen(false);
      }
    };

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setLangOpen(false);
      }
    };

    document.addEventListener('mousedown', handleOutsideClick);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [langOpen]);

  useEffect(() => {
    if (!waitlistOpen) return undefined;

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setWaitlistOpen(false);
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [waitlistOpen]);

  const openWaitlistModal = () => {
    setWaitlistEmail('');
    setWaitlistStatus('idle');
    setWaitlistFeedback('');
    setWaitlistOpen(true);
  };

  const closeWaitlistModal = () => {
    setWaitlistOpen(false);
  };

  const goToGuides = () => {
    showToast({ type: 'success', message: t.toastRedirecting });
    navigate('/guides');
  };

  const scrollToFeatures = () => {
    const target = document.getElementById('features');
    target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const handleWaitlistSubmit = async (event) => {
    event.preventDefault();

    const email = waitlistEmail.trim().toLowerCase();
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (!emailRegex.test(email)) {
      setWaitlistStatus('error');
      setWaitlistFeedback(t.waitlistInvalidEmail);
      showToast({ type: 'error', message: t.waitlistInvalidEmail });
      return;
    }

    setWaitlistStatus('loading');
    setWaitlistFeedback('');

    try {
      const response = await fetch(`${API_URL}/waitlist/premium`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          lang,
          source: 'landing-premium',
        }),
      });

      const payload = await response.json();
      if (!response.ok || !payload?.success) {
        throw new Error(payload?.error || t.waitlistError);
      }

      setWaitlistStatus('success');
      setWaitlistFeedback(t.waitlistSuccess);
      setWaitlistEmail('');
      showToast({ type: 'success', message: t.waitlistSuccess });
    } catch {
      setWaitlistStatus('error');
      setWaitlistFeedback(t.waitlistError);
      showToast({ type: 'error', message: t.waitlistError });
    }
  };

  const fadeUp = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { duration: 0.5, ease: 'easeOut' } }
  };

  const staggerContainer = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.15 } }
  };

  return (
    <main className="landing-automotive">
      <div className="landing-bg-elements" aria-hidden="true" />
      <div className="landing-bg-image" aria-hidden="true" />
      <div className="landing-grid" aria-hidden="true" />

      {/* Navigation Strip */}
      <section className="landing-shell nav-strip">
        <button type="button" className="nav-brand" onClick={() => navigate('/')} aria-label="Home">
          <img className="nav-brand__mark nav-brand__mark--wide" src="/logo top left.png" alt="CarChat" />
        </button>

        <div className="nav-actions">
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
                src={FLAG_BY_LANG[currentLang?.code] || FLAG_BY_LANG.en}
                alt={`${currentLang?.label || 'EN'} flag`}
              />
              <span className="lang-code">{currentLang?.label}</span>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>

            <AnimatePresence>
              {langOpen && (
                <Motion.div
                  className="lang-menu"
                  initial={{ opacity: 0, y: -8, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -8, scale: 0.96 }}
                  transition={{ duration: 0.14 }}
                >
                  {LANGUAGES.map((entry) => (
                    <button
                      key={entry.code}
                      type="button"
                      className={`lang-menu-item${entry.code === lang ? ' active' : ''}`}
                      onClick={() => {
                        setLang(entry.code);
                        setLangOpen(false);
                      }}
                    >
                      <img
                        className="lang-flag"
                        src={FLAG_BY_LANG[entry.code] || FLAG_BY_LANG.en}
                        alt={`${entry.label} flag`}
                      />
                      <span className="lang-code">{entry.label}</span>
                    </button>
                  ))}
                </Motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </section>

      {/* Hero Section */}
      <section className="landing-shell hero-section">
        <Motion.div 
          className="hero-content"
          variants={staggerContainer}
          initial="hidden"
          animate="visible"
        >
          <Motion.div variants={fadeUp} className="hero-badge-line">
            <span className="hero-badge-track" />
            <span className="hero-badge">{t.heroBadge}</span>
          </Motion.div>

          <Motion.h1 variants={fadeUp} className="hero-title">
            <span className="gradient-text hero-title-line">{t.heroTitleHover}</span>
            <span className="light-text hero-title-line">{t.heroTitleMain}</span>
          </Motion.h1>
          
          <Motion.p variants={fadeUp} className="hero-desc">
            {t.heroSubtitle}
          </Motion.p>
          
          <Motion.div variants={fadeUp} className="hero-actions">
            <button className="btn-primary" onClick={goToGuides}>
              <span>{t.ctaPrimary.replace(' >', '')}</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
                <path d="M5 12h14" />
                <path d="M13 5l7 7-7 7" />
              </svg>
            </button>
            <button className="btn-secondary" onClick={scrollToFeatures}>
              {t.ctaSecondary}
            </button>
          </Motion.div>
        </Motion.div>

        {/* Chat Visual Mockup */}
        <Motion.div 
          className="hero-visual"
          initial={{ opacity: 0, x: 20, rotateY: 10 }}
          animate={{ opacity: 1, x: 0, rotateY: 0 }}
          transition={{ duration: 0.8, ease: 'easeOut', delay: 0.2 }}
        >
          <div className="hero-visual-glow" aria-hidden="true" />
          <div className="chat-shell">
            <div className="chat-glass">
              <div className="chat-header">
                <div className="chat-window-controls">
                  <div className="chat-dot"></div>
                  <div className="chat-dot"></div>
                  <div className="chat-dot"></div>
                </div>
                <div className="chat-title">
                  <img src="/carchat-logo.png" alt="CarChat" className="chat-title-icon" />
                  CarChat AI
                </div>
              </div>
              
              <div className="chat-messages">
                <AnimatePresence>
                  {chatStep >= 1 && (
                    <Motion.div 
                      key="preview-user"
                      className="chat-bubble bubble-user"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.18 }}
                    >
                      <TypewriterText text={t.chatPreview.user} delay={100} />
                    </Motion.div>
                  )}
                  
                  {chatStep === 2 && (
                    <Motion.div 
                      key="preview-ai-loading"
                      className="chat-bubble bubble-ai loading-ai"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0, transition: { duration: 0.15 } }}
                    >
                      <div className="typing-dots">
                        <span></span><span></span><span></span>
                      </div>
                    </Motion.div>
                  )}

                  {chatStep >= 3 && (
                    <Motion.div 
                      key="preview-ai-answer"
                      className="chat-bubble bubble-ai"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.2 }}
                    >
                      <TypewriterText text={t.chatPreview.ai} delay={50} />
                    </Motion.div>
                  )}
                </AnimatePresence>
              </div>
              
              <div className="chat-input-bar">
                <div className="chat-input">
                  <span>{t.chatInputPlaceholder || 'Ask your manual...'}</span>
                  <div className="chat-send">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline></svg>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Motion.div>
      </section>

      {/* Features Section */}
      <section id="features" className="landing-shell features-section">
        {t.features.map((feature, idx) => (
          <Motion.div 
            key={idx}
            className="feature-card"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.5, delay: idx * 0.15 }}
          >
            <div className="feature-icon">
              {idx === 0 && <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>}
              {idx === 1 && <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path></svg>}
              {idx === 2 && <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>}
            </div>
            <h3 className="feature-title">{feature.title}</h3>
            <p className="feature-desc">{feature.desc}</p>
          </Motion.div>
        ))}
      </section>

      {/* Access Plans */}
      <section className="landing-shell plans-section">
        <Motion.div
          className="plans-heading"
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ duration: 0.45 }}
        >
          <h2>{t.plansTitle}</h2>
          <p>{t.plansSubtitle}</p>
        </Motion.div>

        <div className="plans-grid">
          <Motion.article
            className="plan-card plan-card-beta"
            initial={{ opacity: 0, y: 14 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.35 }}
            transition={{ duration: 0.45 }}
          >
            <span className="plan-badge">{t.betaPlanBadge || 'LIVE'}</span>
            <h3>{t.betaPlanTitle}</h3>
            <p>{t.betaPlanDesc}</p>
            <button className="plan-cta" onClick={goToGuides}>
              {t.betaPlanCta}
            </button>
          </Motion.article>

          <Motion.article
            className="plan-card plan-card-premium"
            initial={{ opacity: 0, y: 14 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.35 }}
            transition={{ duration: 0.45, delay: 0.08 }}
          >
            <span className="plan-badge plan-badge-premium">{t.premiumPlanBadge || 'COMING SOON'}</span>
            <h3>{t.premiumPlanTitle}</h3>
            <p>{t.premiumPlanDesc}</p>
            <ul className="plan-features">
              {t.premiumPlanFeatures.map((feature) => (
                <li key={feature}>{feature}</li>
              ))}
            </ul>
            <button
              type="button"
              className="plan-cta plan-cta-premium plan-cta-locked"
              disabled
              aria-disabled="true"
            >
              {t.premiumPlanLocked}
            </button>
          </Motion.article>
        </div>
      </section>

      <AnimatePresence>
        {waitlistOpen && (
          <Motion.div
            className="waitlist-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closeWaitlistModal}
          >
            <Motion.div
              className="waitlist-modal"
              initial={{ opacity: 0, y: 12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.98 }}
              transition={{ duration: 0.18 }}
              onClick={(event) => event.stopPropagation()}
            >
              <h3>{t.waitlistTitle}</h3>
              <p>{t.waitlistSubtitle}</p>

              <form className="waitlist-form" onSubmit={handleWaitlistSubmit}>
                <input
                  type="email"
                  value={waitlistEmail}
                  onChange={(event) => setWaitlistEmail(event.target.value)}
                  placeholder={t.waitlistPlaceholder}
                  autoComplete="email"
                  required
                  disabled={waitlistStatus === 'loading'}
                />

                <div className="waitlist-actions">
                  <button
                    type="button"
                    className="waitlist-btn waitlist-btn-ghost"
                    onClick={closeWaitlistModal}
                    disabled={waitlistStatus === 'loading'}
                  >
                    {t.waitlistCancel}
                  </button>
                  <button
                    type="submit"
                    className="waitlist-btn waitlist-btn-primary"
                    disabled={waitlistStatus === 'loading'}
                  >
                    {waitlistStatus === 'loading' ? t.waitlistSubmitting : t.waitlistSubmit}
                  </button>
                </div>
              </form>

              {waitlistFeedback ? (
                <p className={`waitlist-feedback waitlist-feedback-${waitlistStatus}`}>{waitlistFeedback}</p>
              ) : null}
            </Motion.div>
          </Motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}


