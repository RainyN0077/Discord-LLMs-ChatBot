/**
 * MainLayout responsive-sider tests (Wave 3-A CDP fix).
 *
 * naive-ui's NLayoutSider has no `breakpoint` prop (verified in
 * node_modules/naive-ui LayoutSider.mjs/d.ts — the layout module has no
 * breakpoint API and @collapse/@expand only fire from the internal trigger,
 * which this layout doesn't render). MainLayout therefore implements the
 * 768px breakpoint itself with a matchMedia listener.
 *
 * The setup.ts matchMedia mock is a passive stub (matches: false, no-op
 * listeners), so these tests install a controllable per-test mock via
 * vi.stubGlobal (restored by vi.unstubAllGlobals in setup.ts afterEach).
 *
 * Coverage:
 *  - narrow viewport at mount → sider starts collapsed (regression test:
 *    the old `:breakpoint="768"` prop was a no-op, so this fails pre-fix)
 *  - breakpoint crossing narrow→wide / wide→narrow updates collapse state
 *  - manual toggle is preserved until the next crossing (no forced reset)
 *  - unmount removes the change listener
 */

import { defineComponent, h, nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { i18n } from '@/locales'
import MainLayout from '@/layouts/MainLayout.vue'

type MqlListener = (e: { matches: boolean }) => void

/**
 * Controllable matchMedia mock: `setMatches()` fires every registered
 * `change` listener, simulating a viewport breakpoint crossing.
 */
function createMatchMediaMock(initialMatches: boolean) {
  const listeners = new Set<MqlListener>()
  let matches = initialMatches
  const mql = {
    get matches(): boolean {
      return matches
    },
    media: '(max-width: 768px)',
    onchange: null,
    addEventListener: (_type: string, listener: MqlListener): void => {
      listeners.add(listener)
    },
    removeEventListener: (_type: string, listener: MqlListener): void => {
      listeners.delete(listener)
    },
    addListener: (): void => {},
    removeListener: (): void => {},
    dispatchEvent: (): boolean => false,
  }
  return {
    mql,
    listenerCount: (): number => listeners.size,
    setMatches(next: boolean): void {
      matches = next
      listeners.forEach((listener) => listener({ matches: next }))
    },
  }
}

type MatchMediaMock = ReturnType<typeof createMatchMediaMock>

const MENU_PATHS = [
  '/providers',
  '/model-settings',
  '/config-panel',
  '/prompt-studio',
  '/debugger',
  '/user-options',
  '/appearance',
]

const StubPage = defineComponent({ render: () => h('div') })

async function mountLayout(
  controller: MatchMediaMock,
): Promise<{ wrapper: VueWrapper; router: Router }> {
  const pinia = createPinia()
  setActivePinia(pinia)
  vi.stubGlobal('matchMedia', vi.fn(() => controller.mql))

  const router = createRouter({
    history: createMemoryHistory(),
    routes: MENU_PATHS.map((path) => ({ path, component: StubPage })),
  })
  router.push('/providers')
  await router.isReady()

  const wrapper = mount(MainLayout, {
    global: { plugins: [pinia, router, i18n] },
  })
  return { wrapper, router }
}

function isCollapsed(wrapper: VueWrapper): boolean {
  return wrapper.find('.n-layout-sider--collapsed').exists()
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('MainLayout — responsive sider (matchMedia-driven, Wave 3-A)', () => {
  let controller: MatchMediaMock

  beforeEach(() => {
    controller = createMatchMediaMock(false)
  })

  it('narrow viewport at mount → sider starts collapsed (regression: old `breakpoint` prop was a no-op)', async () => {
    controller = createMatchMediaMock(true)
    const { wrapper } = await mountLayout(controller)

    expect(isCollapsed(wrapper)).toBe(true)
    // The expanded-only title text is hidden while collapsed.
    expect(wrapper.find('.sider-title-text').exists()).toBe(false)
  })

  it('crossing wide→narrow collapses, narrow→wide expands', async () => {
    const { wrapper } = await mountLayout(controller) // wide

    expect(isCollapsed(wrapper)).toBe(false)

    controller.setMatches(true) // crossing into narrow
    await nextTick()
    expect(isCollapsed(wrapper)).toBe(true)

    controller.setMatches(false) // crossing back to wide
    await nextTick()
    expect(isCollapsed(wrapper)).toBe(false)
  })

  it('manual toggle survives until the next breakpoint crossing', async () => {
    const { wrapper } = await mountLayout(controller) // wide

    // Manual collapse on a wide screen.
    await wrapper.find('.sider-collapse-btn').trigger('click')
    expect(isCollapsed(wrapper)).toBe(true)

    // Same-side change event (still wide) must NOT force an expand.
    controller.setMatches(false)
    await nextTick()
    expect(isCollapsed(wrapper)).toBe(true)

    // Crossing into narrow keeps it collapsed (auto-collapse agrees).
    controller.setMatches(true)
    await nextTick()
    expect(isCollapsed(wrapper)).toBe(true)

    // Manual expand while narrow.
    await wrapper.find('.sider-collapse-btn').trigger('click')
    expect(isCollapsed(wrapper)).toBe(false)

    // Same-side narrow event must NOT force a collapse.
    controller.setMatches(true)
    await nextTick()
    expect(isCollapsed(wrapper)).toBe(false)

    // Crossing back to wide auto-expands (already expanded — still consistent).
    controller.setMatches(false)
    await nextTick()
    expect(isCollapsed(wrapper)).toBe(false)
  })

  it('unmount removes the matchMedia change listener', async () => {
    const { wrapper } = await mountLayout(controller)
    expect(controller.listenerCount()).toBe(1)

    wrapper.unmount()
    expect(controller.listenerCount()).toBe(0)
  })
})
