import { useEffect, useState } from 'react'
import { Link, Route, Routes, useLocation } from 'react-router-dom'
import {
  ArrowDownRight, ArrowRight, AudioLines, ChartNoAxesCombined, ChevronDown,
  CircleDot, Headphones, Lightbulb, Menu, MessageSquareText, ScanSearch,
  ShieldCheck, Sparkles, Watch, X,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

const capabilities: { number: string; title: string; text: string; icon: LucideIcon }[] = [
  { number: '01', title: 'Analyze reviews', text: 'Bring customer feedback into a clearer, structured view.', icon: MessageSquareText },
  { number: '02', title: 'Detect complaints', text: 'Surface recurring customer-reported experiences.', icon: ScanSearch },
  { number: '03', title: 'Generate insights', text: 'Connect emerging patterns to the reviews behind them.', icon: Lightbulb },
  { number: '04', title: 'Support decisions', text: 'Give people the context to decide what to investigate.', icon: ShieldCheck },
]

const categories: { label: string; state: string; icon: LucideIcon }[] = [
  { label: 'Smartwatches', state: 'Luna dataset available', icon: Watch },
  { label: 'Earbuds', state: 'Future expansion', icon: AudioLines },
  { label: 'Headphones', state: 'Future expansion', icon: Headphones },
  { label: 'Speakers', state: 'Future expansion', icon: CircleDot },
]

function Brand({ light = false }: { light?: boolean }) {
  return <Link className={`brand ${light ? 'brand--light' : ''}`} to="/" aria-label="ZeroInsight home">ZeroInsight<span className="brand-dot">.</span></Link>
}

function ButtonLink({ children, to, outline = false }: { children: React.ReactNode; to: string; outline?: boolean }) {
  return <Link className={`button ${outline ? 'button--outline' : 'button--red'}`} to={to}>{children}<ArrowRight size={17} strokeWidth={1.6} aria-hidden="true" /></Link>
}

function Header() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [solutionsOpen, setSolutionsOpen] = useState(false)
  const location = useLocation()
  useEffect(() => { setMenuOpen(false); setSolutionsOpen(false) }, [location.pathname])

  return (
    <header className="site-header">
      <div className="header-inner">
        <div className="header-brand"><Brand /><span className="header-divider" /><span className="header-tagline">Customer intelligence platform</span></div>
        <nav className="desktop-nav" aria-label="Main navigation">
          <a href="/#overview">Overview</a>
          <div className="nav-dropdown">
            <button className="nav-dropdown-trigger" aria-expanded={solutionsOpen} aria-controls="solutions-menu" onClick={() => setSolutionsOpen(!solutionsOpen)} onKeyDown={(event) => { if (event.key === 'Escape') setSolutionsOpen(false) }}>
              Solutions <ChevronDown size={13} aria-hidden="true" />
            </button>
            {solutionsOpen && <div id="solutions-menu" className="dropdown-menu"><a href="/#solutions" onClick={() => setSolutionsOpen(false)}>What ZeroInsight does</a><a href="/#how-it-works" onClick={() => setSolutionsOpen(false)}>How it works</a></div>}
          </div>
          <a href="/#products">Products</a>
          <a href="/#about">About</a>
          <ButtonLink to="/dashboard">Get Started</ButtonLink>
        </nav>
        <button className="mobile-toggle" aria-label={menuOpen ? 'Close navigation' : 'Open navigation'} aria-expanded={menuOpen} aria-controls="mobile-menu" onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X size={23} /> : <Menu size={23} />}</button>
      </div>
      {menuOpen && <nav id="mobile-menu" className="mobile-menu" aria-label="Mobile navigation">
        <a href="/#overview" onClick={() => setMenuOpen(false)}>Overview</a>
        <a href="/#solutions" onClick={() => setMenuOpen(false)}>Solutions</a>
        <a href="/#products" onClick={() => setMenuOpen(false)}>Products</a>
        <a href="/#about" onClick={() => setMenuOpen(false)}>About</a>
        <ButtonLink to="/dashboard">Get Started</ButtonLink>
      </nav>}
    </header>
  )
}

