/**
 * BotCard component tests (jsdom + @vue/test-utils + real naive-ui).
 *
 * Covers the rename/delete interaction edge cases of B4 Wave 2-Y:
 *  - NEW-3: IME composition guard on blur (no half-word commit)
 *  - NEW-4: reproduction attempt of the "ghost selection" race between the
 *    rename blur-commit and a click-select on another card
 *  - NEW-7: a failed delete keeps the confirm dialog open
 *  - NEW-8: delete-dialog ↔ rename-edit mutual exclusion
 *  - F11: Space selects the card like Enter (and never while editing)
 */

import { defineComponent, h, nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type DOMWrapper, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { NDialogProvider, NMessageProvider } from 'naive-ui'
import { i18n } from '@/locales'
import BotCard from '@/components/BotCard.vue'
import { useBotsStore } from '@/stores/bots'
import type { BotSummary } from '@/api/bots'

const apiMocks = vi.hoisted(() => ({
  fetchBots: vi.fn(),
  createBot: vi.fn(),
  deleteBot: vi.fn(),
  renameBot: vi.fn(),
  startBot: vi.fn(),
  stopBot: vi.fn(),
  restartBot: vi.fn(),
}))

vi.mock('@/api/bots', () => apiMocks)

function makeBot(bot_id: string): BotSummary {
  return {
    bot_id,
    bot_name: bot_id,
    platform: 'discord',
    enabled: true,
    status: 'stopped',
    uptime_seconds: null,
    bot_nickname: '',
    model_name: 'gpt-4o',
    llm_provider: 'openai',
    trigger_keywords: [],
  }
}

const alpha = makeBot('alpha')
const bravo = makeBot('bravo')

/** Mount the real MainLayout-style binding: BotCard list + store selection. */
function mountHarness(bots: BotSummary[], selected: string | null) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useBotsStore()
  store.bots = bots
  store.selectedBotId = selected

  const Harness = defineComponent({
    setup() {
      const s = useBotsStore()
      return () =>
        h(NDialogProvider, null, {
          default: () =>
            h(NMessageProvider, null, {
              default: () =>
                h(
                  'div',
                  { class: 'harness' },
                  s.bots.map((bot) =>
                    h(BotCard, {
                      key: bot.bot_id,
                      bot,
                      active: bot.bot_id === s.selectedBotId,
                      onSelect: (id: string) => s.selectBot(id),
                    }),
                  ),
                ),
            }),
        })
    },
  })

  const wrapper = mount(Harness, {
    global: { plugins: [i18n] },
    attachTo: document.body,
  })
  return { wrapper, store }
}

function cards(wrapper: VueWrapper): DOMWrapper<Element>[] {
  return wrapper.findAll('.bot-card')
}

/** Ids of the cards currently carrying the `.active` highlight. */
function activeIds(wrapper: VueWrapper): string[] {
  return cards(wrapper)
    .filter((c) => c.classes().includes('active'))
    .map((c) => c.find('.card-id').text())
}

async function enterRename(card: DOMWrapper<Element>): Promise<DOMWrapper<Element>> {
  await card.find('.card-id').trigger('dblclick')
  return card.find('input')
}

function deleteButton(card: DOMWrapper<Element>): DOMWrapper<Element> {
  const btns = card.findAll('.card-actions button')
  return btns[btns.length - 1] // delete is the last action button
}

/** Dispatch a real click on a raw DOM element (teleported dialog buttons). */
function clickEl(el: Element | null): void {
  if (!el) throw new Error('expected dialog button element')
  el.dispatchEvent(new MouseEvent('click', { bubbles: true }))
}

/** The dialog's positive (warning-type) button element. */
function dialogPositiveButton(): Element | null {
  return (
    Array.from(document.querySelectorAll('.n-dialog__action button')).find(
      (b) => b.className.includes('warning-type'),
    ) ?? null
  )
}

/**
 * naive-ui keeps the closed dialog in the DOM with `display: none`, so
 * visibility (not presence) is the "open" signal.
 */
function dialogDisplay(): string {
  const el = document.querySelector('.n-dialog')
  return el ? getComputedStyle(el).display : 'gone'
}

