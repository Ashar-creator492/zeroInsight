import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowRight, ExternalLink, Menu, RefreshCw, Search, Star, X } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from './api'
import type { ComplaintBreakdown, Distribution, Product, Progress, RatingSentiment, Review, ReviewsPage } from './api'
import { Sidebar } from './Dashboard'
import './analytics.css'

const sentiments = ['positive', 'negative', 'neutral', 'mixed']
const colors: Record<string, string> = { positive: '#352e2c', negative: '#b51e20', neutral: '#b5aaa5', mixed: '#d7c5c0' }
const categories = ['battery', 'connectivity', 'display', 'charging', 'build quality', 'appearance', 'software/app', 'delivery', 'customer support', 'other']
const label = (value: string) => value.replace(/(^|\s)\S/g, letter => letter.toUpperCase())
const dateLabel = (value: string | null) => value ? new Intl.DateTimeFormat('en', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${value}T00:00:00Z`)) : 'Date unavailable'
const sourceLink = (value: string) => { try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) ? url.href : undefined } catch { return undefined } }

export function useProduct() {
  const [params, setParams] = useSearchParams()
  const [products, setProducts] = useState<Product[] | null>(null)
  const [error, setError] = useState(false)
  const [refresh, setRefresh] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setError(false)
    api.products(controller.signal).then(setProducts).catch(() => { if (!controller.signal.aborted) { setError(true); setProducts([]) } })
    return () => controller.abort()
  }, [refresh])
  const requested = params.get('product')
  const productId = products?.find(product => product.id === requested)?.id || products?.[0]?.id || ''
  const product = products?.find(item => item.id === productId)
  const update = (changes: Record<string, string | null>, resetPage = true) => {
    const next = new URLSearchParams(params)
    Object.entries(changes).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key))
    if (resetPage) next.delete('page')
    setParams(next)
  }
  return { params, products, productId, product, error, refresh, reload: () => setRefresh(value => value + 1), update }
}
type ProductState = ReturnType<typeof useProduct>

export function AnalyticsShell({ state, eyebrow, title, subtitle, children }: { state: ProductState; eyebrow: string; title: string; subtitle: string; children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  return <div className={`dashboard ${collapsed ? 'sidebar-collapsed' : ''}`}><Sidebar collapsed={collapsed} setCollapsed={setCollapsed} mobileOpen={mobileOpen} setMobileOpen={setMobileOpen} productId={state.productId} /><main className="d-main a-main"><header className="d-header"><div className="d-header-top"><button className="d-menu-toggle" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu size={20} /></button><p className="d-eyebrow">{state.product?.name || eyebrow}</p><div className="d-header-actions"><label className="d-product-select"><span className="sr-only">Select product</span><select value={state.productId} onChange={event => state.update({ product: event.target.value })} disabled={!state.products?.length}>{state.products?.length ? state.products.map(product => <option key={product.id} value={product.id}>{product.name}</option>) : <option value="">{state.error ? 'Products unavailable' : 'Loading products…'}</option>}</select></label><button className="d-refresh" aria-label="Refresh page data" title="Refresh data" onClick={state.reload}><RefreshCw size={17} /></button></div></div><h1>{title}</h1><p>{subtitle}</p></header>{state.error ? <div className="d-banner" role="alert">The backend could not be reached. Check FastAPI and refresh.</div> : state.products?.length === 0 ? <div className="d-banner">No products are available.</div> : children}</main></div>
}

function Stars({ rating }: { rating: number }) { return <span className="d-stars" aria-label={`${rating} out of 5 stars`}>{Array.from({ length: 5 }, (_, index) => <Star key={index} size={13} fill={index < rating ? 'currentColor' : 'none'} strokeWidth={1.4} />)}</span> }
export function Skeleton() { return <div className="a-skeleton" role="status" aria-label="Loading data"><span /><span /><span /></div> }
function Empty({ children }: { children: React.ReactNode }) { return <div className="a-empty">{children}</div> }
export function ErrorBox({ retry }: { retry: () => void }) { return <div className="a-error" role="alert">Data could not be loaded. <button onClick={retry}>Try again</button></div> }
export function Coverage({ progress }: { progress: Progress | null }) {
  if (!progress) return <div className="a-coverage">Classification coverage unavailable.</div>
  const percent = progress.total_reviews ? (progress.analyzed / progress.total_reviews * 100).toFixed(1) : '0.0'
  return <div className="a-coverage"><strong>{progress.analyzed} of {progress.total_reviews} reviews analyzed · {percent}%</strong><span>Version {progress.version} · {progress.failed} failed · {progress.pending} pending. Results describe only the analyzed sample and are not representative of all reviews.</span></div>
}

function ReviewDrawer({ review, close }: { review: Review; close: () => void }) {
  const panel = useRef<HTMLElement>(null)
  const closeButton = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    closeButton.current?.focus()
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close()
      if (event.key === 'Tab' && panel.current) {
        const nodes = Array.from(panel.current.querySelectorAll<HTMLElement>('button:not([disabled]), a[href]'))
        if (!nodes.length) return
        if (event.shiftKey && document.activeElement === nodes[0]) { event.preventDefault(); nodes[nodes.length - 1].focus() }
        else if (!event.shiftKey && document.activeElement === nodes[nodes.length - 1]) { event.preventDefault(); nodes[0].focus() }
      }
    }
    document.addEventListener('keydown', keydown)
    return () => { document.removeEventListener('keydown', keydown); previous?.focus() }
  }, [close])
  const analysis = review.classification
  const source = sourceLink(review.source_url)
  return <div className="d-modal-backdrop a-drawer-backdrop" onMouseDown={close}><section ref={panel} className="d-modal a-drawer" role="dialog" aria-modal="true" aria-labelledby="a-review-title" onMouseDown={event => event.stopPropagation()}><button ref={closeButton} className="d-modal-close" onClick={close} aria-label="Close review details"><X size={19} /></button><p className="d-eyebrow">Review · {review.source_id}</p><h2 id="a-review-title">{review.title || 'Customer review'}</h2><div className="d-review-meta"><Stars rating={review.rating} /><span>· {dateLabel(review.review_date)}</span></div><p className="d-modal-text" dir="auto">{review.review_text}</p><div className="a-detail-block"><span>Classification</span>{analysis && review.analysis_status === 'completed' ? <><strong>{label(analysis.sentiment || 'Unspecified')}</strong><p>Complaint categories: {analysis.complaint_categories?.length ? analysis.complaint_categories.map(label).join(', ') : 'None identified'}</p><p>Reported severity: {analysis.issue_severity ? label(analysis.issue_severity) : 'Unavailable'}</p>{analysis.praised_features?.map((feature, index) => <div className="a-evidence" key={`${feature.category}-${index}`}><small>Praised · {label(feature.category)}</small><q dir="auto">{feature.evidence_quote}</q></div>)}{analysis.negative_experiences?.map((quote, index) => <div className="a-evidence" key={index}><small>Reported experience</small><q dir="auto">{quote}</q></div>)}</> : <><strong>Not yet analyzed</strong>{review.analysis_status === 'failed' && <p>The latest analysis attempt failed.</p>}</>}</div>{source && <a className="d-source" href={source} target="_blank" rel="noreferrer">View original source <ExternalLink size={14} /></a>}</section></div>
}

function ReviewList({ page, open, showEvidence = false }: { page: ReviewsPage; open: (review: Review) => void; showEvidence?: boolean }) {
  return <div className="a-review-list">{page.items.map(review => <article className="a-review-card" key={review.id}><div className="a-review-top"><Stars rating={review.rating} /><span>{dateLabel(review.review_date)}</span><span className="a-review-status">{review.classification && review.analysis_status === 'completed' ? label(review.classification.sentiment || 'Analyzed') : 'Not yet analyzed'}</span></div>{review.title && <h3 dir="auto">{review.title}</h3>}<p dir="auto">{review.review_text}</p>{showEvidence && review.classification?.negative_experiences?.map((quote, index) => <div className="a-inline-evidence" key={index}><small>Reported experience</small><q dir="auto">{quote}</q></div>)}<div className="a-review-actions"><button onClick={() => open(review)}>View details <ArrowRight size={14} /></button>{sourceLink(review.source_url) && <a href={sourceLink(review.source_url)} target="_blank" rel="noreferrer">Original source <ExternalLink size={13} /></a>}</div></article>)}</div>
}

function Pagination({ page, total, pageSize, change }: { page: number; total: number; pageSize: number; change: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return <div className="a-pagination"><span>{total ? `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} of ${total}` : '0 reviews'}</span><div><button disabled={page <= 1} onClick={() => change(page - 1)}>Previous</button><span>Page {page} of {pages}</span><button disabled={page >= pages} onClick={() => change(page + 1)}>Next</button></div></div>
}

export function ReviewExplorer() {
  const state = useProduct()
  const { params, productId, refresh } = state
  const search = params.get('search') || ''
  const [draft, setDraft] = useState(search)
  const [result, setResult] = useState<ReviewsPage | null>(null)
  const [error, setError] = useState(false)
  const [selected, setSelected] = useState<Review | null>(null)
  const page = Math.max(1, Number(params.get('page')) || 1)
  const sort = params.get('sort') || 'date-desc'
  const query = params.toString()
  useEffect(() => setDraft(search), [search])
  useEffect(() => {
    if (!productId) return
    const controller = new AbortController()
    setResult(null); setError(false)
    const [field, order] = sort.split('-')
    api.searchReviews(productId, { search, rating: params.get('rating') || '', sentiment: params.get('sentiment') || '', complaint: params.get('complaint') || '', sort: field, order, page, page_size: 10 }, controller.signal).then(setResult).catch(() => { if (!controller.signal.aborted) setError(true) })
    return () => controller.abort()
  }, [productId, query, refresh])
  const setFilter = (name: string, value: string) => state.update({ [name]: value || null })
  return <AnalyticsShell state={state} eyebrow="Customer feedback" title="Review Explorer" subtitle="Search and explore the original customer feedback."><section className="a-toolbar d-card"><form onSubmit={event => { event.preventDefault(); setFilter('search', draft.trim()) }} className="a-search"><Search size={17} /><label className="sr-only" htmlFor="review-search">Search reviews</label><input id="review-search" value={draft} onChange={event => setDraft(event.target.value)} placeholder="Search reviews or review ID" /><button type="submit">Search</button></form><div className="a-filters"><label>Rating<select value={params.get('rating') || ''} onChange={event => setFilter('rating', event.target.value)}><option value="">All ratings</option>{[5, 4, 3, 2, 1].map(rating => <option key={rating} value={rating}>{rating} stars</option>)}</select></label><label>Sentiment<select value={params.get('sentiment') || ''} onChange={event => setFilter('sentiment', event.target.value)}><option value="">All sentiments</option>{sentiments.map(value => <option key={value} value={value}>{label(value)}</option>)}</select></label><label>Complaint<select value={params.get('complaint') || ''} onChange={event => setFilter('complaint', event.target.value)}><option value="">All categories</option>{categories.map(value => <option key={value} value={value}>{label(value)}</option>)}</select></label><label>Sort by<select value={sort} onChange={event => setFilter('sort', event.target.value)}><option value="date-desc">Newest first</option><option value="date-asc">Oldest first</option><option value="rating-desc">Highest rating</option><option value="rating-asc">Lowest rating</option></select></label><button className="a-clear" onClick={() => { setDraft(''); state.update({ search: null, rating: null, sentiment: null, complaint: null, sort: null }) }}>Clear filters</button></div></section><div className="a-section-heading"><div><p className="d-eyebrow">Original feedback</p><h2>Customer reviews</h2></div><span>{result ? `${result.total} matching reviews` : ''}</span></div>{error ? <ErrorBox retry={state.reload} /> : !result ? <Skeleton /> : result.items.length ? <><ReviewList page={result} open={setSelected} /><Pagination page={page} total={result.total} pageSize={10} change={value => state.update({ page: String(value) }, false)} /></> : <Empty>No reviews match these filters. Try clearing a filter.</Empty>}{selected && <ReviewDrawer review={selected} close={() => setSelected(null)} />}</AnalyticsShell>
}

export function SentimentPage() {
  const state = useProduct()
  const [progress, setProgress] = useState<Progress | null>(null)
  const [distribution, setDistribution] = useState<Distribution | null>(null)
  const [matrix, setMatrix] = useState<RatingSentiment | null>(null)
  const [reviews, setReviews] = useState<ReviewsPage | null>(null)
  const [error, setError] = useState(false)
  const [reviewError, setReviewError] = useState(false)
  const [selected, setSelected] = useState<Review | null>(null)
  const sentiment = state.params.get('sentiment') || ''
  const page = Math.max(1, Number(state.params.get('page')) || 1)
  useEffect(() => {
    if (!state.productId) return
    const controller = new AbortController(); setDistribution(null); setMatrix(null); setProgress(null); setError(false)
    Promise.all([api.progress(state.productId, controller.signal), api.sentiment(state.productId, controller.signal), api.sentimentByRating(state.productId, controller.signal)]).then(([p, d, m]) => { setProgress(p); setDistribution(d); setMatrix(m) }).catch(() => { if (!controller.signal.aborted) setError(true) })
    return () => controller.abort()
  }, [state.productId, state.refresh])
  useEffect(() => {
    if (!state.productId) return
    const controller = new AbortController(); setReviews(null); setReviewError(false)
    // An empty sentiment means all completed classifications, fetched through each explicit sentiment filter.
    if (!sentiment) return () => controller.abort()
    api.searchReviews(state.productId, { sentiment, page, page_size: 10 }, controller.signal).then(setReviews).catch(() => { if (!controller.signal.aborted) setReviewError(true) })
    return () => controller.abort()
  }, [state.productId, sentiment, page, state.refresh])
  const pie = useMemo(() => sentiments.map(name => ({ name, count: distribution?.counts[name] || 0 })).filter(item => item.count > 0), [distribution])
  return <AnalyticsShell state={state} eyebrow="Customer sentiment" title="Sentiment Analytics" subtitle="Understand the tone of reviews that have been analyzed.">{error ? <ErrorBox retry={state.reload} /> : !distribution || !matrix || !progress ? <Skeleton /> : <><Coverage progress={progress} /><div className="a-analytics-grid"><article className="d-card a-panel"><div className="a-panel-heading"><h2>Sentiment distribution</h2><span>{distribution.analyzed_reviews} analyzed</span></div>{pie.length ? <div className="a-sentiment-chart"><div className="a-pie"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={pie} dataKey="count" nameKey="name" innerRadius="62%" outerRadius="92%" stroke="none">{pie.map(item => <Cell key={item.name} fill={colors[item.name]} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer></div><div className="a-sentiment-buttons">{sentiments.map(name => <button className={sentiment === name ? 'selected' : ''} key={name} onClick={() => state.update({ sentiment: name })}><i style={{ background: colors[name] }} />{label(name)}<strong>{distribution.counts[name] || 0}</strong></button>)}</div></div> : <Empty>No completed classifications yet.</Empty>}</article><article className="d-card a-panel"><div className="a-panel-heading"><h2>Rating & sentiment</h2><span>Classified reviews only</span></div>{matrix.analyzed_reviews ? <div className="a-matrix-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={matrix.ratings}><CartesianGrid vertical={false} stroke="#d9d1cd" strokeDasharray="2 4" /><XAxis dataKey="rating" tickFormatter={value => `${value}★`} axisLine={false} tickLine={false} /><YAxis allowDecimals={false} axisLine={false} tickLine={false} width={25} /><Tooltip />{sentiments.map(name => <Bar key={name} dataKey={name} stackId="sentiment" fill={colors[name]} />)}</BarChart></ResponsiveContainer></div> : <Empty>No rating comparison is available yet.</Empty>}</article></div><div className="a-section-heading"><div><p className="d-eyebrow">Evidence</p><h2>Supporting reviews</h2></div>{sentiment && <Link to={`/dashboard/reviews?product=${encodeURIComponent(state.productId)}&sentiment=${encodeURIComponent(sentiment)}`}>Open in Review Explorer <ArrowRight size={14} /></Link>}</div><div className="a-filter-pills">{sentiments.map(name => <button key={name} className={sentiment === name ? 'selected' : ''} onClick={() => state.update({ sentiment: name })}>{label(name)} · {distribution.counts[name] || 0}</button>)}</div>{!sentiment ? <Empty>Choose a sentiment to view its supporting reviews.</Empty> : reviewError ? <ErrorBox retry={state.reload} /> : !reviews ? <Skeleton /> : reviews.items.length ? <><ReviewList page={reviews} open={setSelected} /><Pagination page={page} total={reviews.total} pageSize={10} change={value => state.update({ page: String(value) }, false)} /></> : <Empty>No reviews in this sentiment.</Empty>}</>}{selected && <ReviewDrawer review={selected} close={() => setSelected(null)} />}</AnalyticsShell>
}

export function ComplaintPage() {
  const state = useProduct()
  const [progress, setProgress] = useState<Progress | null>(null)
  const [breakdown, setBreakdown] = useState<ComplaintBreakdown | null>(null)
  const [reviews, setReviews] = useState<ReviewsPage | null>(null)
  const [error, setError] = useState(false)
  const [reviewError, setReviewError] = useState(false)
  const [selectedReview, setSelectedReview] = useState<Review | null>(null)
  const selected = breakdown?.categories.find(item => item.category === state.params.get('category')) || breakdown?.categories[0]
  const page = Math.max(1, Number(state.params.get('page')) || 1)
  useEffect(() => {
    if (!state.productId) return
    const controller = new AbortController(); setBreakdown(null); setProgress(null); setError(false)
    Promise.all([api.progress(state.productId, controller.signal), api.complaintBreakdown(state.productId, controller.signal)]).then(([p, b]) => { setProgress(p); setBreakdown(b) }).catch(() => { if (!controller.signal.aborted) setError(true) })
    return () => controller.abort()
  }, [state.productId, state.refresh])
  useEffect(() => {
    if (!state.productId || !selected) return
    const controller = new AbortController(); setReviews(null); setReviewError(false)
    api.searchReviews(state.productId, { complaint: selected.category, page, page_size: 10 }, controller.signal).then(setReviews).catch(() => { if (!controller.signal.aborted) setReviewError(true) })
    return () => controller.abort()
  }, [state.productId, selected?.category, page, state.refresh])
  return <AnalyticsShell state={state} eyebrow="Reported experiences" title="Complaint Intelligence" subtitle="Explore customer-reported issues with the reviews behind them.">{error ? <ErrorBox retry={state.reload} /> : !breakdown || !progress ? <Skeleton /> : <><Coverage progress={progress} /><p className="a-disclaimer">These are customer-reported experiences, not confirmed product defects. Severity is an AI interpretation of each review.</p>{!breakdown.categories.length ? <Empty>No complaint categories are present in the analyzed reviews.</Empty> : <><div className="a-analytics-grid"><article className="d-card a-panel"><div className="a-panel-heading"><h2>Reported categories</h2><span>{breakdown.analyzed_reviews} analyzed</span></div><div className="a-complaint-bars">{breakdown.categories.map(item => <button className={selected?.category === item.category ? 'selected' : ''} key={item.category} onClick={() => state.update({ category: item.category })}><span>{label(item.category)}</span><i><b style={{ width: `${breakdown.analyzed_reviews ? item.count / breakdown.analyzed_reviews * 100 : 0}%` }} /></i><strong>{item.count}</strong></button>)}</div></article><article className="d-card a-panel a-category-detail"><p className="d-eyebrow">Selected category</p><h2>{selected ? label(selected.category) : 'Select a category'}</h2><p>{selected?.count || 0} analyzed {selected?.count === 1 ? 'review reports' : 'reviews report'} this category.</p><div className="a-severity"><span>Review-level severity</span>{selected && Object.entries(selected.severity).map(([severity, count]) => <span key={severity}>{label(severity)} <b>{count}</b></span>)}</div><button className="a-disabled-action" disabled>Investigate issue · Phase 5</button></article></div><div className="a-section-heading"><div><p className="d-eyebrow">Evidence</p><h2>{selected ? `${label(selected.category)} reviews` : 'Supporting reviews'}</h2></div>{selected && <Link to={`/dashboard/reviews?product=${encodeURIComponent(state.productId)}&complaint=${encodeURIComponent(selected.category)}`}>Open in Review Explorer <ArrowRight size={14} /></Link>}</div>{reviewError ? <ErrorBox retry={state.reload} /> : !reviews ? <Skeleton /> : reviews.items.length ? <><ReviewList page={reviews} open={setSelectedReview} showEvidence /><Pagination page={page} total={reviews.total} pageSize={10} change={value => state.update({ page: String(value) }, false)} /></> : <Empty>No supporting reviews available.</Empty>}</>}</>}{selectedReview && <ReviewDrawer review={selectedReview} close={() => setSelectedReview(null)} />}</AnalyticsShell>
}
