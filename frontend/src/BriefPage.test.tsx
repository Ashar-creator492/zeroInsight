// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import BriefPage from './BriefPage'
import { api } from './api'

vi.mock('./api', () => ({ api: { products: vi.fn(), improvementBrief: vi.fn() } }))
vi.mock('recharts', () => ({}))
afterEach(cleanup)

it('renders evidence and an investigation handoff and supports PDF printing', async () => {
  vi.mocked(api.products).mockResolvedValue([{ id: 'luna-smartwatch', name: 'Luna' }])
  vi.mocked(api.improvementBrief).mockResolvedValue({ product_id: 'luna-smartwatch', generated_at: '2026-01-01T00:00:00Z', version: '8', total_reviews: 2, analyzed_reviews: 1, excluded_reviews: 1, complaints: [{ category: 'battery', count: 1, percentage: 100, evidence: [{ review_id: '1', quote: 'Battery drains early', source_url: 'https://example.test' }] }], praised_features: [], recommendations: [], methodology: 'Review frequency', limitations: 'Customer reports' })
  const print = vi.fn()
  vi.stubGlobal('print', print)
  render(<MemoryRouter><BriefPage /></MemoryRouter>)
  expect(await screen.findByText(/1 of 2 reviews/)).toBeTruthy()
  expect(screen.getByText(/Battery drains early/)).toBeTruthy()
  expect(screen.getByRole('link', { name: /Investigate this category/ }).getAttribute('href')).toContain('category=battery')
  fireEvent.click(screen.getByRole('button', { name: /Print or save/ }))
  expect(print).toHaveBeenCalledOnce()
  vi.unstubAllGlobals()
})