async function openDeleteDialog(card: DOMWrapper<Element>): Promise<void> {
  await deleteButton(card).trigger('click')
  await nextTick()
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('BotCard — rename blur vs IME composition (NEW-3)', () => {
  beforeEach(() => {
    apiMocks.renameBot.mockReset()
    apiMocks.renameBot.mockResolvedValue({ message: 'ok', bot_id: 'alice' })
  })

  it('blur during composition does NOT commit half-typed text', async () => {
    const { wrapper } = mountHarness([alpha, bravo], 'alpha')
    const card = cards(wrapper)[0]
    const input = await enterRename(card)

    await input.setValue('alice')
    await input.trigger('compositionstart')
    await input.trigger('blur')

    // Nothing committed, the edit state stays open.
    expect(apiMocks.renameBot).not.toHaveBeenCalled()
    expect(card.find('input').exists()).toBe(true)

    // Once the composition ends the full text is committed.
    await input.trigger('compositionend')
    await flushPromises()
    expect(apiMocks.renameBot).toHaveBeenCalledTimes(1)
    expect(apiMocks.renameBot).toHaveBeenCalledWith('alpha', 'alice')
  })

  it('blur commits immediately when not composing', async () => {
    const { wrapper } = mountHarness([alpha, bravo], 'alpha')
    const card = cards(wrapper)[0]
    const input = await enterRename(card)

    await input.setValue('alice')
    await input.trigger('blur')
    await flushPromises()

    expect(apiMocks.renameBot).toHaveBeenCalledTimes(1)
    expect(apiMocks.renameBot).toHaveBeenCalledWith('alpha', 'alice')
  })
})

describe('BotCard — ghost selection race (NEW-4 reproduction attempt)', () => {
  beforeEach(() => {
    apiMocks.renameBot.mockReset()
    apiMocks.deleteBot.mockReset()
    apiMocks.fetchBots.mockReset()
  })

  it('click on another card while the rename is in flight selects that card', async () => {
    const { wrapper, store } = mountHarness([alpha, bravo], 'alpha')
    let release!: (v: { message: string; bot_id: string }) => void
    apiMocks.renameBot.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          release = resolve
        }),
    )

    const cardA = cards(wrapper)[0]
    const cardB = cards(wrapper)[1]
    const input = await enterRename(cardA)
    await input.setValue('alice')

    // User clicks card B: blur fires (commit starts) → click selects B.
    await input.trigger('blur')
    expect(store.selectedBotId).toBe('alpha') // commit still pending
    await cardB.trigger('click')
    expect(store.selectedBotId).toBe('bravo')

    // Rename resolves AFTER the click — the selection must not be clobbered.
    release({ message: 'ok', bot_id: 'alice' })
    await flushPromises()

    expect(store.selectedBotId).toBe('bravo')
    expect(store.selectedBot?.bot_id).toBe('bravo')
    expect(activeIds(wrapper)).toEqual(['bravo'])
  })

  it('rename resolving before the click cannot create a ghost highlight', async () => {
    const { wrapper, store } = mountHarness([alpha, bravo], 'alpha')
    apiMocks.renameBot.mockResolvedValue({ message: 'ok', bot_id: 'alice' })

    const cardA = cards(wrapper)[0]
    const input = await enterRename(cardA)
    await input.setValue('alice')

    // Blur commits and the rename resolves before mouseup/click lands.
    await input.trigger('blur')
    await flushPromises()
    expect(store.selectedBotId).toBe('alice') // selection synced to the new id

    // The click on card B completes the selection — final state consistent.
    const cardB = cards(wrapper)[1]
    await cardB.trigger('click')
    await flushPromises()

    expect(store.selectedBotId).toBe('bravo')
    expect(store.selectedBot?.bot_id).toBe('bravo')
    expect(activeIds(wrapper)).toEqual(['bravo'])
  })

  it('clicking the renamed card itself keeps one consistent highlight', async () => {
    const { wrapper, store } = mountHarness([alpha, bravo], 'alpha')
    apiMocks.renameBot.mockResolvedValue({ message: 'ok', bot_id: 'alice' })

    const cardA = cards(wrapper)[0]
    const input = await enterRename(cardA)
    await input.setValue('alice')

    await input.trigger('blur')
    await flushPromises()

    // The card was remounted under its new id — clicking it selects 'alice'.
    const renamed = cards(wrapper)[0]
    await renamed.trigger('click')
    await flushPromises()

    expect(store.selectedBotId).toBe('alice')
    expect(activeIds(wrapper)).toEqual(['alice'])
  })
})

