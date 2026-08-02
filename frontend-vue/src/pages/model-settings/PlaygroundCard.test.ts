/**
 * PlaygroundCard component tests (jsdom + @vue/test-utils + real naive-ui).
 *
 * S3 coverage (docs/full-implementation-design.md §2.4 / §7.1):
 *  - empty-state guide; empty input blocked with a warning toast
 *  - success: thinking bubble → assistant text + usage line (total falls
 *    back to prompt + completion when absent) + provider/model label
 *  - failure: error bubble + retry button; retry reuses the last user msg
 *  - H2: switching botId while a request is in flight drops the stale
 *    response, clears the chat, and leaves the card sendable again
 *  - disabled prop blocks sending; clear button wipes messages + usage
 *  - >50 message head-trimming; plain-text rendering (<script> never
 *    parsed); no-model guard; 500 LLM_PROVIDER_ERROR generalization
 *
 * sendDirectChat is mocked (`vi.mock('@/api/chat')`); the card is mounted
 * under NMessageProvider so toasts land in document.body.
 */

import { defineComponent, h, nextTick, reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { i18n } from '@/locales'
import PlaygroundCard from '@/pages/model-settings/PlaygroundCard.vue'
import type { DirectChatResponse } from '@/api/chat'

const chatApiMocks = vi.hoisted(() => ({
  sendDirectChat: vi.fn(),
}))

vi.mock('@/api/chat', () => chatApiMocks)

interface MountOptions {
  provider?: string
  modelName?: string
  botId?: string
  disabled?: boolean
}

interface MountResult {
  wrapper: VueWrapper
  card: VueWrapper
  /** Mutate the reactive prop source (used by the H2 bot-switch test). */
  setProp: <K extends keyof Required<MountOptions>>(key: K, value: MountOptions[K]) => void
}

/** Mount under NMessageProvider (useMessage) with a reactive prop source —
 *  props can be mutated at runtime, which is how the H2 bot-switch test
 *  drives the `watch(() => props.botId)` guard. */
function mountCard(opts: MountOptions = {}): MountResult {
  const propsState = reactive({
    provider: opts.provider ?? 'openai',
    modelName: opts.modelName ?? 'gpt-4o',
    botId: opts.botId ?? 'main',
    disabled: opts.disabled ?? false,
  })
  const Harness = defineComponent({
    setup() {
      return () =>
        h(NMessageProvider, null, {
          default: () => h(PlaygroundCard, { ...propsState }),
        })
    },
  })
  const wrapper = mount(Harness, { global: { plugins: [i18n] } })
  return {
    wrapper,
    card: wrapper.findComponent(PlaygroundCard),
    setProp: (key, value) => {
      propsState[key] = value as never
    },
  }
}

function okResponse(overrides: Partial<DirectChatResponse> = {}): DirectChatResponse {
  return {
    success: true,
    response: 'hello back',
    usage: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    provider: 'openai',
    model: 'gpt-4o',
    ...overrides,
  }
}

async function sendText(wrapper: VueWrapper, text: string): Promise<void> {
  await wrapper.find('textarea').setValue(text)
  await wrapper.find('.pg-send-btn').trigger('click')
}

function toastText(): string | null {
  return document.querySelector('.n-message')?.textContent ?? null
}

beforeEach(() => {
  chatApiMocks.sendDirectChat.mockReset()
  chatApiMocks.sendDirectChat.mockResolvedValue(okResponse())
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('PlaygroundCard — empty state and input guard', () => {
  it('shows the empty guide, title and hint initially', () => {
    const { wrapper } = mountCard()
    expect(wrapper.text()).toContain('Playground 测试对话')
    expect(wrapper.text()).toContain('在这里用当前模型测试对话，无需保存配置。')
    expect(wrapper.text()).toContain('测试基于该 Bot 已保存的配置')
  })

  it('blocks an empty/whitespace send with a warning and no API call', async () => {
    const { wrapper } = mountCard()
    await sendText(wrapper, '   ')
    await flushPromises()
    expect(chatApiMocks.sendDirectChat).not.toHaveBeenCalled()
    expect(toastText()).toContain('请输入消息内容')
  })

  it('blocks sending when modelName is not configured (draft guard)', async () => {
    const { wrapper } = mountCard({ modelName: '' })
    await sendText(wrapper, 'hi')
    await flushPromises()
    expect(chatApiMocks.sendDirectChat).not.toHaveBeenCalled()
    expect(toastText()).toContain('请先配置模型名称')
  })

  it('disables the send button when disabled', async () => {
    const { wrapper } = mountCard({ disabled: true })
    const btn = wrapper.find('.pg-send-btn')
    expect(btn.attributes('disabled')).toBeDefined()
    await sendText(wrapper, 'hi')
    await flushPromises()
    expect(chatApiMocks.sendDirectChat).not.toHaveBeenCalled()
  })
})

describe('PlaygroundCard — send flow (four states)', () => {
  it('shows the thinking bubble, then the assistant reply with usage', async () => {
    const { wrapper } = mountCard()
    await sendText(wrapper, 'hi')
    await flushPromises()
    expect(wrapper.text()).toContain('hello back')
    expect(wrapper.text()).not.toContain('正在思考...')
    expect(chatApiMocks.sendDirectChat).toHaveBeenCalledWith({
      messages: [{ role: 'user', content: 'hi' }],
      include_system_prompt: true,
      bot_id: 'main',
    })
    // usage line: exact values + provider/model label
    expect(wrapper.text()).toContain('Token 用量')
    expect(wrapper.text()).toContain('输入 10')
    expect(wrapper.text()).toContain('输出 5')
    expect(wrapper.text()).toContain('总计 15')
    expect(wrapper.text()).toContain('openai / gpt-4o')
  })

  it('shows the thinking bubble and the sending label while in flight', async () => {
    let resolve!: (value: DirectChatResponse) => void
    chatApiMocks.sendDirectChat.mockImplementationOnce(
      () =>
        new Promise<DirectChatResponse>((res) => {
          resolve = res
        }),
    )
    const { wrapper } = mountCard()
    await sendText(wrapper, 'hi')
    // In-flight: thinking bubble + button shows the sending label.
    expect(wrapper.text()).toContain('正在思考...')
    expect(wrapper.text()).toContain('发送中...')
    resolve(okResponse())
    await flushPromises()
    expect(wrapper.text()).toContain('hello back')
    expect(wrapper.text()).not.toContain('正在思考...')
  })

  it('falls back to prompt + completion when total is missing (LOW-16)', async () => {
    chatApiMocks.sendDirectChat.mockResolvedValue(
      okResponse({ usage: { input_tokens: 7, output_tokens: 3 } }),
    )
    const { wrapper } = mountCard()
    await sendText(wrapper, 'hi')
    await flushPromises()
    expect(wrapper.text()).toContain('输入 7')
    expect(wrapper.text()).toContain('输出 3')
    expect(wrapper.text()).toContain('总计 10') // 7 + 3 fallback
  })

  it('renders the assistant response as plain text (script not parsed)', async () => {
    chatApiMocks.sendDirectChat.mockResolvedValue(
      okResponse({ response: '<script>alert(1)</script>' }),
    )
    const { wrapper } = mountCard()
    await sendText(wrapper, 'hi')
    await flushPromises()
    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.text()).toContain('<script>alert(1)</script>')
  })

  it('sends on plain Enter and keeps Shift+Enter for newlines', async () => {
    const { wrapper } = mountCard()
    await wrapper.find('textarea').setValue('keyboard send')
    await wrapper.find('textarea').trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(chatApiMocks.sendDirectChat).toHaveBeenCalledTimes(1)
    expect(chatApiMocks.sendDirectChat).toHaveBeenCalledWith(
      expect.objectContaining({
        messages: [{ role: 'user', content: 'keyboard send' }],
      }),
    )
    // Shift+Enter must not send (multiline input semantics).
    await wrapper.find('textarea').setValue('line two')
    await wrapper.find('textarea').trigger('keydown', { key: 'Enter', shiftKey: true })
    await flushPromises()
    expect(chatApiMocks.sendDirectChat).toHaveBeenCalledTimes(1)
  })

  it('renders an error bubble with a retry button on failure', async () => {
    chatApiMocks.sendDirectChat.mockRejectedValue(new Error('boom'))
    const { wrapper } = mountCard()
    await sendText(wrapper, 'hi')
    await flushPromises()
    expect(wrapper.find('.pg-message[data-role="error"]').exists()).toBe(true)
    // qa LOW-1: the error bubble renders the playground.error i18n key
    // (「发送失败：{error}」), not the raw detail alone.
    expect(wrapper.text()).toContain('发送失败：boom')
    expect(wrapper.find('.pg-retry-btn').exists()).toBe(true)
  })

  it('generalizes 500 LLM_PROVIDER_ERROR into the providerError text (sec-M1)', async () => {
    chatApiMocks.sendDirectChat.mockRejectedValue(
      Object.assign(new Error('LLM provider error. Check backend logs.'), {
        status: 500,
      }),
    )
    const { wrapper } = mountCard()
    await sendText(wrapper, 'hi')
    await flushPromises()
    expect(wrapper.text()).toContain('LLM 提供商错误，请查看后端日志')
    expect(wrapper.text()).not.toContain('Check backend logs')
  })

  it('keeps the raw detail for non-provider errors', async () => {
    chatApiMocks.sendDirectChat.mockRejectedValue(
      Object.assign(new Error('redis down'), { status: 500 }),
    )
    const { wrapper } = mountCard()
    await sendText(wrapper, 'hi')
    await flushPromises()
    expect(wrapper.text()).toContain('发送失败：redis down')
    expect(wrapper.text()).not.toContain('LLM 提供商错误')
  })

  it('qa LOW-2: hides the usage line when the response carries no usage', async () => {
    chatApiMocks.sendDirectChat.mockResolvedValue(okResponse({ usage: undefined }))
    const { wrapper } = mountCard()
    await sendText(wrapper, 'hi')
    await flushPromises()
    expect(wrapper.text()).toContain('hello back')
    expect(wrapper.find('[data-testid="pg-usage"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('输入 0')
  })

  it('qa LOW-4: Enter during an IME composition does not send', async () => {
    const { wrapper } = mountCard()
    await wrapper.find('textarea').setValue('拼音输入')
    // IME composition-confirmation Enter must be ignored.
    await wrapper.find('textarea').trigger('keydown', {
      key: 'Enter',
      isComposing: true,
    })
    await flushPromises()
    expect(chatApiMocks.sendDirectChat).not.toHaveBeenCalled()
    // A plain Enter right after composition still sends normally.
    await wrapper.find('textarea').trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(chatApiMocks.sendDirectChat).toHaveBeenCalledTimes(1)
  })
})

describe('PlaygroundCard — retry, clear, H2 guard, trimming', () => {
  it('retries with the last user message and drops the failed bubble', async () => {
    chatApiMocks.sendDirectChat.mockRejectedValueOnce(new Error('boom'))
    const { wrapper } = mountCard()
    await sendText(wrapper, 'retry me')
    await flushPromises()
    expect(wrapper.find('.pg-retry-btn').exists()).toBe(true)

    chatApiMocks.sendDirectChat.mockResolvedValueOnce(okResponse({ response: 'ok now' }))
    await wrapper.find('.pg-retry-btn').trigger('click')
    await flushPromises()

    expect(chatApiMocks.sendDirectChat).toHaveBeenLastCalledWith(
      expect.objectContaining({
        messages: [{ role: 'user', content: 'retry me' }],
        bot_id: 'main',
      }),
    )
    expect(wrapper.text()).toContain('ok now')
    expect(wrapper.find('.pg-message[data-role="error"]').exists()).toBe(false)
    expect(wrapper.findAll('.pg-message[data-role="user"]').length).toBe(1)
  })

  it('H2: bot switch drops the stale response, clears chat and stays sendable', async () => {
    let resolveFirst!: (value: DirectChatResponse) => void
    chatApiMocks.sendDirectChat.mockImplementationOnce(
      () =>
        new Promise<DirectChatResponse>((resolve) => {
          resolveFirst = resolve
        }),
    )
    const { wrapper, setProp } = mountCard({ botId: 'bot-a' })
    await sendText(wrapper, 'old msg')
    // In-flight; now the user switches to another bot.
    setProp('botId', 'bot-b')
    await nextTick()
    // The stale response arrives afterwards.
    resolveFirst(okResponse({ response: 'stale reply' }))
    await flushPromises()
    // Dropped: no assistant text, chat cleared back to the empty guide.
    expect(wrapper.text()).not.toContain('stale reply')
    expect(wrapper.find('.pg-message[data-role="user"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('在这里用当前模型测试对话，无需保存配置。')
    // sending was reset — the new bot can send immediately.
    chatApiMocks.sendDirectChat.mockResolvedValue(okResponse({ response: 'new reply' }))
    await sendText(wrapper, 'new msg')
    await flushPromises()
    expect(chatApiMocks.sendDirectChat).toHaveBeenLastCalledWith(
      expect.objectContaining({ bot_id: 'bot-b' }),
    )
    expect(wrapper.text()).toContain('new reply')
  })

  it('clears messages and usage with the clear button', async () => {
    const { wrapper } = mountCard()
    await sendText(wrapper, 'hi')
    await flushPromises()
    expect(wrapper.find('[data-testid="pg-usage"]').exists()).toBe(true)

    await wrapper.find('.pg-clear-btn').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('在这里用当前模型测试对话，无需保存配置。')
    expect(wrapper.find('[data-testid="pg-usage"]').exists()).toBe(false)
  })

  it('trims the message list head when it exceeds 50 messages', async () => {
    const { wrapper } = mountCard()
    chatApiMocks.sendDirectChat.mockResolvedValue(
      okResponse({ response: 'ok', usage: null }),
    )
    for (let i = 0; i < 26; i++) {
      await sendText(wrapper, `msg ${i}`)
      await flushPromises()
    }
    // 26 turns × 2 messages = 52 → trimmed to 50 (oldest head dropped).
    expect(wrapper.findAll('.pg-message').length).toBe(50)
    expect(wrapper.text()).not.toContain('msg 0')
    expect(wrapper.text()).toContain('msg 25')
  })
})
