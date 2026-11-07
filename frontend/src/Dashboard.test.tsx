// @vitest-environment jsdom
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { api } from './api'
import Dashboard from './Dashboard'

vi.mock('./api', () => ({ api: { products: vi.fn(), summary: vi.fn(), reviews: vi.fn(), trend: vi.fn(), progress: vi.fn(), sentiment: vi.fn(), complaints: vi.fn(), features: vi.fn() } }))
vi.mock('recharts', () => {
  const Box = ({ children }: { children?: ReactNode }) => <div>{children}</div>
  return { Area: Box, AreaChart: () => <div />, Bar: Box, BarChart: () => <div />, CartesianGrid: Box, Cell: Box, Pie: Box, PieChart: () => <div />, ResponsiveContainer: Box, Tooltip: Box, XAxis: Box, YAxis: Box }
})

beforeEach(() => {
  vi.mocked(api.products).mockResolvedValue([{ id: 'luna-smartwatch', name: 'Luna Smartwatch' }])
  vi.mocked(api.summary).mockResolvedValue({ product_id: 'luna-smartwatch', total_reviews: 10, average_rating: 4.2, rating_distribution: { '1': 1, '2': 0, '3': 1, '4': 2, '5': 6 } })
  vi.mocked(api.reviews).mockResolvedValue({ items: [{ id: 'a', source_id: '1', product_id: 'luna-smartwatch', review_text: 'Sample review', title: null, rating: 4, review_date: '2026-10-01', source_url: 'https://example.test/review' }], total: 10, page: 1, page_size: 3 })
  vi.mocked(api.trend).mockResolvedValue({ product_id: 'luna-smartwatch', points: [{ month: '2026-10', count: 10 }], undated_reviews: 0 })
  vi.mocked(api.progress).mockResolvedValue({ product_id: 'luna-smartwatch', model_name: 'test', version: '7', total_reviews: 10, analyzed: 4, failed: 1, pending: 5, cooldown_until: null })
  vi.mocked(api.sentiment).mockResolvedValue({ product_id: 'luna-smartwatch', analyzed_reviews: 4, counts: { positive: 3, mixed: 1 } })
  vi.mocked(api.complaints).mockResolvedValue({ product_id: 'luna-smartwatch', analyzed_reviews: 4, counts: { battery: 1 } })
  vi.mocked(api.features).mockResolvedValue({ product_id: 'luna-smartwatch', analyzed_reviews: 4, counts: { display: 2 } })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('dashboard overview', () => {
  it('renders stored coverage and opens a review, then refreshes', async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>)
    expect(await screen.findByText('4 / 10 reviews analyzed')).toBeTruthy()
    expect(screen.getByText('1 failed · 5 pending · v7')).toBeTruthy()
    expect(screen.getByText(/Classification covers 4 of 10 reviews/)).toBeTruthy()
    fireEvent.click(screen.getByText('Sample review'))
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.getByRole('link', { name: /View original source/ }).getAttribute('href')).toBe('https://example.test/review')
    fireEvent.click(screen.getByRole('button', { name: 'Close review' }))
    fireEvent.click(screen.getByRole('button', { name: 'Refresh dashboard data' }))
    await waitFor(() => expect(api.products).toHaveBeenCalledTimes(2))
  })

  it('shows a backend error instead of indefinite loading', async () => {
    vi.mocked(api.products).mockRejectedValueOnce(new Error('offline'))
    render(<MemoryRouter><Dashboard /></MemoryRouter>)
    expect((await screen.findByRole('alert')).textContent).toContain('The backend could not be reached')
    expect(screen.getAllByText(/Data unavailable/i).length).toBeGreaterThan(0)
  })

  it('opens and closes the mobile navigation without enabling unfinished pages', async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>)
    await screen.findByText('4 / 10 reviews analyzed')
    fireEvent.click(screen.getByRole('button', { name: 'Open navigation' }))
    expect(screen.getAllByRole('button', { name: 'Close navigation' }).length).toBeGreaterThan(0)
    expect(document.querySelector('.d-sidebar')?.classList.contains('is-open')).toBe(true)
    expect((screen.getByRole('button', { name: /Review Explorer/ }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(screen.getAllByRole('button', { name: 'Close navigation' })[0])
    expect(document.querySelector('.d-sidebar')?.classList.contains('is-open')).toBe(false)
  })
})
