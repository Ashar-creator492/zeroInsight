import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, BookOpen, CircleCheck, FileSearch, GitBranch, MessageSquareText, ShieldCheck, Sparkles } from 'lucide-react'
import { api } from './api'
import type { ChatAnswer, ComplaintBreakdown, Investigation, Progress, ReviewsPage } from './api'
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
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<{ question: string; answer: ChatAnswer }[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<number | null>(null)
  const answer = selected === null ? null : messages[selected]?.answer
  async function send(text: string) {
    const value = text.trim()
    if (!value || !state.productId || loading) return
    setLoading(true); setError(''); setQuestion(value)
    try {
      const result = await api.ask(value, state.productId)
      setMessages(previous => [...previous, { question: value, answer: result }])
      setSelected(messages.length); setQuestion('')
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to get an answer. Please try again.') }
    finally { setLoading(false) }
  }
  return <AnalyticsShell state={state} eyebrow="Evidence-backed answers" title="Ask ZeroInsight" subtitle="Explore Luna customer feedback with review-backed answers.">
    <div className="f-workspace"><aside className="d-card f-card f-history"><p className="d-eyebrow">Conversations</p><h2>Chat history</h2>{messages.length ? <div className="f-chat-history">{messages.map((message, index) => <button key={index} onClick={() => setSelected(index)} aria-current={selected === index ? 'true' : undefined}>{message.question}</button>)}</div> : <div className="f-history-empty"><MessageSquareText size={22} /><p>No conversations yet.</p><small>Your questions appear here during this session.</small></div>}<button disabled={loading || !messages.length} onClick={() => { setMessages([]); setSelected(null); setError(''); setQuestion('') }}>New conversation</button></aside>
    <section className="d-card f-chat"><div className="f-chat-head"><div><span className="f-icon"><Sparkles size={18} /></span><div><strong>ZeroInsight assistant</strong><small>Answers from customer reviews</small></div></div><span className="f-tag">Luna reviews</span></div>
    {answer ? <div className="f-chat-conversation" aria-live="polite"><p className="f-user-question" dir="auto">{messages[selected!].question}</p>{answer.message && <p className="f-answer-message" dir="auto">{answer.message}</p>}{answer.claims.map((claim, index) => <p className="f-answer-message" dir="auto" key={index}>{claim.text} {claim.review_ids.map(id => <a key={id} href={`#citation-${encodeURIComponent(id)}`}>[{id}]</a>)}</p>)}<small>Customer reports, not verified product facts. Search results are not representative of all reviews.</small></div> : <div className="f-chat-body"><span className="f-chat-mark"><Sparkles size={27} /></span><h2>Ask better questions.</h2><p>Explore customer experiences and follow citations back to the original reviews.</p><div className="f-suggestions">{['What do customers say about battery life?', 'What do customers say about the display?', 'What do customers say about connectivity?'].map(item => <button key={item} disabled={loading || !state.productId} onClick={() => void send(item)}>{item}</button>)}</div></div>}
    {loading && <p className="f-chat-status" role="status">Searching reviews and preparing an answer…</p>}{error && <p className="f-chat-error" role="alert">{error}</p>}<form className="f-composer" onSubmit={event => { event.preventDefault(); void send(question) }}><label className="sr-only" htmlFor="chat-question">Ask a question</label><input id="chat-question" value={question} onChange={event => setQuestion(event.target.value)} maxLength={500} disabled={loading} placeholder="Ask about Luna customer reviews" /><button disabled={loading || !question.trim() || !state.productId} aria-label="Send message"><ArrowRight size={18} /></button></form></section>
    <aside className="d-card f-card f-citations"><p className="d-eyebrow">Sources</p><h2>Review citations</h2>{answer?.sources.length ? answer.sources.map(source => <article className="f-quote" id={`citation-${encodeURIComponent(source.source_id)}`} key={source.id}><div><strong>Review {source.source_id}</strong><span>{source.rating} / 5</span></div><p dir="auto">{source.review_text}</p><Link to={`/dashboard/reviews?product=${encodeURIComponent(source.product_id)}&search=${encodeURIComponent(source.source_id)}`}>Open review <ArrowRight size={13} /></Link><a href={source.source_url} target="_blank" rel="noreferrer">Original source ↗</a></article>) : <><BookOpen size={25} /><p>Sources for an answer will appear here.</p><small>No supporting reviews to show yet.</small></>}</aside></div>
  </AnalyticsShell>
}

const stages = [{ icon: MessageSquareText, title: 'Request', text: 'Define the question' }, { icon: FileSearch, title: 'Evidence', text: 'Gather customer reports' }, { icon: GitBranch, title: 'Analysis', text: 'Examine patterns' }, { icon: ShieldCheck, title: 'Human review', text: 'Decide what happens next' }]
export function InvestigationsPage() {
  const state = useProduct()
  const [request, setRequest] = useState('')
  const [notes, setNotes] = useState('')
  const [investigation, setInvestigation] = useState<Investigation | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    const id = localStorage.getItem('zeroinsight-investigation-id')
    if (!id) return
    setBusy(true)
    api.investigation(id).then(setInvestigation).catch(err => setError(err instanceof Error ? err.message : 'Unable to restore investigation.')).finally(() => setBusy(false))
  }, [])
  async function start() {
    if (!request.trim() || !state.productId || busy) return
    setBusy(true); setError('')
    try {
      const result = await api.startInvestigation(request.trim(), state.productId)
      localStorage.setItem('zeroinsight-investigation-id', result.id)
      setInvestigation(result)
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to start investigation.') }
    finally { setBusy(false) }
  }
  async function decide(decision: string) {
    if (!investigation || busy) return
    setBusy(true); setError('')
    try { setInvestigation(await api.decideInvestigation(investigation.id, decision, notes)); setNotes('') }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to save decision.') }
    finally { setBusy(false) }
  }
  const awaiting = investigation?.status === 'awaiting_review'
  // Decisions stay unavailable until an authorization mechanism is approved.
  const decisionsEnabled = false
  return <AnalyticsShell state={state} eyebrow="Evidence to action" title="Investigation Center" subtitle="Examine customer-reported issues and review the evidence before deciding.">
    <div className="f-notice"><ShieldCheck size={16} /><span>Customer experiences are reports, not verified product defects. Retrieved reviews are a limited sample.</span></div>
    <section className="d-card f-card"><div className="f-heading"><div><p className="d-eyebrow">Investigation request</p><h2>From question to decision</h2></div><span className="f-tag">{investigation ? investigation.status.replaceAll('_', ' ') : 'Ready'}</span></div>
      <form className="f-composer" onSubmit={event => { event.preventDefault(); void start() }}><label className="sr-only" htmlFor="investigation-request">Product issue</label><input id="investigation-request" value={request} onChange={event => setRequest(event.target.value)} placeholder="Describe a Luna customer-reported issue" maxLength={500} disabled={busy} /><button type="submit" disabled={busy || !request.trim() || !state.productId} aria-label="Start investigation"><ArrowRight size={18} /></button></form>
      {busy && <p role="status">Investigation request in progress. Please wait…</p>}{error && <p className="f-chat-error" role="alert">{error}</p>}
      {investigation && <p>Request: {investigation.request} · Current stage: {investigation.stage.replaceAll('_', ' ')}</p>}
      <div className="f-stages">{stages.map(({ icon: Icon, title, text }, index) => <div className="f-stage" key={title}><div className="f-stage-number">0{index + 1}</div><span className="f-stage-icon"><Icon size={20} /></span><strong>{title}</strong><small>{text}</small></div>)}</div></section>
    <div className="f-invest-grid"><section className="d-card f-card"><p className="d-eyebrow">Review evidence</p><h2>Evidence panel</h2>{investigation?.evidence?.length ? investigation.evidence.map(review => <article className="f-quote" id={`investigation-review-${encodeURIComponent(review.source_id)}`} key={review.id}><div><strong>Review {review.source_id}</strong><span>{review.rating} / 5</span></div>{review.title && <strong dir="auto">{review.title}</strong>}<p dir="auto">{review.review_text}</p><Link to={`/dashboard/reviews?product=${encodeURIComponent(review.product_id)}&search=${encodeURIComponent(review.source_id)}`}>Open review <ArrowRight size={13} /></Link> <a href={review.source_url} target="_blank" rel="noreferrer">Original source ↗</a></article>) : <div className="f-placeholder"><FileSearch size={25} /><p>No investigation evidence yet.</p></div>}</section>
    <section className="d-card f-card"><p className="d-eyebrow">Investigation report</p><h2>Report &amp; findings</h2>{investigation?.report ? <><p>{investigation.report.limitations}</p>{investigation.report.findings.length ? investigation.report.findings.map((finding, index) => <article className="f-quote" key={index}><strong>{finding.kind.replaceAll('_', ' ')}</strong><p dir="auto">{finding.text}</p>{finding.citations.map((citation, i) => <blockquote dir="auto" key={i}>“{citation.evidence_quote}” <a href={`#investigation-review-${encodeURIComponent(citation.review_id)}`}>Review {citation.review_id}</a></blockquote>)}</article>) : <p>Insufficient evidence to make a supported finding.</p>}</> : <div className="f-placeholder"><BookOpen size={25} /><p>No reports yet.</p></div>}</section>
    <section className="d-card f-card f-approval"><p className="d-eyebrow">Human decision</p><h2>Approval</h2><p>{awaiting ? 'Review the report and evidence before making a decision.' : investigation?.decision ? `Decision: ${investigation.decision.decision.replaceAll('_', ' ')} · ${new Date(investigation.decision.decided_at).toLocaleString()}` : 'No report is awaiting review.'}</p>{investigation?.decision?.notes && <p dir="auto">Notes: {investigation.decision.notes}</p>}{investigation?.decision?.decision === 'request_revision' && <p>Human follow-up is required. Automatic revision is not available.</p>}
      <label htmlFor="investigation-notes">Decision notes</label><textarea id="investigation-notes" className="f-invest-notes" maxLength={2000} value={notes} onChange={event => setNotes(event.target.value)} disabled={!awaiting || busy || !decisionsEnabled} /><div className="f-approval-actions"><button disabled={!awaiting || busy || !decisionsEnabled} onClick={() => void decide('approve')}>Approve</button><button disabled={!awaiting || busy || !decisionsEnabled} onClick={() => void decide('reject')}>Reject</button><button disabled={!awaiting || busy || !decisionsEnabled} onClick={() => void decide('request_revision')}>Request revision</button></div><small>Decisions are unavailable until authorization is configured. No external action is taken.</small></section></div>
  </AnalyticsShell>
}

