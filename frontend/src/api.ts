export interface ChatSource { id: string; source_id: string; product_id: string; review_text: string; title: string | null; rating: number; review_date: string | null; source_url: string; similarity: number }
export interface ChatAnswer { claims: { text: string; review_ids: string[]; evidence_quote: string }[]; sources: ChatSource[]; message: string | null }
export interface Investigation {
  id: string; status: string; request: string; product_id: string; stage: string
  evidence?: (ChatSource & { retrieval_query: string })[]
  report?: { findings: { kind: string; text: string; citations: { review_id: string; evidence_quote: string }[] }[]; limitations: string; evidence_status: string }
  decision?: { decision: string; notes: string; decided_at: string }
}
export interface Product { id: string; name: string }
export interface ReviewAnalysis {
  sentiment: string | null; complaint_categories: string[] | null
  praised_features: { category: string; evidence_quote: string }[] | null
  general_praise: string[] | null; negative_experiences: string[] | null
  issue_severity: string | null; investigation_areas: string[] | null
}
export interface Review {
  id: string
  source_id: string
  product_id: string
  review_text: string
  title: string | null
  rating: number
  review_date: string | null
  source_url: string
  analysis_status?: 'completed' | 'failed' | 'pending'
  classification?: ReviewAnalysis | null
}
export interface ReviewsPage { items: Review[]; total: number; page: number; page_size: number }
export interface Summary { product_id: string; total_reviews: number; average_rating: number | null; rating_distribution: Record<string, number> }
export interface Trend { product_id: string; points: { month: string; count: number }[]; undated_reviews: number }
export interface Progress {
  product_id: string; model_name: string; version: string; total_reviews: number
  analyzed: number; failed: number; pending: number; cooldown_until: string | null
}
export interface Distribution { product_id: string; analyzed_reviews: number; counts: Record<string, number> }
export interface RatingSentiment { product_id: string; analyzed_reviews: number; ratings: ({ rating: number } & Record<string, number>)[] }
export interface ComplaintBreakdown { product_id: string; analyzed_reviews: number; categories: { category: string; count: number; severity: Record<string, number> }[] }
export interface ReviewFilters { search?: string; rating?: string; sentiment?: string; complaint?: string; sort?: string; order?: string; page?: number; page_size?: number }

const base = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${base}${path}`, { signal })
  if (!response.ok) throw new Error(`Request failed (${response.status})`)
  return response.json() as Promise<T>
}

export const api = {
  investigation: (id: string) => get<Investigation>(`/api/investigations/${encodeURIComponent(id)}`),
  startInvestigation: (request: string, productId: string) => postInvestigation('/api/investigations', { request, product_id: productId }),
  verifyAdmin: async (token: string) => {
    const response = await fetch(`${base}/api/investigations/authorization`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' })
    if (!response.ok) throw new Error(response.status === 401 ? 'Invalid administrator token.' : 'Unable to verify authorization. Please try again.')
  },
  decideInvestigation: (id: string, decision: string, notes: string, token: string) => postInvestigation(`/api/investigations/${encodeURIComponent(id)}/decision`, { decision, notes }, token),
  ask: async (question: string, productId: string): Promise<ChatAnswer> => {
    const response = await fetch(`${base}/api/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, product_id: productId }) })
    if (!response.ok) {
      const body = await response.json().catch(() => ({}))
      throw new Error(typeof body.detail === 'string' ? body.detail : 'Unable to get an answer. Please try again.')
    }
    return response.json() as Promise<ChatAnswer>
  },
  products: (signal?: AbortSignal) => get<Product[]>('/api/products', signal),
  summary: (id: string, signal?: AbortSignal) => get<Summary>(`/api/products/${encodeURIComponent(id)}/summary`, signal),
  reviews: (id: string, signal?: AbortSignal) => get<ReviewsPage>(`/api/products/${encodeURIComponent(id)}/reviews?page=1&page_size=3`, signal),
  searchReviews: (id: string, filters: ReviewFilters, signal?: AbortSignal) => {
    const query = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => { if (value !== undefined && value !== '') query.set(key, String(value)) })
    return get<ReviewsPage>(`/api/products/${encodeURIComponent(id)}/reviews?${query}`, signal)
  },
  trend: (id: string, signal?: AbortSignal) => get<Trend>(`/api/products/${encodeURIComponent(id)}/review-trend`, signal),
  progress: (id: string, signal?: AbortSignal) => get<Progress>(`/api/products/${encodeURIComponent(id)}/intelligence/progress`, signal),
  sentiment: (id: string, signal?: AbortSignal) => get<Distribution>(`/api/products/${encodeURIComponent(id)}/intelligence/sentiment`, signal),
  complaints: (id: string, signal?: AbortSignal) => get<Distribution>(`/api/products/${encodeURIComponent(id)}/intelligence/complaints`, signal),
  features: (id: string, signal?: AbortSignal) => get<Distribution>(`/api/products/${encodeURIComponent(id)}/intelligence/praised-features`, signal),
  sentimentByRating: (id: string, signal?: AbortSignal) => get<RatingSentiment>(`/api/products/${encodeURIComponent(id)}/intelligence/sentiment-by-rating`, signal),
  complaintBreakdown: (id: string, signal?: AbortSignal) => get<ComplaintBreakdown>(`/api/products/${encodeURIComponent(id)}/intelligence/complaint-breakdown`, signal),
}

async function postInvestigation(path: string, body: object, token?: string): Promise<Investigation> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  const response = await fetch(`${base}${path}`, { method: 'POST', headers, body: JSON.stringify(body) })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(typeof error.detail === 'string' ? error.detail : `Request failed (${response.status})`)
  }
  return response.json() as Promise<Investigation>
}
