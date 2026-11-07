import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import {
  ArrowLeft, ArrowRight, ArrowUpRight, BarChart3, ChevronLeft, ChevronRight,
  CircleHelp, ExternalLink, Gauge, Home, Layers3, Menu, MessageSquareText,
  RefreshCw, Search, Settings2, Sparkles, Star, Workflow, X,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from './api'
import type { Distribution, Product, Progress, Review, ReviewsPage, Summary, Trend } from './api'
import './dashboard.css'

type OverviewData = { summary: Summary | null; reviews: ReviewsPage | null; trend: Trend | null; progress: Progress | null; sentiment: Distribution | null; complaints: Distribution | null; features: Distribution | null }
const emptyData: OverviewData = { summary: null, reviews: null, trend: null, progress: null, sentiment: null, complaints: null, features: null }
const sentimentColors: Record<string, string> = { positive: '#312b2a', neutral: '#b9aeaa', mixed: '#d8c8c4', negative: '#b61b1c' }
const sentimentOrder = ['positive', 'neutral', 'mixed', 'negative']
const navItems: { label: string; icon: LucideIcon; path?: string }[] = [
  { label: 'Overview', icon: Home, path: '/dashboard' }, { label: 'Review Explorer', icon: Search, path: '/dashboard/reviews' },
  { label: 'Sentiment Analytics', icon: BarChart3, path: '/dashboard/sentiment' }, { label: 'Complaint Intelligence', icon: CircleHelp, path: '/dashboard/complaints' },
  { label: 'AI Insights', icon: Sparkles, path: '/dashboard/insights' }, { label: 'Ask ZeroInsight', icon: MessageSquareText, path: '/dashboard/ask' },
  { label: 'Investigation Center', icon: Workflow, path: '/dashboard/investigations' }, { label: 'Settings & Processing', icon: Settings2, path: '/dashboard/settings' },
]

function titleCase(value: string) { return value.replace(/(^|\s)\S/g, letter => letter.toUpperCase()) }
function displayDate(value: string | null) {
  if (!value) return 'Date unavailable'
  const date = new Date(`${value}T00:00:00Z`)
  return Number.isNaN(date.valueOf()) ? 'Date unavailable' : new Intl.DateTimeFormat('en', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(date)
}
function safeSource(value: string) { try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) ? url.href : undefined } catch { return undefined } }
function recentMonths(points: Trend['points']) {
  if (!points.length) return []
  const sorted = [...points].sort((a, b) => a.month.localeCompare(b.month))
  const counts = new Map(sorted.map(point => [point.month, point.count]))
  const [year, month] = sorted[sorted.length - 1].month.split('-').map(Number)
  const [firstYear, firstMonth] = sorted[0].month.split('-').map(Number)
  const lastIndex = year * 12 + month - 1
  const firstIndex = Math.max(firstYear * 12 + firstMonth - 1, lastIndex - 11)
  return Array.from({ length: lastIndex - firstIndex + 1 }, (_, index) => {
    const current = firstIndex + index
    const key = `${Math.floor(current / 12)}-${String(current % 12 + 1).padStart(2, '0')}`
    const label = new Intl.DateTimeFormat('en', { month: 'short', year: '2-digit', timeZone: 'UTC' }).format(new Date(`${key}-01T00:00:00Z`))
    return { month: key, label, count: counts.get(key) ?? 0 }
  })
}
function Stars({ rating }: { rating: number }) {
  return <span className="d-stars" aria-label={`${rating} out of 5 stars`}>{Array.from({ length: 5 }, (_, i) => <Star key={i} size={13} fill={i < rating ? 'currentColor' : 'none'} strokeWidth={1.4} />)}</span>
}
function Empty({ children }: { children: React.ReactNode }) { return <div className="d-empty">{children}</div> }
function CardTitle({ title, detail }: { title: string; detail?: string }) { return <div className="d-card-title"><h2>{title}</h2>{detail && <span>{detail}</span>}</div> }