export function SettingsPage() {
  const state = useProduct()
  const { progress, error } = useProgress(state.productId, state.refresh)
  return <AnalyticsShell state={state} eyebrow="Workspace configuration" title="Settings & Processing" subtitle="Review the current classification state and processing availability.">
    {error ? <ErrorBox retry={state.reload} /> : !progress ? <Skeleton /> : <><Coverage progress={progress} /><div className="f-settings-grid"><section className="d-card f-card f-settings-main"><div className="f-heading"><div><p className="d-eyebrow">Classification</p><h2>Processing overview</h2></div><span className="f-tag">Read only</span></div><div className="f-settings-counts"><div><strong>{progress.analyzed}</strong><span>Completed</span></div><div><strong>{progress.failed}</strong><span>Failed</span></div><div><strong>{progress.pending}</strong><span>Pending</span></div></div><div className="f-setting-row"><span>Classification version</span><strong>Version {progress.version}</strong></div><div className="f-setting-row"><span>Configured model</span><strong>{progress.model_name}</strong></div><div className="f-setting-row"><span>Rate-limit cooldown</span><strong>{progress.cooldown_until ? new Date(progress.cooldown_until).toLocaleString() : 'None reported'}</strong></div><div className="f-setting-row"><span>Live processing status</span><strong>Not available</strong></div><p className="f-muted">Counts reflect the configured model and classification version. Live job activity is not exposed by the backend.</p></section><section className="d-card f-card f-dark"><span className="f-icon"><CircleCheck size={20} /></span><p className="d-eyebrow">Future controls</p><h2>Batch processing</h2><p>Batch controls are not connected. Existing classifications and reviews remain unchanged.</p><div className="f-future-controls"><button disabled>Start batch</button><button disabled>Retry failed</button></div><small>Processing requires a future implementation and approval.</small></section></div></>}
  </AnalyticsShell>
}
