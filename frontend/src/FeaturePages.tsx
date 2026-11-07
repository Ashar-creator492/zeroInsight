import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, BookOpen, CircleCheck, FileSearch, GitBranch, LockKeyhole, MessageSquareText, ShieldCheck, Sparkles } from 'lucide-react'
import { api } from './api'
import type { ComplaintBreakdown, Progress, ReviewsPage } from './api'
import { AnalyticsShell, Coverage, ErrorBox, Skeleton, useProduct } from './AnalyticsPages'
import './features.css'

const label = (value: string) => value.replace(/(^|\s)\S/g, letter => letter.toUpperCase())

function useProgress(productId: string, refresh: number) {
  const [progress, setProgress] = useState<Progress | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => {
    if (!productId) return
    const controller = new AbortController()
    setProgress(null); setError(false)
    api.progress(productId, controller.signal).then(setProgress).catch(() => { if (!controller.signal.aborted) setError(true) })
    return () => controller.abort()
  }, [productId, refresh])
  return { progress, error }
}

export function InsightsPage() {
  const state = useProduct()
  const { progress, error } = useProgress(state.productId, state.refresh)
  const [breakdown, setBreakdown] = useState<ComplaintBreakdown | null>(null)
  const [reviews, setReviews] = useState<ReviewsPage | null>(null)
  const [dataError, setDataError] = useState(false)
  useEffect(() => {
    if (!state.productId) return
    const controller = new AbortController()
    setBreakdown(null); setReviews(null); setDataError(false)
    api.complaintBreakdown(state.productId, controller.signal).then(async data => {
      setBreakdown(data)
      if (data.categories.length) setReviews(await api.searchReviews(state.productId, { complaint: data.categories[0].category, page: 1, page_size: 3 }, controller.signal))
    }).catch(() => { if (!controller.signal.aborted) setDataError(true) })
    return () => controller.abort()
  }, [state.productId, state.refresh])
  const top = breakdown?.categories[0]
  return <AnalyticsShell state={state} eyebrow="Evidence-led decisions" title="AI Insights" subtitle="A closer look at the customer reports behind your next decision.">
    {error || dataError ? <ErrorBox retry={state.reload} /> : !progress || !breakdown || (top && !reviews) ? <Skeleton /> : <>
      <Coverage progress={progress} />
      <div className="f-intro"><div><p className="d-eyebrow">Signals &amp; suggestions</p><h2>Start with the evidence.</h2><p>Classifications are AI interpretations of customer reports, not confirmed defects.</p></div><span className="f-chip"><Sparkles size={14} /> Evidence first</span></div>
      <div className="f-insights-grid"><section className="d-card f-card f-observation"><div className="f-card-top"><span className="f-icon"><FileSearch size={19} /></span><span className="f-tag">Stored observation</span></div>{top ? <><h2>{label(top.category)} reports</h2><p>{top.count} of {breakdown.analyzed_reviews} analyzed reviews mention this complaint category. This small sample is not representative of all reviews.</p><Link className="f-link" to={`/dashboard/complaints?product=${encodeURIComponent(state.productId)}&category=${encodeURIComponent(top.category)}`}>Explore the evidence <ArrowRight size={15} /></Link></> : <><h2>No complaint signals yet</h2><p>Evidence will appear here when completed classifications identify a reported complaint.</p></>}</section>
      <section className="d-card f-card f-dark"><div className="f-card-top"><span className="f-icon"><Sparkles size={19} /></span><span className="f-tag">Coming in a future phase</span></div><h2>Recommendations</h2><p>No AI recommendations have been generated. Future suggestions will be linked to supporting evidence and reviewed by a person.</p><button disabled>Generate recommendation · Coming later</button></section></div>
      <div className="f-insights-grid f-lower"><section className="d-card f-card"><div className="f-heading"><div><p className="d-eyebrow">Customer voice</p><h2>Supporting reviews</h2></div><BookOpen size={19} /></div>{reviews?.items.length ? reviews.items.map(review => <article className="f-quote" key={review.id}><div><strong>Review {review.source_id}</strong><span>{review.rating} / 5</span></div><p dir="auto">{review.review_text}</p>{review.classification?.negative_experiences?.map((quote, i) => <blockquote dir="auto" key={i}>{quote}</blockquote>)}<Link to={`/dashboard/reviews?product=${encodeURIComponent(state.productId)}&search=${encodeURIComponent(review.source_id)}`}>Find review <ArrowRight size={13} /></Link></article>) : <p className="f-muted">No supporting complaint reviews are available.</p>}</section>
      <section className="d-card f-card"><div className="f-heading"><div><p className="d-eyebrow">Human in the loop</p><h2>Investigation &amp; approval</h2></div><ShieldCheck size={20} /></div><p className="f-muted">Investigation reports, suggestions and approval decisions are not available yet.</p><div className="f-status-line"><span>Approval status</span><strong>Not available</strong></div><Link className="f-link" to={`/dashboard/investigations?product=${encodeURIComponent(state.productId)}`}>View investigation workspace <ArrowRight size={15} /></Link></section></div>
    </>}</AnalyticsShell>
}

