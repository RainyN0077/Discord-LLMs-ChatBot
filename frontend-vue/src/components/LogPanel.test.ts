/**
 * LogPanel component tests (jsdom + @vue/test-utils + real naive-ui).
 *
 * B4 Wave 3-B coverage for the footer log viewer:
 *  - level filter button group: a click switches the active filter and the
 *    visible rows (toolbar spec, F5)
 *  - truncation note: `truncated` + `droppedCount` drive the
 *    "show last N · hidden M" status bar (MED-1+F5)
 *  - error banner: `error` + `polling` show the next-retry countdown derived
 *    from `retryIntervalMs` (F7)
 *
 * The store is exercised in its real state shape (setup store refs are
 * writable), so the panel renders exactly what the polling loop would set.
 */

import { afterEach, describe, expect, it } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { i18n } from '@/locales'
import LogPanel from '@/components/LogPanel.vue'
import { useLogsStore, type LogRow } from '@/stores/logs'

const ROWS: LogRow[] = [
  { raw: '10:00:00 | ERROR | boom', level: 'ERROR' },
  { raw: '10:00:01 | WARN | slow query', level: 'WARN' },
  { raw: '10:00:02 | INFO | bot started', level: 'INFO' },
  { raw: '10:00:03 | DEBUG | trace 123', level: 'DEBUG' },
]

/** Mount the panel with a fresh pinia whose logs store is pre-seeded. */
function mountPanel(seed: Partial<{ rows: LogRow[]; truncated: boolean; droppedCount: number; error: string | null; polling: boolean; retryIntervalMs: number }> = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useLogsStore()
  if (seed.rows) store.rows = seed.rows
  if (seed.truncated !== undefined) store.truncated = seed.truncated
  if (seed.droppedCount !== undefined) store.droppedCount = seed.droppedCount
  if (seed.error !== undefined) store.error = seed.error
  if (seed.polling !== undefined) store.polling = seed.polling
  if (seed.retryIntervalMs !== undefined) store.retryIntervalMs = seed.retryIntervalMs

  const wrapper = mount(LogPanel, { global: { plugins: [i18n] } })
  return { wrapper, store }
}

function filterButtons(wrapper: VueWrapper): { text: string; element: () => Promise<void> }[] {
  return wrapper.findAll('.log-filter-btn').map((btn) => ({
    text: btn.text(),
    element: () => btn.trigger('click'),
  }))
}

async function clickFilter(wrapper: VueWrapper, label: string): Promise<void> {
  const btn = wrapper
    .findAll('.log-filter-btn')
    .find((b) => b.text() === label)
  if (!btn) throw new Error(`filter button "${label}" not found`)
  await btn.trigger('click')
  await flushPromises()
}

function activeFilter(wrapper: VueWrapper): string {
  return wrapper
    .findAll('.log-filter-btn')
    .filter((b) => b.classes().includes('active'))
    .map((b) => b.text())[0]
}

function visibleLines(wrapper: VueWrapper): string[] {
  return wrapper.findAll('.log-line').map((line) => line.text())
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('LogPanel — level filter button group', () => {
  it('shows every row while the ALL filter is active', async () => {
    const { wrapper } = mountPanel({ rows: ROWS })
    expect(activeFilter(wrapper)).toBe('ALL')
    expect(visibleLines(wrapper)).toEqual(ROWS.map((r) => r.raw))
  })

  it('clicking a level filter shows only matching rows and highlights it', async () => {
    const { wrapper } = mountPanel({ rows: ROWS })

    await clickFilter(wrapper, 'WARN')
    expect(activeFilter(wrapper)).toBe('WARN')
    expect(visibleLines(wrapper)).toEqual(['10:00:01 | WARN | slow query'])

    await clickFilter(wrapper, 'ERROR')
    expect(activeFilter(wrapper)).toBe('ERROR')
    expect(visibleLines(wrapper)).toEqual(['10:00:00 | ERROR | boom'])
  })

  it('clicking ALL again restores the full buffer', async () => {
    const { wrapper } = mountPanel({ rows: ROWS })
    await clickFilter(wrapper, 'DEBUG')
    expect(visibleLines(wrapper)).toEqual(['10:00:03 | DEBUG | trace 123'])

    await clickFilter(wrapper, 'ALL')
    expect(activeFilter(wrapper)).toBe('ALL')
    expect(visibleLines(wrapper)).toHaveLength(4)
  })

  it('renders the full filter set (ALL / ERROR / WARN / INFO / DEBUG / OTHER)', () => {
    const { wrapper } = mountPanel({ rows: [] })
    expect(filterButtons(wrapper).map((b) => b.text)).toEqual([
      'ALL',
      'ERROR',
      'WARN',
      'INFO',
      'DEBUG',
      'OTHER',
    ])
  })
})

describe('LogPanel — truncation status bar (MED-1+F5)', () => {
  it('shows "last N lines" when the buffer is at the cap without drops', async () => {
    const { wrapper } = mountPanel({ rows: ROWS, truncated: true, droppedCount: 0 })
    const note = wrapper.find('.log-panel-limit')
    expect(note.exists()).toBe(true)
    expect(note.text()).toContain('显示最近 500 行')
    expect(note.text()).not.toContain('已隐藏')
  })

  it('appends the hidden count when lines were dropped', async () => {
    const { wrapper } = mountPanel({ rows: ROWS, truncated: true, droppedCount: 5 })
    const note = wrapper.find('.log-panel-limit')
    expect(note.text()).toContain('显示最近 500 行')
    expect(note.text()).toContain('已隐藏 5 行')
  })

  it('hides the status bar when the buffer fits the cap', () => {
    const { wrapper } = mountPanel({ rows: ROWS, truncated: false })
    expect(wrapper.find('.log-panel-limit').exists()).toBe(false)
  })
})

describe('LogPanel — error banner with retry countdown (F7)', () => {
  it('shows the error and the next-retry interval while polling', async () => {
    const { wrapper } = mountPanel({
      rows: ROWS,
      error: 'backend down',
      polling: true,
      retryIntervalMs: 10_000,
    })
    const banner = wrapper.find('.log-panel-error')
    expect(banner.text()).toContain('backend down')
    expect(banner.text()).toContain('10 秒后重试')
  })

  it('omits the retry note when polling is stopped', () => {
    const { wrapper } = mountPanel({
      rows: ROWS,
      error: 'backend down',
      polling: false,
      retryIntervalMs: 60_000,
    })
    const banner = wrapper.find('.log-panel-error')
    expect(banner.text()).toContain('backend down')
    expect(banner.find('.log-retry-note').exists()).toBe(false)
  })

  it('renders no banner while the store is healthy', () => {
    const { wrapper } = mountPanel({ rows: ROWS, error: null })
    expect(wrapper.find('.log-panel-error').exists()).toBe(false)
  })
})
