/**
 * CapturesTab component tests (jsdom + @vue/test-utils + real naive-ui).
 *
 * S2 coverage (docs/full-implementation-design.md §4.4 / §7.1):
 *  - list load + empty state
 *  - per-row delete (success / failure / stopPropagation / drawer close)
 *  - toolbar clear-all via n-popconfirm (confirm / cancel)
 *  - trace three-state rendering (empty / texts / timeline), degraded
 *    fallback with raw-JSON fold, reasoning default-collapsed, tool_call
 *    name/args, detail load failure, row keyboard activation (Enter/Space)
 *  - L4 XSS: raw JSON containing `<script>` renders as literal text
 *
 * naive-ui drawers/popovers/messages teleport into document.body, so
 * assertions read from `document.body` (ProvidersPage.test.ts pattern).
 */

import { defineComponent, h } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { i18n } from '@/locales'
import CapturesTab from '@/pages/debugger/CapturesTab.vue'
import type { DebugCaptureDetail, DebugCaptureSummary } from '@/api/debug'

const debugApiMocks = vi.hoisted(() => ({
  listCaptures: vi.fn(),
  getCapture: vi.fn(),
  deleteCapture: vi.fn(),
  clearCaptures: vi.fn(),
}))

vi.mock('@/api/debug', () => debugApiMocks)

function makeSummary(overrides: Partial<DebugCaptureSummary> = {}): DebugCaptureSummary {
  return {
    id: 'cap-1',
    captured_at: '2026-08-02T00:00:00Z',
    trigger_message_id: 'msg-1',
    channel_id: '123',
    guild_id: null,
    user_id: 'u1',
    user_name: 'user1',
    user_display_name: '',
    trigger_sources: ['keyword'],
    raw_user_message: 'hello world',
    provider: 'openai',
    model: 'gpt-4o',
    ...overrides,
  }
}

function makeDetail(overrides: Partial<DebugCaptureDetail> = {}): DebugCaptureDetail {
  return {
    ...makeSummary(),
    plugin_outputs: [],
    formatted_user_request: 'fmt request',
    system_prompt: 'sys prompt',
    history_for_llm: [],
    llm_messages: [],
    intermediate_llm_responses: [],
    raw_llm_response: 'raw out',
    cleaned_llm_response: 'clean out',
    usage: null,
    ...overrides,
  }
}

/** Mount under NMessageProvider (useMessage) — naive-ui toasts go to body. */
function mountTab(): { wrapper: VueWrapper; card: VueWrapper } {
  const Harness = defineComponent({
    setup() {
      return () => h(NMessageProvider, null, { default: () => h(CapturesTab) })
    },
  })
  const wrapper = mount(Harness, { global: { plugins: [i18n] } })
  return { wrapper, card: wrapper.findComponent(CapturesTab) }
}

/** Open the first row's detail drawer and settle everything. */
async function openFirstDetail(wrapper: VueWrapper): Promise<void> {
  await wrapper.find('.captures-row').trigger('click')
  await flushPromises()
}

function bodyText(): string {
  return document.body.textContent ?? ''
}

function toastText(): string | null {
  return document.querySelector('.n-message')?.textContent ?? null
}