export function AskPage() {
  const state = useProduct()
  return <AnalyticsShell state={state} eyebrow="Evidence-backed answers" title="Ask ZeroInsight" subtitle="A future workspace for questions grounded in customer feedback.">
    <div className="f-workspace"><aside className="d-card f-card f-history"><p className="d-eyebrow">Conversations</p><h2>Chat history</h2><div className="f-history-empty"><MessageSquareText size={22} /><p>No conversations yet.</p><small>History will appear when the assistant is available.</small></div><button disabled>New conversation · Coming later</button></aside>
    <section className="d-card f-chat"><div className="f-chat-head"><div><span className="f-icon"><Sparkles size={18} /></span><div><strong>ZeroInsight assistant</strong><small>Evidence-backed answers · Future phase</small></div></div><span className="f-tag">Unavailable</span></div><div className="f-chat-body"><span className="f-chat-mark"><Sparkles size={27} /></span><h2>Ask better questions.</h2><p>Review-based answers and citations will be available when the question-answering workflow is implemented.</p><div className="f-suggestions"><button disabled>What do customers say about battery life?</button><button disabled>Which features receive praise?</button><button disabled>What should we investigate?</button></div></div><div className="f-composer"><label className="sr-only" htmlFor="future-question">Ask a question</label><input id="future-question" disabled placeholder="Question answering is coming in a future phase" /><button disabled aria-label="Send message"><ArrowRight size={18} /></button></div></section>
    <aside className="d-card f-card f-citations"><p className="d-eyebrow">Sources</p><h2>Review citations</h2><BookOpen size={25} /><p>Sources for an answer will appear here.</p><small>No answer or citations are available yet.</small></aside></div>
  </AnalyticsShell>
}

const stages = [{ icon: MessageSquareText, title: 'Request', text: 'Define the question' }, { icon: FileSearch, title: 'Evidence', text: 'Gather customer reports' }, { icon: GitBranch, title: 'Analysis', text: 'Examine patterns' }, { icon: ShieldCheck, title: 'Human review', text: 'Decide what happens next' }]
export function InvestigationsPage() {
  const state = useProduct()
  return <AnalyticsShell state={state} eyebrow="Evidence to action" title="Investigation Center" subtitle="A future workflow for examining customer-reported issues.">
    <div className="f-notice"><LockKeyhole size={16} /><span>Investigation workflows and human decisions are planned for Phase 5. No investigations have been run here.</span></div>
    <section className="d-card f-card"><div className="f-heading"><div><p className="d-eyebrow">Planned workflow</p><h2>From question to decision</h2></div><span className="f-tag">Preview only</span></div><div className="f-stages">{stages.map(({ icon: Icon, title, text }, index) => <div className="f-stage" key={title}><div className="f-stage-number">0{index + 1}</div><span className="f-stage-icon"><Icon size={20} /></span><strong>{title}</strong><small>{text}</small></div>)}</div></section>
    <div className="f-invest-grid"><section className="d-card f-card"><p className="d-eyebrow">Review evidence</p><h2>Evidence panel</h2><div className="f-placeholder"><FileSearch size={25} /><p>No investigation evidence yet.</p><small>Supporting reviews will appear after an investigation runs.</small></div></section><section className="d-card f-card"><p className="d-eyebrow">Investigation report</p><h2>Report &amp; findings</h2><div className="f-placeholder"><BookOpen size={25} /><p>No reports yet.</p><small>Findings and uncertainty will be shown with their sources.</small></div></section><section className="d-card f-card f-approval"><p className="d-eyebrow">Human decision</p><h2>Approval</h2><p>No recommendation is awaiting review.</p><div className="f-approval-actions"><button disabled>Approve</button><button disabled>Reject</button><button disabled>Request more evidence</button></div><small>Approval actions will be available in Phase 5.</small></section></div>
  </AnalyticsShell>
}

export function SettingsPage() {
  const state = useProduct()
  const { progress, error } = useProgress(state.productId, state.refresh)
  return <AnalyticsShell state={state} eyebrow="Workspace configuration" title="Settings & Processing" subtitle="Review the current classification state and processing availability.">
    {error ? <ErrorBox retry={state.reload} /> : !progress ? <Skeleton /> : <><Coverage progress={progress} /><div className="f-settings-grid"><section className="d-card f-card f-settings-main"><div className="f-heading"><div><p className="d-eyebrow">Classification</p><h2>Processing overview</h2></div><span className="f-tag">Read only</span></div><div className="f-settings-counts"><div><strong>{progress.analyzed}</strong><span>Completed</span></div><div><strong>{progress.failed}</strong><span>Failed</span></div><div><strong>{progress.pending}</strong><span>Pending</span></div></div><div className="f-setting-row"><span>Classification version</span><strong>Version {progress.version}</strong></div><div className="f-setting-row"><span>Configured model</span><strong>{progress.model_name}</strong></div><div className="f-setting-row"><span>Rate-limit cooldown</span><strong>{progress.cooldown_until ? new Date(progress.cooldown_until).toLocaleString() : 'None reported'}</strong></div><div className="f-setting-row"><span>Live processing status</span><strong>Not available</strong></div><p className="f-muted">Counts reflect the configured model and classification version. Live job activity is not exposed by the backend.</p></section><section className="d-card f-card f-dark"><span className="f-icon"><CircleCheck size={20} /></span><p className="d-eyebrow">Future controls</p><h2>Batch processing</h2><p>Batch controls are not connected. Existing classifications and reviews remain unchanged.</p><div className="f-future-controls"><button disabled>Start batch</button><button disabled>Retry failed</button></div><small>Processing requires a future implementation and approval.</small></section></div></>}
  </AnalyticsShell>
}
