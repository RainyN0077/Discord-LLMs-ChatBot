/**
 * MainLayout sub-page switch transition (Wave page-animation).
 *
 * The content-area router-view is wrapped in
 * `<transition name="page" mode="out-in">` so switching between child routes
 * plays the global .page-* classes instead of a hard swap.
 *
 * This test lives in its own file (no @vue/test-utils import) because:
 *  - VTU replaces template `<transition>` with a stub by default, and its
 *    `transformVNodeArgs` transformer is a *global* Vue hook installed by any
 *    VTU `mount()` call — it persists into later tests in the same file (even
 *    ones that use plain createApp). Vitest isolates per file, so a dedicated
 *    file keeps the real transition intact.
 *  - jsdom computes no CSS transition duration (empty computed styles), which
 *    makes Vue's Transition resolve after two requestAnimationFrame ticks —
 *    the transient classes vanish within milliseconds. A real 500ms CSS
 *    duration is faked via getComputedStyle so the leave/enter phases are
 *    observably present (verified with a MutationObserver while debugging).
 *    The transition-* props are overridden in place on the fresh declaration
 *    jsdom returns per call — a plain Object.create wrapper would throw,
 *    because CSSStyleDeclaration accessors brand-check their receiver
 *    ("called on an object that is not a valid instance of
 *    CSSStyleProperties" broke getTransitionInfo and hung the transition).
 */

import { createApp, defineComponent, h, nextTick } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { i18n } from '@/locales'
import MainLayout from '@/layouts/MainLayout.vue'

const PageA = defineComponent({
  render: () => h('div', { class: 'stub-page-a' }, 'Page A'),
})
const PageB = defineComponent({
  render: () => h('div', { class: 'stub-page-b' }, 'Page B'),
})

/** Poll until `fn` is true (or the window expires) on a short timer. */
async function pollUntil(fn: () => boolean, windowMs = 800): Promise<boolean> {
  const deadline = Date.now() + windowMs
  while (Date.now() < deadline) {
    if (fn()) return true
    await new Promise((resolve) => setTimeout(resolve, 5))
  }
  return fn()
}

async function mountLayoutWithRouter(): Promise<{
  app: ReturnType<typeof createApp>
  router: Router
  container: HTMLDivElement
}> {
  const pinia = createPinia()
  setActivePinia(pinia)
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({
      matches: false,
      media: '(max-width: 768px)',
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    })),
  )

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/a', component: PageA },
      { path: '/b', component: PageB },
    ],
  })
  router.push('/a')
  await router.isReady()

  const container = document.createElement('div')
  document.body.appendChild(container)
  const app = createApp(MainLayout)
  app.use(pinia)
  app.use(router)
  app.use(i18n)
  app.mount(container)
  return { app, router, container }
}

describe('MainLayout — sub-page switch transition (out-in)', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('applies page-leave-active/page-enter-active on sub-page switch and swaps content', async () => {
    // Fake a CSS transition duration so Vue's Transition keeps the classes
    // applied long enough to observe.
    const realGetComputedStyle = window.getComputedStyle.bind(window)
    const patchStyle = (el: Element): CSSStyleDeclaration => {
      const real = realGetComputedStyle(el)
      Object.defineProperties(real, {
        transitionDuration: { value: '0.5s', configurable: true },
        transitionDelay: { value: '0s', configurable: true },
        transitionProperty: { value: 'opacity, transform', configurable: true },
      })
      return real
    }
    window.getComputedStyle = patchStyle as typeof window.getComputedStyle

    let app: ReturnType<typeof createApp> | null = null
    try {
      const mounted = await mountLayoutWithRouter()
      app = mounted.app
      const { router, container } = mounted
      const q = (sel: string): HTMLElement | null => container.querySelector(sel)

      // Initial page rendered.
      expect(q('.stub-page-a')).not.toBeNull()

      await router.push('/b')
      await nextTick()

      // Out-in leave: the outgoing page is kept on screen with the leave
      // classes while the fake 500ms duration runs.
      const sawLeave = await pollUntil(
        () => q('.stub-page-a')?.classList.contains('page-leave-active') ?? false,
        800,
      )
      expect(sawLeave).toBe(true)

      // Out-in enter: after the leave finishes (~500ms), the incoming page
      // mounts with the enter classes.
      const sawEnter = await pollUntil(
        () => q('.stub-page-b')?.classList.contains('page-enter-active') ?? false,
        1500,
      )
      expect(sawEnter).toBe(true)

      // Settled: old page unmounted, new page rendered, classes removed.
      const settled = await pollUntil(
        () =>
          !q('.stub-page-a') &&
          !!q('.stub-page-b') &&
          !(q('.stub-page-b')?.classList.contains('page-enter-active') ?? true),
        1500,
      )
      expect(settled).toBe(true)
      expect(q('.stub-page-b')?.textContent).toContain('Page B')

      // Regression: the fixed chrome (sider/top menu) is untouched by the
      // transition — the layout root still renders after the swap.
      expect(container.querySelector('.main-layout')).not.toBeNull()
    } finally {
      app?.unmount()
      document.body.innerHTML = ''
      window.getComputedStyle = realGetComputedStyle
    }
  })
})
