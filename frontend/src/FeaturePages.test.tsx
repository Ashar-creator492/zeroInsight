// @vitest-environment jsdom
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { api } from './api'
import { AskPage, InsightsPage, InvestigationsPage, SettingsPage } from './FeaturePages'

vi.mock('./api', () => ({ api: { products: vi.fn(), progress: vi.fn(), complaintBreakdown: vi.fn(), searchReviews: vi.fn() } }))
vi.mock('recharts', () => {
  const Box = ({ children }: { children?: ReactNode }) => <div>{children}</div>
  return { Area: Box, AreaChart: Box, Bar: Box, BarChart: Box, CartesianGrid: Box, Cell: Box, Pie: Box, PieChart: Box, ResponsiveContainer: Box, Tooltip: Box, XAxis: Box, YAxis: Box }
})
const product = 'luna-smartwatch'
beforeEach(() => {
  vi.mocked(api.products).mockResolvedValue([{ id: product, name: 'Luna Smartwatch' }])
  vi.mocked(api.progress).mockResolvedValue({ product_id: product, model_name: 'test-model', version: '7', total_reviews: 510, analyzed: 4, failed: 1, pending: 505, cooldown_until: null })
  vi.mocked(api.complaintBreakdown).mockResolvedValue({ product_id: product, analyzed_reviews: 4, categories: [{ category: 'battery', count: 1, severity: { medium: 1 } }] })
  vi.mocked(api.searchReviews).mockResolvedValue({ items: [{ id: 'a', source_id: '21', product_id: product, review_text: 'Battery drains quickly', title: null, rating: 2, review_date: null, source_url: 'https://example.test', analysis_status: 'completed', classification: { sentiment: 'negative', complaint_categories: ['battery'], praised_features: [], general_praise: [], negative_experiences: ['Battery drains quickly'], issue_severity: 'medium', investigation_areas: [] } }], total: 1, page: 1, page_size: 3 })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })
const show = (element: ReactNode) => render(<MemoryRouter>{element}</MemoryRouter>)
describe('future AI interfaces', () => {
  it('shows only stored observation and linked review evidence', async () => {
    show(<InsightsPage />)
    expect(await screen.findByText(/1 of 4 analyzed reviews/)).toBeTruthy()
    expect(screen.getAllByText('Battery drains quickly').length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: /Explore the evidence/ }).getAttribute('href')).toContain('category=battery')
    expect((screen.getByRole('button', { name: /Generate recommendation/ }) as HTMLButtonElement).disabled).toBe(true)
  })
  it('provides a disabled chat and citation empty state', async () => {
    show(<AskPage />)
    expect(await screen.findByText('No conversations yet.')).toBeTruthy()
    expect((screen.getByLabelText('Ask a question') as HTMLInputElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Send message' }) as HTMLButtonElement).disabled).toBe(true)
  })
  it('keeps investigation decisions disabled', async () => {
    show(<InvestigationsPage />)
    expect(await screen.findByText('No reports yet.')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Approve' }) as HTMLButtonElement).disabled).toBe(true)
  })
  it('shows stored progress and disables batch processing', async () => {
    show(<SettingsPage />)
    expect(await screen.findByText('Version 7')).toBeTruthy()
    expect(screen.getByText('505')).toBeTruthy()
    expect(screen.getByText('Not available')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Start batch' }) as HTMLButtonElement).disabled).toBe(true)
  })
  it('shows an error when progress cannot be fetched', async () => {
    vi.mocked(api.progress).mockRejectedValue(new Error('offline'))
    show(<SettingsPage />)
    expect((await screen.findByRole('alert')).textContent).toContain('Data could not be loaded')
  })
})