beforeEach(() => {
  debugApiMocks.listCaptures.mockReset()
  debugApiMocks.getCapture.mockReset()
  debugApiMocks.deleteCapture.mockReset()
  debugApiMocks.clearCaptures.mockReset()
  debugApiMocks.listCaptures.mockResolvedValue([makeSummary()])
  debugApiMocks.getCapture.mockResolvedValue(makeDetail())
  debugApiMocks.deleteCapture.mockResolvedValue({ message: 'ok' })
  debugApiMocks.clearCaptures.mockResolvedValue({ message: 'ok' })
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('CapturesTab — list load and empty state', () => {
  it('loads the capture list on mount and shows the empty state', async () => {
    debugApiMocks.listCaptures.mockResolvedValue([])
    const { wrapper } = mountTab()
    await flushPromises()
    expect(debugApiMocks.listCaptures).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('还没有截取到 Discord 触发对话。')
  })

  it('renders a row per capture', async () => {
    debugApiMocks.listCaptures.mockResolvedValue([
      makeSummary({ id: 'cap-1' }),
      makeSummary({ id: 'cap-2', raw_user_message: 'second msg' }),
    ])
    const { wrapper } = mountTab()
    await flushPromises()
    expect(wrapper.findAll('.captures-row').length).toBe(2)
    expect(wrapper.text()).toContain('second msg')
  })
})

describe('CapturesTab — per-row delete', () => {
  it('deletes a capture, toasts success and reloads the list', async () => {
    const { wrapper } = mountTab()
    await flushPromises()
    await wrapper.find('.captures-delete').trigger('click')
    await flushPromises()
    expect(debugApiMocks.deleteCapture).toHaveBeenCalledWith('cap-1')
    expect(debugApiMocks.listCaptures).toHaveBeenCalledTimes(2) // mount + reload
    expect(toastText()).toContain('已删除该条截取记录')
  })

  it('closes the drawer when the deleted capture is the open detail', async () => {
    const { wrapper, card } = mountTab()
    await flushPromises()
    await openFirstDetail(wrapper)
    expect(document.body.querySelector('.n-drawer')).toBeTruthy()
    await wrapper.find('.captures-delete').trigger('click')
    await flushPromises()
    expect(
      (card.vm as unknown as { drawerVisible: boolean }).drawerVisible,
    ).toBe(false)
  })

  it('toasts an error and keeps the list unchanged on failure', async () => {
    debugApiMocks.deleteCapture.mockRejectedValueOnce(new Error('boom'))
    const { wrapper } = mountTab()
    await flushPromises()
    await wrapper.find('.captures-delete').trigger('click')
    await flushPromises()
    expect(toastText()).toContain('删除失败')
    expect(toastText()).toContain('boom')
    expect(debugApiMocks.listCaptures).toHaveBeenCalledTimes(1) // no reload
  })

  it('does not open the row detail when the delete button is clicked', async () => {
    const { wrapper } = mountTab()
    await flushPromises()
    await wrapper.find('.captures-delete').trigger('click')
    await flushPromises()
    expect(debugApiMocks.getCapture).not.toHaveBeenCalled()
  })

  it('qa MEDIUM-1: Enter on the focused delete button does not open the row', async () => {
    const { wrapper } = mountTab()
    await flushPromises()
    await wrapper.find('.captures-delete').trigger('keydown', { key: 'Enter' })
    await flushPromises()
    // @keydown.stop on the delete button: the keydown must not bubble to
    // the row container's Enter handler (which would open the drawer).
    expect(debugApiMocks.getCapture).not.toHaveBeenCalled()
    expect(debugApiMocks.deleteCapture).not.toHaveBeenCalled() // keydown alone never deletes
  })

  it('qa MEDIUM-1: Space on the focused delete button does not activate the row', async () => {
    const { wrapper } = mountTab()
    await flushPromises()
    await wrapper.find('.captures-delete').trigger('keydown', { key: ' ' })
    await flushPromises()
    expect(debugApiMocks.getCapture).not.toHaveBeenCalled()
  })

  it('qa MEDIUM-1: real delete-button activation deletes without opening the detail', async () => {
    const { wrapper } = mountTab()
    await flushPromises()
    const del = wrapper.find('.captures-delete')
    // Browser flow for a focused button: keydown Enter → click (activation).
    await del.trigger('keydown', { key: 'Enter' })
    await del.trigger('click')
    await flushPromises()
    expect(debugApiMocks.deleteCapture).toHaveBeenCalledWith('cap-1')
    expect(debugApiMocks.getCapture).not.toHaveBeenCalled()
  })
})

describe('CapturesTab — clear all (popconfirm)', () => {
  it('clears all captures after confirming and reloads', async () => {
    const { wrapper } = mountTab()
    await flushPromises()
    await wrapper.find('.captures-clear-btn').trigger('click')
    await flushPromises()
    const buttons = Array.from(
      document.querySelectorAll('.n-popconfirm__action .n-button'),
    )
    const confirmBtn = buttons[buttons.length - 1] // positive button is last
    expect(confirmBtn).toBeTruthy()
    await confirmBtn!.dispatchEvent(new MouseEvent('click'))
    await flushPromises()
    expect(debugApiMocks.clearCaptures).toHaveBeenCalledTimes(1)
    expect(debugApiMocks.listCaptures).toHaveBeenCalledTimes(2)
    expect(toastText()).toContain('已清空全部截取记录')
  })

  it('does not call clearCaptures when the popconfirm is cancelled', async () => {
    const { wrapper } = mountTab()
    await flushPromises()
    await wrapper.find('.captures-clear-btn').trigger('click')
    await flushPromises()
    const buttons = document.querySelectorAll('.n-popconfirm__action .n-button')
    await buttons[0]!.dispatchEvent(new MouseEvent('click')) // cancel is first
    await flushPromises()
    expect(debugApiMocks.clearCaptures).not.toHaveBeenCalled()
  })
})

describe('CapturesTab — trace three states in the detail drawer', () => {
  it('shows the empty hint when there are no intermediate outputs', async () => {
    debugApiMocks.getCapture.mockResolvedValue(
      makeDetail({ intermediate_llm_responses: [] }),
    )
    const { wrapper } = mountTab()
    await flushPromises()
    await openFirstDetail(wrapper)
    expect(bodyText()).toContain('Trace 时间线')
    expect(bodyText()).toContain('无中间阶段输出')
  })

  it('renders each string item as a pre block (texts state)', async () => {
    debugApiMocks.getCapture.mockResolvedValue(
      makeDetail({ intermediate_llm_responses: ['chunk one', 'chunk two'] }),
    )
    const { wrapper } = mountTab()
    await flushPromises()
    await openFirstDetail(wrapper)
    expect(bodyText()).toContain('chunk one')
    expect(bodyText()).toContain('chunk two')
    expect(bodyText()).not.toContain('详情解析失败')
  })

  it('renders the timeline with mapped stage labels', async () => {
    debugApiMocks.getCapture.mockResolvedValue(
      makeDetail({
        intermediate_llm_responses: [
          { stage: 'request', name: 'openai · gpt-4o' },
          { stage: 'response', content: 'final answer' },
        ] as unknown as string[],
      }),
    )
    const { wrapper } = mountTab()
    await flushPromises()
    await openFirstDetail(wrapper)
    const nodes = document.querySelectorAll('.tl-node')
    expect(nodes.length).toBe(2)
    expect(nodes[0].getAttribute('data-stage')).toBe('request')
    expect(nodes[0].textContent).toContain('请求')
    expect(nodes[1].textContent).toContain('响应')
    expect(nodes[1].textContent).toContain('final answer')
  })
})

describe('CapturesTab — degraded fallback and reasoning folding', () => {
  it('shows the fallback alert + raw JSON fold for degraded data', async () => {
    debugApiMocks.getCapture.mockResolvedValue(
      makeDetail({
        intermediate_llm_responses: [
          '<script>alert(1)</script>',
          { stage: 'x' },
        ] as unknown as string[],
      }),
    )
    const { wrapper } = mountTab()
    await flushPromises()
    await openFirstDetail(wrapper)
    expect(bodyText()).toContain('详情解析失败，已降级显示原始内容。')
    expect(bodyText()).toContain('原始 JSON')
  })

  it('L4: raw JSON with <script> renders as literal text, never parsed', async () => {
    debugApiMocks.getCapture.mockResolvedValue(
      makeDetail({
        intermediate_llm_responses: [
          '<script>alert(1)</script>',
          { stage: 'x' },
        ] as unknown as string[],
      }),
    )
    const { wrapper } = mountTab()
    await flushPromises()
    await openFirstDetail(wrapper)
    const pre = document.querySelector('.trace-raw-fold pre')
    expect(pre?.textContent).toContain('<script>alert(1)</script>')
    expect(document.querySelectorAll('script').length).toBe(0)
  })

  it('keeps reasoning nodes collapsed by default (details without open)', async () => {
    debugApiMocks.getCapture.mockResolvedValue(
      makeDetail({
        intermediate_llm_responses: [
          { stage: 'reasoning', content: 'think step by step' },
        ] as unknown as string[],
      }),
    )
    const { wrapper } = mountTab()
    await flushPromises()
    await openFirstDetail(wrapper)
    const fold = document.querySelector('.reasoning-fold')
    expect(fold).toBeTruthy()
    expect(fold!.hasAttribute('open')).toBe(false)
    expect(fold!.textContent).toContain('推理')
    expect(fold!.textContent).toContain('think step by step')
  })

  it('shows tool_call name and args in the timeline meta line', async () => {
    debugApiMocks.getCapture.mockResolvedValue(
      makeDetail({
        intermediate_llm_responses: [
          { stage: 'tool_call', name: 'web_search', args: 'q=ela' },
        ] as unknown as string[],
      }),
    )
    const { wrapper } = mountTab()
    await flushPromises()
    await openFirstDetail(wrapper)
    const node = document.querySelector('.tl-node[data-stage="tool_call"]')
    expect(node?.textContent).toContain('web_search')
    expect(node?.textContent).toContain('q=ela')
    expect(document.querySelector('.tl-dot.warn')).toBeTruthy()
  })

  it('labels unknown stages with the generic traceOther label', async () => {
    debugApiMocks.getCapture.mockResolvedValue(
      makeDetail({
        intermediate_llm_responses: [
          { stage: 'weird_stage', content: 'mystery' },
        ] as unknown as string[],
      }),
    )
    const { wrapper } = mountTab()
    await flushPromises()
    await openFirstDetail(wrapper)
    const node = document.querySelector('.tl-node[data-stage="other"]')
    expect(node?.textContent).toContain('weird_stage')
  })
})

describe('CapturesTab — detail errors and row keyboard activation', () => {
  it('shows the detail error message on load failure', async () => {
    debugApiMocks.getCapture.mockRejectedValueOnce(new Error('net down'))
    const { wrapper } = mountTab()
    await flushPromises()
    await openFirstDetail(wrapper)
    expect(bodyText()).toContain('加载截取详情失败')
    expect(bodyText()).toContain('net down')
  })

  it('opens the detail with the Enter key on the row', async () => {
    const { wrapper } = mountTab()
    await flushPromises()
    await wrapper.find('.captures-row').trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(debugApiMocks.getCapture).toHaveBeenCalledWith('cap-1')
  })

  it('opens the detail with the Space key on the row', async () => {
    const { wrapper } = mountTab()
    await flushPromises()
    await wrapper.find('.captures-row').trigger('keydown', { key: ' ' })
    await flushPromises()
    expect(debugApiMocks.getCapture).toHaveBeenCalledWith('cap-1')
  })
})

describe('CapturesTab — drawer lifecycle (perf LOW-1 / perf LOW-2)', () => {
  it('perf LOW-1: closing the drawer releases the detail; reopening re-fetches', async () => {
    const { wrapper, card } = mountTab()
    await flushPromises()
    await openFirstDetail(wrapper)
    expect(debugApiMocks.getCapture).toHaveBeenCalledTimes(1)
    expect((card.vm as unknown as { detail: unknown }).detail).not.toBeNull()
    // Close via the mask click (teleported into body) → @update:show(false).
    const mask = document.querySelector('.n-drawer-mask')
    expect(mask).toBeTruthy()
    ;(mask as HTMLElement).dispatchEvent(new MouseEvent('click'))
    await flushPromises()
    // The payload must be released on close, not kept until the next open.
    expect((card.vm as unknown as { detail: unknown }).detail).toBeNull()
    expect((card.vm as unknown as { detailError: string }).detailError).toBe('')
    // Reopening re-fetches instead of reusing a stale/cached detail.
    await wrapper.find('.captures-row').trigger('click')
    await flushPromises()
    expect(debugApiMocks.getCapture).toHaveBeenCalledTimes(2)
  })

  it('perf LOW-2: list loading resets even when a detail opens mid-refresh', async () => {
    const { wrapper, card } = mountTab()
    await flushPromises() // initial list resolved → row rendered
    // Start a refresh whose response is deferred.
    let resolveList!: (v: DebugCaptureSummary[]) => void
    debugApiMocks.listCaptures.mockImplementationOnce(
      () =>
        new Promise<DebugCaptureSummary[]>((resolve) => {
          resolveList = resolve
        }),
    )
    const pending = (
      card.vm as unknown as { loadCaptures: () => Promise<void> }
    ).loadCaptures()
    await flushPromises()
    // Open a detail while the refresh is still in flight.
    await wrapper.find('.captures-row').trigger('click')
    await flushPromises()
    expect(debugApiMocks.getCapture).toHaveBeenCalledTimes(1)
    // The pending list response resolves afterwards; the list loading flag
    // must reset (shared requestSeq used to drop it → stuck loading=true).
    resolveList([makeSummary({ id: 'cap-2' })])
    await Promise.all([pending, flushPromises()])
    expect((card.vm as unknown as { loading: boolean }).loading).toBe(false)
    expect((card.vm as unknown as { detailLoading: boolean }).detailLoading).toBe(
      false,
    )
  })
})
