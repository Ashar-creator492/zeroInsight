// @vitest-environment jsdom
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { api } from './api'
import { AskPage, InsightsPage, InvestigationsPage, SettingsPage } from './FeaturePages'

vi.mock('./api', () => ({ api: { products: vi.fn(), progress: vi.fn(), complaintBreakdown: vi.fn(), searchReviews: vi.fn(), ask: vi.fn(), investigation: vi.fn(), startInvestigation: vi.fn(), decideInvestigation: vi.fn() } }))
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
afterEach(() => { cleanup(); vi.clearAllMocks(); localStorage.clear() })
const show = (element: ReactNode) => render(<MemoryRouter>{element}</MemoryRouter>)
describe('future AI interfaces', () => {
  it('shows only stored observation and linked review evidence', async () => {
    show(<InsightsPage />)
    expect(await screen.findByText(/1 of 4 analyzed reviews/)).toBeTruthy()
    expect(screen.getAllByText('Battery drains quickly').length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: /Explore the evidence/ }).getAttribute('href')).toContain('category=battery')
    expect((screen.getByRole('button', { name: /Generate recommendation/ }) as HTMLButtonElement).disabled).toBe(true)
  })
  it('sends a question and displays linked evidence', async () => {
    vi.mocked(api.ask).mockResolvedValue({ claims: [{ text: 'A customer liked the battery.', review_ids: ['21'], evidence_quote: 'Battery lasts all day' }], sources: [{ id: 'a', source_id: '21', product_id: product, review_text: 'Battery lasts all day', title: null, rating: 5, review_date: null, source_url: 'https://example.test', similarity: 0.7 }], message: null })
    show(<AskPage />)
    expect(await screen.findByText('No conversations yet.')).toBeTruthy()
    const input = screen.getByLabelText('Ask a question')
    fireEvent.change(input, { target: { value: 'battery?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
    expect(await screen.findByText('A customer liked the battery.')).toBeTruthy()
    expect(screen.getByRole('link', { name: '[21]' }).getAttribute('href')).toBe('#citation-21')
    expect(screen.getByRole('link', { name: /Open review/ }).getAttribute('href')).toContain('search=21')
  })
  it('keeps investigation decisions disabled', async () => {
    show(<InvestigationsPage />)
    expect(await screen.findByText('No reports yet.')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Approve' }) as HTMLButtonElement).disabled).toBe(true)
  })
  it('starts an investigation, saves a revision decision and restores it', async () => {
    const result = { id: '123', status: 'awaiting_review', stage: 'human_approval', request: 'battery', product_id: product, evidence: [{ id: 'a', source_id: '21', product_id: product, review_text: 'Battery drains quickly', title: null, rating: 2, review_date: null, source_url: 'https://example.test', similarity: 0.7, retrieval_query: 'complaint' }], report: { findings: [{ kind: 'reported_problem', text: 'A customer reported short battery life.', citations: [{ review_id: '21', evidence_quote: 'Battery drains quickly' }] }], limitations: 'Limited sample.', evidence_status: 'available' } }
    vi.mocked(api.startInvestigation).mockResolvedValue(result)
    vi.mocked(api.decideInvestigation).mockResolvedValue({ ...result, status: 'request_revision', stage: 'revision_requested', decision: { decision: 'request_revision', notes: 'More evidence', decided_at: '2026-01-01T00:00:00Z' } })
    vi.mocked(api.investigation).mockResolvedValue(result)
    const view = show(<InvestigationsPage />)
    await screen.findByText('No reports yet.')
    fireEvent.change(screen.getByLabelText('Product issue'), { target: { value: 'battery' } })
    fireEvent.click(screen.getByRole('button', { name: 'Start investigation' }))
    expect(await screen.findByText('A customer reported short battery life.')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Review 21' }).getAttribute('href')).toBe('#investigation-review-21')
    fireEvent.change(screen.getByLabelText('Decision notes'), { target: { value: 'More evidence' } })
    fireEvent.click(screen.getByRole('button', { name: 'Request revision' }))
    expect(await screen.findByText(/Human follow-up is required/)).toBeTruthy()
    expect(api.decideInvestigation).toHaveBeenCalledWith('123', 'request_revision', 'More evidence')
    view.unmount()
    show(<InvestigationsPage />)
    expect(await screen.findByText('A customer reported short battery life.')).toBeTruthy()
    expect(api.investigation).toHaveBeenCalledWith('123')
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
