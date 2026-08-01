/**
 * ProvidersPage component tests (jsdom + @vue/test-utils + real naive-ui).
 *
 * B4 Wave 3-B coverage for the provider switch page:
 *  - picking a provider pre-fills the empty model/base_url fields from
 *    PROVIDER_DEFAULTS (P1-6 parity), without clobbering user-typed values
 *  - the refresh button re-fetches the provider list for the selected bot
 *  - a failed refresh surfaces a message toast (loadFailed)
 *
 * The page's stores are real (pinia); only the API boundary and the
 * PROVIDER_DEFAULTS data module are mocked (Wave 2 pattern).
 */

import { defineComponent, h, nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { NMessageProvider, NSelect } from 'naive-ui'
import { createMemoryHistory, createRouter } from 'vue-router'
import { i18n } from '@/locales'
import ProvidersPage from '@/pages/ProvidersPage.vue'
import { useBotsStore } from '@/stores/bots'
import type { BotSummary } from '@/api/bots'
import type { ProviderInfo } from '@/api/providers'

const botsApiMocks = vi.hoisted(() => ({
  fetchBots: vi.fn(),
  createBot: vi.fn(),
  deleteBot: vi.fn(),
  renameBot: vi.fn(),
  startBot: vi.fn(),
  stopBot: vi.fn(),
  restartBot: vi.fn(),
  exportBotConfig: vi.fn(),
  importBotConfig: vi.fn(),
  getGuilds: vi.fn(),
  getChannels: vi.fn(),
  getRoles: vi.fn(),
  searchMembers: vi.fn(),
  getDiagnostics: vi.fn(),
}))

vi.mock('@/api/bots', () => botsApiMocks)

const providersApiMocks = vi.hoisted(() => ({
  fetchProviders: vi.fn(),
  switchProvider: vi.fn(),
}))

vi.mock('@/api/providers', () => providersApiMocks)

/** Controllable PROVIDER_DEFAULTS so pre-fill assertions never depend on
 *  the real data file drifting. */
const defaultsMocks = vi.hoisted(() => ({
  defaults: {
    deepseek: {
      baseUrl: 'https://mock.deepseek.example/v1',
      defaultModel: 'mock-deepseek-model',
    },
    openai: {
      baseUrl: 'https://mock.openai.example/v1',
      defaultModel: 'mock-gpt-model',
    },
    // A provider without a default model: only base_url may be pre-filled.
    anthropic: { baseUrl: 'https://mock.anthropic.example' },
  },
}))

vi.mock('@/pages/model-settings/providerDefaults', () => ({
  KNOWN_PROVIDERS: ['deepseek'],
  PROVIDER_DEFAULTS: defaultsMocks.defaults,
  LLM_PROVIDER_VALUES: ['deepseek', 'openai', 'anthropic'],
  getProviderBaseUrl: () => '',
}))

const PROVIDERS: ProviderInfo[] = [
  {
    name: 'deepseek',
    model: 'mock-deepseek-model',
    configured: true,
    healthy: true,
    latency_ms: 120,
    is_current: true,
  },
  {
    name: 'openai',
    model: '',
    configured: false,
    healthy: null,
    latency_ms: null,
    is_current: false,
  },
  {
    name: 'anthropic',
    model: '',
    configured: false,
    healthy: null,
    latency_ms: null,
    is_current: false,
  },
]

function makeBot(botId = 'main'): BotSummary {
  return {
    bot_id: botId,
    bot_name: 'Main Bot',
    platform: 'discord',
    enabled: true,
    status: 'running',
    uptime_seconds: 123,
    bot_nickname: '',
    model_name: 'mock-deepseek-model',
    llm_provider: 'deepseek',
    trigger_keywords: [],
  }
}

/** Mount the page under NMessageProvider (useMessage) with a real router. */
function mountPage(): { wrapper: VueWrapper } {
  const pinia = createPinia()
  setActivePinia(pinia)
  const botsStore = useBotsStore()
  botsStore.bots = [makeBot()]
  botsStore.selectedBotId = 'main'

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/',
        name: 'model-settings',
        component: { render: () => h('div') },
      },
    ],
  })

  const Harness = defineComponent({
    setup() {
      return () => h(NMessageProvider, null, { default: () => h(ProvidersPage) })
    },
  })

  const wrapper = mount(Harness, {
    global: { plugins: [i18n, pinia, router] },
  })
  return { wrapper }
}

