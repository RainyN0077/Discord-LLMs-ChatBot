/**
 * Overlay animation pause — while a naive-ui modal/dialog overlay is mounted
 * (`.n-modal-container` teleported under <body>), every page-level *infinite*
 * animation (style effects: grid, scanline, glitch, aurora drift, status-dot
 * blink, …) is paused via the Web Animations API.
 *
 * Why: opening an overlay flips the html scroll lock (scrollbar disappears →
 * viewport width change → full-screen effect layers re-rasterize) while the
 * overlay's own enter/leave transitions run. On effect-heavy styles
 * (cyberpunk etc.) this compounding per-frame work froze the whole page for
 * 1-3 s right after the overlay closed. `animation.pause()` keeps the
 * composited layers alive, so resuming is cheap and glitch-free.
 *
 * Only `iterations: Infinity` animations are touched, and anything inside the
 * overlay (or one of the short-lived floaters: message/tooltip/popover/
 * notification) is left running.
 */

/** Containers whose own animations must keep running while an overlay is up. */
const OVERLAY_SELECTOR =
  '.n-modal-container, .n-message-container, .n-notification-container, .n-tooltip, .n-popover'

let pausedAnims: Animation[] = []

function isInFloater(target: EventTarget | null): boolean {
  return target instanceof Element && target.closest(OVERLAY_SELECTOR) !== null
}

function isInfiniteLoop(anim: Animation): boolean {
  const effect = anim.effect
  if (!effect) return false
  // CSS animations report a Timing; use the iterations from the effect's
  // timing object. `Infinity` is the Web Animations representation of
  // `animation-iteration-count: infinite`.
  const timing = effect.getTiming()
  return timing.iterations === Infinity
}

function pausePageAnims(): void {
  if (pausedAnims.length > 0) return
  for (const anim of document.getAnimations()) {
    if (anim.playState !== 'running') continue
    if (!isInfiniteLoop(anim)) continue
    const target = anim.effect?.target ?? null
    if (isInFloater(target)) continue
    anim.pause()
    pausedAnims.push(anim)
  }
}

function resumePageAnims(): void {
  for (const anim of pausedAnims) {
    try {
      anim.play()
    } catch {
      // The animation may have been garbage-collected with its element
      // (e.g. an unmounted page); nothing to resume.
    }
  }
  pausedAnims = []
}

function overlayPresent(): boolean {
  return document.querySelector(OVERLAY_SELECTOR) !== null
}

/**
 * Watch <body> for teleported overlays and pause/resume page effects around
 * them. Returns a dispose function (used by tests; App.vue keeps it for the
 * app's lifetime).
 */
export function setupOverlayAnimPause(): () => void {
  let overlayUp = overlayPresent()
  if (overlayUp) pausePageAnims()

  const observer = new MutationObserver(() => {
    const nowUp = overlayPresent()
    if (nowUp === overlayUp) return
    overlayUp = nowUp
    if (nowUp) pausePageAnims()
    else resumePageAnims()
  })
  observer.observe(document.body, { childList: true, subtree: false })

  return () => {
    observer.disconnect()
    resumePageAnims()
  }
}

/** Test helper — current count of paused page animations. */
export function pausedAnimCount(): number {
  return pausedAnims.length
}