describe('BotCard — keyboard activation (F11)', () => {
  beforeEach(() => {
    apiMocks.renameBot.mockReset()
  })

  it('Space selects the card like Enter', async () => {
    const { wrapper, store } = mountHarness([alpha, bravo], 'alpha')
    const cardB = cards(wrapper)[1]

    await cardB.trigger('keydown', { key: ' ' })
    expect(store.selectedBotId).toBe('bravo')

    await cardB.trigger('keydown', { key: 'Enter' })
    expect(store.selectedBotId).toBe('bravo')
  })

  it('Space typed in the rename input neither selects nor gets blocked', async () => {
    const { wrapper, store } = mountHarness([alpha, bravo], 'alpha')
    const cardA = cards(wrapper)[0]
    const input = await enterRename(cardA)

    await input.setValue('ali')
    await input.trigger('keydown', { key: ' ' })
    await input.setValue('ali ce') // typing still works

    expect(store.selectedBotId).toBe('alpha')
    expect(apiMocks.renameBot).not.toHaveBeenCalled()
  })

  it('Enter in the rename input commits but does not re-select the card', async () => {
    const { wrapper, store } = mountHarness([alpha, bravo], 'alpha')
    apiMocks.renameBot.mockResolvedValue({ message: 'ok', bot_id: 'alice' })
    const cardA = cards(wrapper)[0]
    const input = await enterRename(cardA)

    await input.setValue('alice')
    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()

    // Enter only commits — the keydown select is suppressed while editing;
    // the store still re-points the selection to the renamed id (correct).
    expect(apiMocks.renameBot).toHaveBeenCalledTimes(1)
    expect(store.selectedBotId).toBe('alice')
    expect(activeIds(wrapper)).toEqual(['alice'])
  })

  it('Space/Enter on an inner action button does NOT select the card (M1)', async () => {
    const { wrapper, store } = mountHarness([alpha, bravo], 'alpha')
    const cardB = cards(wrapper)[1]
    const startBtn = cardB.find('.card-actions button') // first action button

    // The keydown bubbles from the button up to the card handler — the
    // card must not preventDefault / select, or the button activation
    // (and its click) would be cancelled.
    await startBtn.trigger('keydown', { key: ' ' })
    expect(store.selectedBotId).toBe('alpha')

    await startBtn.trigger('keydown', { key: 'Enter' })
    expect(store.selectedBotId).toBe('alpha')
  })

  it('Space/Enter on the rename ✓/× buttons does NOT select the card (M1)', async () => {
    const { wrapper, store } = mountHarness([alpha, bravo], 'alpha')
    const cardA = cards(wrapper)[0]
    await enterRename(cardA)

    const confirmBtn = cardA.find('.rename-btn-confirm')
    await confirmBtn.trigger('keydown', { key: ' ' })
    expect(store.selectedBotId).toBe('alpha')

    const cancelBtn = cardA.find('.rename-btn-cancel')
    await cancelBtn.trigger('keydown', { key: 'Enter' })
    expect(store.selectedBotId).toBe('alpha')
  })
})

describe('BotCard — delete dialog (NEW-7 / NEW-8)', () => {
  beforeEach(() => {
    apiMocks.deleteBot.mockReset()
    apiMocks.renameBot.mockReset()
  })

  it('a failed delete keeps the dialog open and shows the error', async () => {
    apiMocks.deleteBot.mockRejectedValueOnce(new Error('boom'))
    const { wrapper } = mountHarness([alpha, bravo], 'alpha')
    const cardA = cards(wrapper)[0]

    await openDeleteDialog(cardA)
    expect(dialogDisplay()).toBe('block')

    clickEl(dialogPositiveButton())
    await flushPromises()
    await nextTick()

    // Dialog stays open, error surfaced via the message API.
    expect(dialogDisplay()).toBe('block')
    expect(document.querySelector('.n-message')?.textContent).toContain('boom')

    // The guard stays set — clicking delete again must not stack a dialog.
    await deleteButton(cardA).trigger('click')
    await nextTick()
    expect(document.querySelectorAll('.n-dialog')).toHaveLength(1)
  })

  it('a successful delete closes the dialog', async () => {
    apiMocks.deleteBot.mockResolvedValue({ message: 'ok' })
    const { wrapper } = mountHarness([alpha, bravo], 'alpha')
    const cardA = cards(wrapper)[0]

    await openDeleteDialog(cardA)
    expect(dialogDisplay()).toBe('block')

    clickEl(dialogPositiveButton())
    await flushPromises()
    await nextTick()

    expect(dialogDisplay()).toBe('none')
    expect(apiMocks.deleteBot).toHaveBeenCalledWith('alpha')
  })

  it('the delete dialog blocks entering rename while open (NEW-8)', async () => {
    const { wrapper } = mountHarness([alpha, bravo], 'alpha')
    const cardA = cards(wrapper)[0]

    await openDeleteDialog(cardA)
    expect(dialogDisplay()).toBe('block')
    await cardA.find('.card-id').trigger('dblclick')
    expect(cardA.find('input').exists()).toBe(false)
  })

  it('the rename edit state blocks opening the delete dialog (NEW-8)', async () => {
    const { wrapper } = mountHarness([alpha, bravo], 'alpha')
    const cardA = cards(wrapper)[0]
    await enterRename(cardA)

    await deleteButton(cardA).trigger('click')
    await nextTick()
    expect(document.querySelector('.n-dialog')).toBeNull()
  })
})
