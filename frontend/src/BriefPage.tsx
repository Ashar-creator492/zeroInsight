import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AnalyticsShell, ErrorBox, Skeleton, useProduct } from './AnalyticsPages'
import { api } from './api'
import type { BriefItem, ImprovementBrief } from './api'
import './features.css'
import './brief.css'

function Evidence({ item, product }: { item: BriefItem; product: string }) {
  return <details open><summary>View supporting reviews</summary>{item.evidence.map(row => <blockquote key={row.review_id} dir="auto">“{row.quote}” <Link to={`/dashboard/reviews?product=${encodeURIComponent(product)}&search=${encodeURIComponent(row.review_id)}`}>Review {row.review_id}</Link> {/^https?:\/\//i.test(row.source_url) && <a href={row.source_url} target="_blank" rel="noreferrer">Original source ↗</a>}</blockquote>)}</details>
}

export default function BriefPage() {
  const state = useProduct()
  const [brief, setBrief] = useState<ImprovementBrief | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => {
    if (!state.productId) return
    const controller = new AbortController()
    setBrief(null); setError(false)
    api.improvementBrief(state.productId, controller.signal).then(setBrief).catch(() => { if (!controller.signal.aborted) setError(true) })
    return () => controller.abort()
  }, [state.productId, state.refresh])
  return <AnalyticsShell state={state} eyebrow="Evidence to action" title="Product Improvement Brief" subtitle="A practical review-backed starting point for human decisions.">
    {error ? <ErrorBox retry={state.reload} /> : !brief ? <Skeleton /> : <div className="brief-document">
      <section className="d-card f-card"><p className="d-eyebrow">Executive summary · Version {brief.version}</p><h2>Customer feedback, in context.</h2><p>{brief.analyzed_reviews} of {brief.total_reviews} reviews have completed classifications; {brief.excluded_reviews} are excluded. {brief.complaints.length ? `The most frequently supported reported category is ${brief.complaints[0].category} (${brief.complaints[0].count} reviews).` : 'No supported complaint categories are available.'}</p><p>Generated {new Date(brief.generated_at).toLocaleString()}. Independent analysis; not commissioned or endorsed by the brand.</p><button className="brief-print" onClick={() => { document.querySelectorAll<HTMLDetailsElement>('.brief-document details').forEach(item => { item.open = true }); window.print() }}>Print or save as PDF</button></section>
      <div className="f-insights-grid"><section className="d-card f-card"><h2>Customer-reported complaints</h2>{brief.complaints.length ? brief.complaints.map(item => <article className="f-quote" key={item.category}><strong>{item.category} · {item.count}</strong><p>{item.percentage}% of completed classifications</p><Evidence item={item} product={state.productId} /><Link to={`/dashboard/investigations?product=${encodeURIComponent(state.productId)}&category=${encodeURIComponent(item.category)}`}>Investigate this category →</Link></article>) : <p>No supported complaints available.</p>}</section>
      <section className="d-card f-card"><h2>Praised features</h2>{brief.praised_features.length ? brief.praised_features.map(item => <article className="f-quote" key={item.category}><strong>{item.category} · {item.count}</strong><Evidence item={item} product={state.productId} /></article>) : <p>No supported feature praise available.</p>}</section></div>
      <section className="d-card f-card"><h2>Recommended action plan</h2><p>Priorities rank review frequency; they do not establish severity.</p>{brief.recommendations.length ? brief.recommendations.map(item => <article className="f-quote" key={item.category}><p className="d-eyebrow">{item.priority} review priority</p><h3>{item.category}</h3><p>{item.action}</p><p>{item.rationale} {item.uncertainty}</p><Evidence item={item} product={state.productId} /><Link to={`/dashboard/investigations?product=${encodeURIComponent(state.productId)}&category=${encodeURIComponent(item.category)}`}>Open investigation →</Link></article>) : <p>No evidence-backed opportunities yet.</p>}</section>
      <section className="d-card f-card"><h2>Methodology and limitations</h2><p>{brief.methodology}</p><p>{brief.limitations}</p></section>
    </div>}
  </AnalyticsShell>
}
