export interface Product { id: string; name: string }
export interface Review {
  id: string
  source_id: string
  product_id: string
  review_text: string
  title: string | null
  rating: number
  review_date: string | null
  source_url: string
}
export interface ReviewsPage { items: Review[]; total: number; page: number; page_size: number }
export interface Summary { product_id: string; total_reviews: number; average_rating: number | null; rating_distribution: Record<string, number> }
export interface Trend { product_id: string; points: { month: string; count: number }[]; undated_reviews: number }
export interface Progress {
  product_id: string; model_name: string; version: string; total_reviews: number
  analyzed: number; failed: number; pending: number; cooldown_until: string | null
}
export interface Distribution { product_id: string; analyzed_reviews: number; counts: Record<string, number> }

const base = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${base}${path}`, { signal })
  if (!response.ok) throw new Error(`Request failed (${response.status})`)
  return response.json() as Promise<T>
}

export const api = {
  products: (signal?: AbortSignal) => get<Product[]>('/api/products', signal),
  summary: (id: string, signal?: AbortSignal) => get<Summary>(`/api/products/${encodeURIComponent(id)}/summary`, signal),
  reviews: (id: string, signal?: AbortSignal) => get<ReviewsPage>(`/api/products/${encodeURIComponent(id)}/reviews?page=1&page_size=3`, signal),
  trend: (id: string, signal?: AbortSignal) => get<Trend>(`/api/products/${encodeURIComponent(id)}/review-trend`, signal),
  progress: (id: string, signal?: AbortSignal) => get<Progress>(`/api/products/${encodeURIComponent(id)}/intelligence/progress`, signal),
  sentiment: (id: string, signal?: AbortSignal) => get<Distribution>(`/api/products/${encodeURIComponent(id)}/intelligence/sentiment`, signal),
  complaints: (id: string, signal?: AbortSignal) => get<Distribution>(`/api/products/${encodeURIComponent(id)}/intelligence/complaints`, signal),
  features: (id: string, signal?: AbortSignal) => get<Distribution>(`/api/products/${encodeURIComponent(id)}/intelligence/praised-features`, signal),
}