function providerSelect(wrapper: VueWrapper): InstanceType<typeof NSelect> {
  const comp = wrapper.findComponent(NSelect)
  if (!comp.exists()) throw new Error('provider NSelect not found')
  return comp.vm as InstanceType<typeof NSelect>
}

/** Pick a provider through the real select v-model (update:value event). */
async function pickProvider(wrapper: VueWrapper, name: string): Promise<void> {
  await providerSelect(wrapper).$emit('update:value', name)
  await nextTick()
}

function inputByPlaceholder(wrapper: VueWrapper, placeholder: string): HTMLInputElement {
  const el = wrapper.find(`input[placeholder="${placeholder}"]`)
  if (!el.exists()) throw new Error(`input with placeholder "${placeholder}" not found`)
  return el.element as HTMLInputElement
}

function modelInput(wrapper: VueWrapper): HTMLInputElement {
  return inputByPlaceholder(wrapper, '输入模型名称')
}

function baseUrlInput(wrapper: VueWrapper): HTMLInputElement {
  return inputByPlaceholder(wrapper, '留空使用官方 API，或填写自定义接口地址')
}

function refreshButton(wrapper: VueWrapper): { trigger: () => Promise<void> } {
  const btn = wrapper.findAll('button').find((b) => b.text().includes('刷新'))
  if (!btn) throw new Error('refresh button not found')
  return { trigger: () => btn.trigger('click') }
}

beforeEach(() => {
  providersApiMocks.fetchProviders.mockReset()
  providersApiMocks.switchProvider.mockReset()
  providersApiMocks.fetchProviders.mockResolvedValue({
    current_provider: 'deepseek',
    current_model: 'mock-deepseek-model',
    providers: PROVIDERS,
  })
  botsApiMocks.fetchBots.mockReset()
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('ProvidersPage — default pre-fill on provider switch', () => {
  it('pre-fills model and base_url from PROVIDER_DEFAULTS', async () => {
    const { wrapper } = mountPage()
    await flushPromises() // initial fetch settles

    await pickProvider(wrapper, 'deepseek')
    expect(modelInput(wrapper).value).toBe('mock-deepseek-model')
    expect(baseUrlInput(wrapper).value).toBe('https://mock.deepseek.example/v1')
  })

  it('does not clobber a model the user already typed', async () => {
    const { wrapper } = mountPage()
    await flushPromises()

    await pickProvider(wrapper, 'openai')
    expect(modelInput(wrapper).value).toBe('mock-gpt-model')
    await wrapper.find('input[placeholder="输入模型名称"]').setValue('my-custom-model')

    // The pre-fill is empty-field-only: typed model and the already-filled
    // base_url from the previous provider are both left untouched.
    await pickProvider(wrapper, 'deepseek')
    expect(modelInput(wrapper).value).toBe('my-custom-model')
    expect(baseUrlInput(wrapper).value).toBe('https://mock.openai.example/v1')
  })

  it('leaves the model empty for providers without a defaultModel', async () => {
    const { wrapper } = mountPage()
    await flushPromises()

    await pickProvider(wrapper, 'anthropic')
    expect(modelInput(wrapper).value).toBe('')
    expect(baseUrlInput(wrapper).value).toBe('https://mock.anthropic.example')
  })
})

describe('ProvidersPage — refresh button', () => {
  it('refetches the provider list for the selected bot', async () => {
    const { wrapper } = mountPage()
    await flushPromises()
    expect(providersApiMocks.fetchProviders).toHaveBeenCalledTimes(1)
    expect(providersApiMocks.fetchProviders).toHaveBeenCalledWith('main')

    await refreshButton(wrapper).trigger()
    await flushPromises()

    expect(providersApiMocks.fetchProviders).toHaveBeenCalledTimes(2)
    expect(providersApiMocks.fetchProviders).toHaveBeenLastCalledWith('main')
  })

  it('surfaces a failed refresh as an error toast', async () => {
    const { wrapper } = mountPage()
    await flushPromises()

    providersApiMocks.fetchProviders.mockRejectedValueOnce(new Error('boom'))
    await refreshButton(wrapper).trigger()
    await flushPromises()

    const toast = document.querySelector('.n-message')
    expect(toast?.textContent).toContain('加载提供商失败')
    expect(toast?.textContent).toContain('boom')
  })
})
