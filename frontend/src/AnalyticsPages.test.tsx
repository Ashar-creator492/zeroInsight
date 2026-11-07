// @vitest-environment jsdom
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { api } from './api'
import { ComplaintPage, ReviewExplorer, SentimentPage } from './AnalyticsPages'

vi.mock('./api', () => ({ api: { products: vi.fn(), searchReviews: vi.fn(), progress: vi.fn(), sentiment: vi.fn(), sentimentByRating: vi.fn(), complaintBreakdown: vi.fn() } }))
vi.mock('recharts', () => {
  const Box = ({ children }: { children?: ReactNode }) => <div>{children}</div>
  return { Area: Box, AreaChart: () => <div />, Bar: Box, BarChart: () => <div />, CartesianGrid: Box, Cell: Box, Pie: Box, PieChart: () => <div />, ResponsiveContainer: Box, Tooltip: Box, XAxis: Box, YAxis: Box }
})

const review = { id: 'r1', source_id: '1', product_id: 'luna-smartwatch', review_text: 'Battery needs charging often', title: 'Battery', rating: 2, review_date: '2026-10-01', source_url: 'https://example.test/review', analysis_status: 'completed' as const, classification: { sentiment: 'negative', complaint_categories: ['battery'], praised_features: [], general_praise: [], negative_experiences: ['Battery needs charging often'], issue_severity: 'medium', investigation_areas: [] } }

beforeEach(() => {
  vi.mocked(api.products).mockResolvedValue([{ id: 'luna-smartwatch', name: 'Luna Smartwatch' }])
  vi.mocked(api.searchReviews).mockResolvedValue({ items: [review], total: 1, page: 1, page_size: 10 })
  vi.mocked(api.progress).mockResolvedValue({ product_id: 'luna-smartwatch', model_name: 'test', version: '7', total_reviews: 510, analyzed: 4, failed: 1, pending: 505, cooldown_until: null })
  vi.mocked(api.sentiment).mockResolvedValue({ product_id: 'luna-smartwatch', analyzed_reviews: 4, counts: { negative: 1, positive: 3 } })
  vi.mocked(api.sentimentByRating).mockResolvedValue({ product_id: 'luna-smartwatch', analyzed_reviews: 4, ratings: [{ rating: 2, positive: 0, negative: 1, neutral: 0, mixed: 0 }] })
  vi.mocked(api.complaintBreakdown).mockResolvedValue({ product_id: 'luna-smartwatch', analyzed_reviews: 4, categories: [{ category: 'battery', count: 1, severity: { medium: 1 } }] })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('analytics pages', () => {
  it('submits server-side search and opens evidence in the review drawer', async () => {
    render(<MemoryRouter initialEntries={['/dashboard/reviews']}><ReviewExplorer /></MemoryRouter>)
    await screen.findByText('Battery needs charging often')
    fireEvent.change(screen.getByLabelText('Search reviews'), { target: { value: 'battery' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(api.searchReviews).toHaveBeenCalledWith('luna-smartwatch', expect.objectContaining({ search: 'battery', page: 1 }), expect.any(AbortSignal)))
    fireEvent.click(screen.getByRole('button', { name: /View details/ }))
    expect(screen.getByRole('dialog').textContent).toContain('Reported experience')
    expect(screen.getByRole('dialog').textContent).toContain('Battery needs charging often')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('shows limited sentiment coverage and requests supporting reviews on selection', async () => {
    render(<MemoryRouter initialEntries={['/dashboard/sentiment']}><SentimentPage /></MemoryRouter>)
    expect(await screen.findByText(/4 of 510 reviews analyzed/)).toBeTruthy()
    fireEvent.click(screen.getAllByRole('button', { name: /Negative/ })[0])
    await waitFor(() => expect(api.searchReviews).toHaveBeenCalledWith('luna-smartwatch', expect.objectContaining({ sentiment: 'negative' }), expect.any(AbortSignal)))
    expect(await screen.findByText('Battery needs charging often')).toBeTruthy()
  })

  it('shows complaint evidence and a filtered Review Explorer link', async () => {
    render(<MemoryRouter initialEntries={['/dashboard/complaints']}><ComplaintPage /></MemoryRouter>)
    expect(await screen.findByText('Reported experience')).toBeTruthy()
    expect(screen.getByRole('link', { name: /Open in Review Explorer/ }).getAttribute('href')).toContain('complaint=battery')
    expect((screen.getByRole('button', { name: /Investigate issue/ }) as HTMLButtonElement).disabled).toBe(true)
  })
})