export function Sidebar({ collapsed, setCollapsed, mobileOpen, setMobileOpen, productId }: { collapsed: boolean; setCollapsed: (value: boolean) => void; mobileOpen: boolean; setMobileOpen: (value: boolean) => void; productId?: string }) {
  return <>
    {mobileOpen && <button className="d-scrim" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
    <aside className={`d-sidebar ${collapsed ? 'is-collapsed' : ''} ${mobileOpen ? 'is-open' : ''}`}>
      <div className="d-side-brand"><Link to="/" className="d-logo" aria-label="ZeroInsight home">{collapsed ? 'Z' : 'ZeroInsight'}<span>.</span></Link><span className="d-side-kicker">Company intelligence</span><button className="d-mobile-close" aria-label="Close navigation" onClick={() => setMobileOpen(false)}><X size={19} /></button></div>
      <nav className="d-nav" aria-label="Dashboard navigation">{navItems.map(({ label, icon: Icon, path }) => path
        ? <NavLink to={`${path}${productId ? `?product=${encodeURIComponent(productId)}` : ''}`} end={path === '/dashboard'} className={({ isActive }) => `d-nav-item ${isActive ? 'active' : ''}`} key={label} onClick={() => setMobileOpen(false)}><Icon size={18} strokeWidth={1.5} /><span>{label}</span></NavLink>
        : <button className="d-nav-item" key={label} disabled title={`${label} will be available in a later milestone`}><Icon size={18} strokeWidth={1.5} /><span>{label}</span><small>Soon</small></button>)}</nav>
      <div className="d-side-bottom"><Link to="/" className="d-back"><ArrowLeft size={16} /><span>Back to website</span></Link><button className="d-collapse" onClick={() => setCollapsed(!collapsed)} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>{collapsed ? <ChevronRight size={17} /> : <ChevronLeft size={17} />}</button></div>
    </aside>
  </>
}

function ReviewDialog({ review, close }: { review: Review; close: () => void }) {
  useEffect(() => { const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') close() }; window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey) }, [close])
  const source = safeSource(review.source_url)
  return <div className="d-modal-backdrop" onClick={close}><section className="d-modal" role="dialog" aria-modal="true" aria-labelledby="review-title" onClick={event => event.stopPropagation()}><button className="d-modal-close" onClick={close} aria-label="Close review"><X size={19} /></button><p className="d-eyebrow">Customer review · {review.source_id}</p><h2 id="review-title">{review.title || 'Review details'}</h2><div className="d-review-meta"><Stars rating={review.rating} /><span>{displayDate(review.review_date)}</span></div><p className="d-modal-text" dir="auto">{review.review_text}</p>{source && <a className="d-source" href={source} target="_blank" rel="noreferrer">View original source <ExternalLink size={14} /></a>}</section></div>
}

export default function Dashboard() {
  const [products, setProducts] = useState<Product[] | null>(null)
  const [productId, setProductId] = useState('')
  const [productError, setProductError] = useState(false)
  const [data, setData] = useState<OverviewData | null>(null)
  const [refresh, setRefresh] = useState(0)
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [selectedReview, setSelectedReview] = useState<Review | null>(null)
  const closeReview = useCallback(() => setSelectedReview(null), [])

  useEffect(() => {
    const controller = new AbortController()
    setProductError(false)
    api.products(controller.signal).then(items => {
      setProducts(items)
      setProductId(current => items.some(item => item.id === current) ? current : items[0]?.id || '')
      if (!items.length) setData(emptyData)
    }).catch(() => {
      if (!controller.signal.aborted) { setProductError(true); setProducts([]); setProductId(''); setData(emptyData) }
    })
    return () => controller.abort()
  }, [refresh])

  useEffect(() => {
    if (!productId) return
    const controller = new AbortController()
    setData(null)
    const safe = <T,>(request: Promise<T>) => request.catch(() => null)
    Promise.all([safe(api.summary(productId, controller.signal)), safe(api.reviews(productId, controller.signal)), safe(api.trend(productId, controller.signal)), safe(api.progress(productId, controller.signal)), safe(api.sentiment(productId, controller.signal)), safe(api.complaints(productId, controller.signal)), safe(api.features(productId, controller.signal))]).then(([summary, reviews, trend, progress, sentiment, complaints, features]) => { if (!controller.signal.aborted) setData({ summary, reviews, trend, progress, sentiment, complaints, features }) })
    return () => controller.abort()
  }, [productId, refresh])

  const trend = useMemo(() => recentMonths(data?.trend?.points || []), [data?.trend])
  const product = products?.find(item => item.id === productId)
  const summary = data?.summary
  const progress = data?.progress
  const sentiment = data?.sentiment
  const sentimentChart = sentimentOrder.map(name => ({ name, value: sentiment?.counts[name] || 0 })).filter(item => item.value > 0)
  const ratingChart = [1, 2, 3, 4, 5].map(rating => ({ rating: `${rating}★`, count: summary?.rating_distribution[String(rating)] || 0 }))
  const completion = progress?.total_reviews ? (progress.analyzed / progress.total_reviews) * 100 : 0
  const sortedCounts = (distribution: Distribution | null | undefined) => Object.entries(distribution?.counts || {}).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 5)
  const unavailable = (label: string) => <Empty>{label} unavailable. Try refreshing the dashboard.</Empty>

  return <div className={`dashboard ${collapsed ? 'sidebar-collapsed' : ''}`} id="overview">
    <Sidebar collapsed={collapsed} setCollapsed={setCollapsed} mobileOpen={mobileOpen} setMobileOpen={setMobileOpen} productId={productId} />
    <main className="d-main">
      <header className="d-header"><div className="d-header-top"><button className="d-menu-toggle" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu size={20} /></button><p className="d-eyebrow">{product?.name || 'Product intelligence'}</p><div className="d-header-actions"><label className="d-product-select"><span className="sr-only">Select product</span><select value={productId} onChange={event => setProductId(event.target.value)} disabled={!products?.length}>{products?.length ? products.map(item => <option key={item.id} value={item.id}>{item.name}</option>) : <option value="">{productError ? 'Products unavailable' : 'Loading products…'}</option>}</select></label><button className="d-refresh" onClick={() => setRefresh(value => value + 1)} aria-label="Refresh dashboard data" title="Refresh data"><RefreshCw size={17} /></button></div></div><h1>Product Intelligence <em>Dashboard</em></h1><p>Real customer feedback. AI interpretations. Evidence for better decisions.</p></header>
      {productError && <div className="d-banner" role="alert">The backend could not be reached. Check that FastAPI is running, then refresh.</div>}
      {!productError && products?.length === 0 && <div className="d-banner">No products are available yet.</div>}
      <div className={`d-workspace ${product?.id === 'luna-smartwatch' ? '' : 'd-workspace--no-art'}`}><div className="d-content">
        <section className="d-kpis" aria-label="Overview metrics">
          <article className="d-card d-kpi d-kpi-dark"><span className="d-kpi-label">Total Reviews</span><strong>{!data ? '—' : summary ? summary.total_reviews.toLocaleString() : '—'}</strong><small>{summary ? 'Stored customer reviews' : data ? 'Data unavailable' : 'Loading…'}</small><Layers3 className="d-kpi-icon" size={21} /></article>
          <article className="d-card d-kpi"><span className="d-kpi-label">Average Rating</span><strong>{summary?.average_rating != null ? summary.average_rating.toFixed(2) : '—'}<i> / 5</i></strong><div className="d-rating-stars" style={{ backgroundImage: `linear-gradient(90deg, #b51d20 ${(summary?.average_rating || 0) * 20}%, #c9bfba ${(summary?.average_rating || 0) * 20}%)` }} aria-label={summary?.average_rating != null ? `${summary.average_rating.toFixed(2)} out of 5` : 'Rating unavailable'}>★★★★★</div><small>{summary ? 'Based on all rated reviews' : data ? 'Data unavailable' : 'Loading…'}</small></article>
          <article className="d-card d-kpi d-sentiment-kpi"><span className="d-kpi-label">Sentiment <small>(classified)</small></span>{sentiment && sentiment.analyzed_reviews > 0 ? <div className="d-sentiment-inner"><div className="d-donut"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={sentimentChart} dataKey="value" nameKey="name" innerRadius="63%" outerRadius="92%" paddingAngle={1} stroke="none">{sentimentChart.map(item => <Cell key={item.name} fill={sentimentColors[item.name]} />)}</Pie><Tooltip formatter={(value) => [`${value} reviews`, 'Count']} /></PieChart></ResponsiveContainer></div><div className="d-legend">{sentimentOrder.map(name => <div key={name}><span><i style={{ background: sentimentColors[name] }} />{titleCase(name)}</span><b>{sentiment.counts[name] || 0}</b></div>)}</div></div> : <small>{data ? sentiment ? 'No classified reviews yet.' : 'Data unavailable' : 'Loading…'}</small>}<small>{sentiment ? `${sentiment.analyzed_reviews} analyzed · not all reviews` : ''}</small></article>
          <article className="d-card d-kpi d-kpi-red"><span className="d-kpi-label">Classification Progress</span><strong>{progress ? `${completion.toFixed(1)}%` : '—'}</strong><small>{progress ? `${progress.analyzed} / ${progress.total_reviews} reviews analyzed` : data ? 'Data unavailable' : 'Loading…'}</small><div className="d-progress-track"><span style={{ width: `${completion}%` }} /></div><small>{progress ? `${progress.failed} failed · ${progress.pending} pending · v${progress.version}` : ''}</small></article>
        </section>
        <section className="d-charts" aria-label="Review analytics">
          <article className="d-card d-chart-card"><CardTitle title="Rating Distribution" detail="All reviews" />{!data ? <Empty>Loading ratings…</Empty> : !summary ? unavailable('Ratings') : <div className="d-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={ratingChart} margin={{ top: 10, right: 4, left: -25, bottom: 0 }}><CartesianGrid vertical={false} stroke="#d9d1cd" strokeDasharray="2 4" /><XAxis dataKey="rating" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#817875' }} /><YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#817875' }} /><Tooltip formatter={(value) => [`${value} reviews`, 'Count']} cursor={{ fill: '#ddd5d1' }} /><Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={32}>{ratingChart.map((item, index) => <Cell key={item.rating} fill={index === 4 ? '#b61b1c' : '#afa4a0'} />)}</Bar></BarChart></ResponsiveContainer></div>}</article>
          <article className="d-card d-chart-card"><CardTitle title="Review Trend" detail="Monthly · latest 12 months" />{!data ? <Empty>Loading trend…</Empty> : !data.trend ? unavailable('Review trend') : !trend.length ? <Empty>No dated reviews are available.</Empty> : <><div className="d-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={trend} margin={{ top: 10, right: 8, left: -28, bottom: 0 }}><defs><linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#bd3430" stopOpacity={0.26} /><stop offset="100%" stopColor="#bd3430" stopOpacity={0.02} /></linearGradient></defs><CartesianGrid vertical={false} stroke="#d9d1cd" strokeDasharray="2 4" /><XAxis dataKey="label" axisLine={false} tickLine={false} minTickGap={22} tick={{ fontSize: 9, fill: '#817875' }} /><YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#817875' }} /><Tooltip formatter={(value) => [`${value} reviews`, 'Count']} /><Area type="monotone" dataKey="count" stroke="#b61b1c" strokeWidth={2} fill="url(#trendFill)" /></AreaChart></ResponsiveContainer></div><p className="d-card-note">{data.trend.undated_reviews} undated reviews excluded.</p></>}</article>
          <article className="d-card d-chart-card"><CardTitle title="Top Complaint Categories" detail={data?.complaints ? `${data.complaints.analyzed_reviews} analyzed` : undefined} />{!data ? <Empty>Loading complaints…</Empty> : !data.complaints ? unavailable('Complaints') : !sortedCounts(data.complaints).length ? <Empty>No complaints in the analyzed reviews.</Empty> : <div className="d-bar-list">{sortedCounts(data.complaints).map(([name, count]) => <div className="d-bar-row" key={name}><span>{titleCase(name)}</span><div className="d-bar-track"><i style={{ width: `${Math.min(100, count / data.complaints!.analyzed_reviews * 100)}%` }} /></div><b>{count}</b></div>)}</div>}<p className="d-card-note">Customer-reported experiences, not confirmed defects.</p></article>
        </section>
        <section className="d-bottom-grid" aria-label="Review highlights">
          <article className="d-card d-list-card"><CardTitle title="Most Praised Features" detail={data?.features ? `${data.features.analyzed_reviews} analyzed` : undefined} />{!data ? <Empty>Loading features…</Empty> : !data.features ? unavailable('Features') : !sortedCounts(data.features).length ? <Empty>No specific features identified yet.</Empty> : <div className="d-feature-list">{sortedCounts(data.features).map(([name, count]) => <div key={name}><Sparkles size={15} strokeWidth={1.3} /><span>{titleCase(name)}</span><b>{count}</b></div>)}</div>}<p className="d-card-note">Counts reflect classified reviews only.</p></article>
          <article className="d-card d-list-card"><CardTitle title="Recent Reviews" detail="Latest stored" />{!data ? <Empty>Loading reviews…</Empty> : !data.reviews ? unavailable('Reviews') : !data.reviews.items.length ? <Empty>No reviews available.</Empty> : <div className="d-reviews">{data.reviews.items.map(review => <button className="d-review" key={review.id} onClick={() => setSelectedReview(review)}><span className="d-review-meta"><Stars rating={review.rating} /><span>· {displayDate(review.review_date)}</span></span><span className="d-review-text" dir="auto">{review.review_text}</span><ArrowUpRight size={15} /></button>)}</div>}</article>
          <article className="d-card d-insight"><div className="d-insight-head"><Sparkles size={19} strokeWidth={1.4} /><h2>AI Insights</h2></div><div><p>No insight reports yet.</p><span>Evidence-backed observations will appear here when available.</span></div><button disabled>Investigate issue <ArrowRightIcon /></button></article>
        </section>
        {progress && progress.analyzed < progress.total_reviews && <p className="d-coverage"><Gauge size={14} /> Classification covers {progress.analyzed} of {progress.total_reviews} reviews. Sentiment and complaint results describe only that analyzed sample.</p>}
      </div>{product?.id === 'luna-smartwatch' && <aside className="d-product-art" aria-label="Illustrative smartwatch artwork"><div className="d-product-art-label"><span>Luna</span><small>Smartwatch</small></div><div className="d-art-note">Illustrative render</div></aside>}</div>
    </main>
    {selectedReview && <ReviewDialog review={selectedReview} close={closeReview} />}
  </div>
}

function ArrowRightIcon() { return <ArrowRight size={16} /> }