function LandingPage() {
  return (
    <>
      <Header />
      <main>
        <section className="hero" id="overview" aria-labelledby="hero-title">
          <div className="hero-art" aria-hidden="true" />
          <div className="hero-content page-width">
            <div className="hero-copy">
              <p className="eyebrow hero-eyebrow">Reviews <span>/</span> Insights <span>/</span> Investigations <span>/</span> Actions</p>
              <h1 id="hero-title">Turn Customer<br />Feedback into<br /><em>Product Intelligence.</em></h1>
              <div className="hero-actions"><ButtonLink to="/dashboard">Explore Platform</ButtonLink><span className="demo-unavailable">Demo coming soon</span></div>
            </div>
          </div>
          <div className="hero-bottom page-width"><span>Independent product intelligence</span><a href="#solutions" aria-label="Explore what ZeroInsight does">Scroll to explore <ArrowDownRight size={15} aria-hidden="true" /></a></div>
        </section>

        <section className="intro section-pad" id="solutions">
          <div className="page-width">
            <div className="section-heading split-heading"><div><p className="eyebrow"><span className="red-mark" /> What ZeroInsight does</p><h2>Make every review<br /><em>mean more.</em></h2></div><p className="section-lead">Customer feedback holds the details behind better product decisions. ZeroInsight brings those details into focus.</p></div>
            <div className="capability-grid">
              {capabilities.map(({ number, title, text, icon: Icon }) => <article className="capability" key={number}><div className="capability-top"><Icon size={22} strokeWidth={1.35} aria-hidden="true" /><span>{number}</span></div><h3>{title}</h3><p>{text}</p></article>)}
            </div>
          </div>
        </section>

        <section className="process-section section-pad" id="how-it-works">
          <div className="page-width process-layout"><div><p className="eyebrow eyebrow--light"><span className="red-mark" /> From feedback to focus</p><h2>A clearer path<br />from <em>voice to action.</em></h2></div><div className="process-content"><p>Keep the customer’s words close to every insight—and the final decision in human hands.</p><ol className="process-list"><li><span>01</span>Customer reviews</li><li><span>02</span>Structured analysis</li><li><span>03</span>Evidence-backed insights</li><li><span>04</span>Human decisions</li></ol></div></div>
        </section>

        <section className="products-section section-pad" id="products">
          <div className="page-width products-layout"><div className="products-copy"><p className="eyebrow"><span className="red-mark" /> Product intelligence</p><h2>One product.<br /><em>A wider vision.</em></h2><p>Luna Smartwatch is the first dataset in ZeroInsight. The platform is designed to grow as more product feedback is provided.</p><p className="image-note">Product renders are illustrative, not official catalog images.</p></div><div className="category-list">{categories.map(({ label, state, icon: Icon }, index) => <div className="category-row" key={label}><span className="category-index">0{index + 1}</span><Icon size={23} strokeWidth={1.3} aria-hidden="true" /><div className="category-name">{label}</div><span className={`category-state ${index === 0 ? 'category-state--available' : ''}`}>{state}</span><ArrowDownRight size={18} strokeWidth={1.4} aria-hidden="true" /></div>)}</div></div>
        </section>

        <section className="platform-section section-pad" aria-labelledby="platform-title">
          <div className="page-width platform-card"><div className="platform-orbit" aria-hidden="true"><span /><span /><span /></div><div className="platform-copy"><p className="eyebrow eyebrow--light"><Sparkles size={15} strokeWidth={1.5} aria-hidden="true" /> The intelligence workspace</p><h2 id="platform-title">See the story<br /><em>behind the stars.</em></h2><p>Explore the workspace designed to bring reviews, sentiment, and customer-reported issues together.</p><ButtonLink to="/dashboard" outline>Enter the workspace</ButtonLink></div><div className="platform-aside"><ChartNoAxesCombined size={24} strokeWidth={1.25} aria-hidden="true" /><span>Designed for<br />evidence-led decisions</span></div></div>
        </section>

        <section className="about-section" id="about"><div className="page-width about-inner"><p className="eyebrow"><span className="red-mark" /> About the project</p><p>ZeroInsight is an independent proof of concept inspired by Zero Lifestyle. It is not an official Zero Lifestyle product or partnership.</p></div></section>
      </main>
      <footer className="site-footer"><div className="page-width footer-inner"><div><Brand light /><p>Customer intelligence, with context.</p></div><div className="footer-links"><a href="#solutions">Solutions</a><a href="#products">Products</a><a href="#about">About</a><Link to="/dashboard">Workspace <ArrowRight size={14} /></Link></div><div className="footer-bottom"><span>Independent proof of concept</span><span>Made for more thoughtful decisions.</span></div></div></footer>
    </>
  )
}

function DashboardComingSoon() {
  return <><Header /><main className="coming-soon"><div className="coming-soon-inner"><p className="eyebrow"><span className="red-mark" /> Product intelligence</p><h1>The workspace<br /><em>is next.</em></h1><p>The dashboard will be connected to the Luna review dataset in the next milestone, after the landing page is approved.</p><Link className="text-link" to="/">Return to the landing page <ArrowRight size={16} /></Link></div></main></>
}

export default function App() {
  return <Routes><Route path="/" element={<LandingPage />} /><Route path="/dashboard" element={<DashboardComingSoon />} /><Route path="*" element={<DashboardComingSoon />} /></Routes>
}
