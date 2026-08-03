/**
 * Unit tests for overlay animation pause (src/utils/overlayAnimPause.ts).
 *
 * Focus: infinite page animations pause while a naive overlay is mounted and
 * resume afterwards; overlay-internal and one-shot animations stay running.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { pausedAnimCount, setupOverlayAnimPause } from './overlayAnimPause'

interface MockAnim {
  playState: string
  paused: boolean
  effect: { target: Element | null; getTiming: () => { iterations: number } }
  pause: ReturnType<typeof vi.fn>
  play: ReturnType<typeof vi.fn>
}

function makeAnim(target: Element | null, iterations: number, running = true): MockAnim {
  return {
    playState: running ? 'running' : 'finished',
    paused: false,
    effect: { target, getTiming: () => ({ iterations }) },
    pause: vi.fn(function (this: MockAnim) {
      this.paused = true
      this.playState = 'paused'
    }),
    play: vi.fn(function (this: MockAnim) {
      this.paused = false
      this.playState = 'running'
    }),
  }
}

let anims: MockAnim[] = []
let observerCb: MutationCallback | null = null

function overlayEl(): HTMLElement {
  const el = document.createElement('div')
  el.className = 'n-modal-container'
  return el
}

describe('setupOverlayAnimPause', () => {
  beforeEach(() => {
    anims = []
    observerCb = null
    document.body.innerHTML = ''
    class MockObserver {
      observe = vi.fn()
      disconnect = vi.fn()
      constructor(cb: MutationCallback) {
        observerCb = cb
      }
    }
    vi.stubGlobal('MutationObserver', MockObserver)
    // jsdom's document lacks getAnimations; install a fake.
    Object.defineProperty(document, 'getAnimations', {
      configurable: true,
      value: () => anims as unknown as Animation[],
    })
  })

  afterEach(() => {
    delete (document as unknown as Record<string, unknown>).getAnimations
    vi.unstubAllGlobals()
  })

  it('pauses infinite page animations while an overlay is mounted', () => {
    const pageFx = makeAnim(null, Infinity)
    const oneShot = makeAnim(null, 1)
    anims = [pageFx, oneShot]

    const dispose = setupOverlayAnimPause()
    expect(pausedAnimCount()).toBe(0)

    document.body.appendChild(overlayEl())
    observerCb?.([] as unknown as MutationRecord[], null as unknown as MutationObserver)
    expect(pageFx.pause).toHaveBeenCalledTimes(1)
    expect(oneShot.pause).not.toHaveBeenCalled()
    expect(pausedAnimCount()).toBe(1)

    dispose()
  })

  it('leaves animations inside the overlay running', () => {
    const overlay = overlayEl()
    const inside = makeAnim(overlay, Infinity)
    const outside = makeAnim(null, Infinity)
    anims = [inside, outside]

    const dispose = setupOverlayAnimPause()
    document.body.appendChild(overlay)
    observerCb?.([] as unknown as MutationRecord[], null as unknown as MutationObserver)
    expect(outside.pause).toHaveBeenCalledTimes(1)
    expect(inside.pause).not.toHaveBeenCalled()

    dispose()
  })

  it('resumes paused animations when the overlay is removed', () => {
    const pageFx = makeAnim(null, Infinity)
    anims = [pageFx]

    const dispose = setupOverlayAnimPause()
    const overlay = overlayEl()
    document.body.appendChild(overlay)
    observerCb?.([] as unknown as MutationRecord[], null as unknown as MutationObserver)

    overlay.remove()
    observerCb?.([] as unknown as MutationRecord[], null as unknown as MutationObserver)
    expect(pageFx.play).toHaveBeenCalledTimes(1)
    expect(pausedAnimCount()).toBe(0)

    dispose()
  })

  it('ignores repeated mutations while state is unchanged', () => {
    const pageFx = makeAnim(null, Infinity)
    anims = [pageFx]

    const dispose = setupOverlayAnimPause()
    document.body.appendChild(overlayEl())
    observerCb?.([] as unknown as MutationRecord[], null as unknown as MutationObserver)
    // Extra mutations while the overlay stays mounted â†?no re-pause.
    observerCb?.([] as unknown as MutationRecord[], null as unknown as MutationObserver)
    observerCb?.([] as unknown as MutationRecord[], null as unknown as MutationObserver)
    expect(pageFx.pause).toHaveBeenCalledTimes(1)

    dispose()
  })

  it('dispose resumes anything still paused', () => {
    const pageFx = makeAnim(null, Infinity)
    anims = [pageFx]

    const dispose = setupOverlayAnimPause()
    document.body.appendChild(overlayEl())
    observerCb?.([] as unknown as MutationRecord[], null as unknown as MutationObserver)
    expect(pausedAnimCount()).toBe(1)

    dispose()
    expect(pageFx.play).toHaveBeenCalledTimes(1)
    expect(pausedAnimCount()).toBe(0)
  })
})
