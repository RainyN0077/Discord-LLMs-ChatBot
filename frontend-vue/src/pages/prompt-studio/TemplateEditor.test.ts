/**
 * TemplateEditor component tests (jsdom + @vue/test-utils + real naive-ui).
 *
 * B4 Wave 3-B coverage for the 14-key three-column editor:
 *  - placeholder token tags render for the selected key (default:
 *    message_format → {author_id}/{content}/{image_note})
 *  - left-nav navigation switches the active key, the textarea value and the
 *    placeholder hints
 *  - editing emits a full update:templates payload
 *  - the operational_instructions column lists/adds/removes instructions
 *
 * S4 (design §5 / §7.1): placeholder click insertion + keyboard a11y:
 *  - click / Enter / Space insert the token at the caret (selected text is
 *    replaced), emit the full new value, restore the caret and show the
 *    phInserted toast
 *  - graceful degradation when the inner textarea is unavailable
 *
 * Mount cost is low (no stores/router needed), so the full editor is
 * exercised instead of a reduced logical subset. The editor is mounted under
 * NMessageProvider (ProvidersPage.test.ts same pattern) with a reactive
 * v-model harness so emits flow back into props like a real parent.
 */

import { describe, expect, it } from 'vitest'
import { h, reactive } from 'vue'
import { mount, type VueWrapper } from '@vue/test-utils'
import { NInput, NMessageProvider } from 'naive-ui'
import { i18n } from '@/locales'
import TemplateEditor from '@/pages/prompt-studio/TemplateEditor.vue'
import type { PromptTemplate } from '@/api/prompts'

function makeTemplates(): PromptTemplate {
  return {
    message_format: '「{author_id_str}」说：\n{content}',
    image_note: '[图片 x{count}]',
    reply_context: '',
    deleted_reply_context: '',
    user_request_block: '<user_request>\n{parts}\n</user_request>',
    tool_context: '',
    memory_context: '',
    worldbook_context: '',
    system_prompt_foundation_header: '你是一个乐于助人的 AI 助手。',
    system_prompt_persona_header: '',
    system_prompt_situation_header: '',
    system_prompt_participants_header: '',
    system_prompt_security_header: '',
    operational_instructions: ['规则一：先回复再行动', '规则二：保持简洁'],
  }
}

/**
 * Mount the editor under NMessageProvider (useMessage) with a reactive
 * v-model harness: `update:templates` emits flow back into props, so the
 * NInput stays controlled like in a real parent (cursor math stays valid).
 * `attachTo: document.body` keeps the tree connected — jsdom ignores
 * focus() on detached elements, which would break caret/focus assertions.
 * Returns the TemplateEditor wrapper — emitted() reports its own events.
 */
function mountEditor(templates: PromptTemplate = makeTemplates()): VueWrapper {
  const state = reactive({ templates })
  const provider = mount(NMessageProvider, {
    attachTo: document.body,
    global: { plugins: [i18n] },
    slots: {
      default: () =>
        h(TemplateEditor, {
          templates: state.templates,
          'onUpdate:templates': (v: PromptTemplate) => {
            state.templates = v
          },
        }),
    },
  })
  return provider.findComponent(TemplateEditor)
}

function navItems(wrapper: VueWrapper): { label: string; click: () => Promise<void>; isActive: boolean }[] {
  return wrapper.findAll('.template-editor-nav-item').map((item) => ({
    label: item.text(),
    click: () => item.trigger('click'),
    isActive: item.classes().includes('active'),
  }))
}

async function clickNav(wrapper: VueWrapper, label: string): Promise<void> {
  const item = navItems(wrapper).find((n) => n.label === label)
  if (!item) throw new Error(`nav item "${label}" not found`)
  await item.click()
}

function placeholderTags(wrapper: VueWrapper): string[] {
  return wrapper.findAll('.placeholder-tag').map((tag) => tag.text())
}

function textarea(wrapper: VueWrapper): { value: () => string; set: (v: string) => Promise<void> } {
  const el = wrapper.find('textarea')
  return {
    value: () => (el.element as HTMLTextAreaElement).value,
    set: (v: string) => el.setValue(v),
  }
}

describe('TemplateEditor — placeholder token rendering', () => {
  it('renders the message_format tokens by default with the current value', () => {
    const wrapper = mountEditor()
    expect(textarea(wrapper).value()).toBe('「{author_id_str}」说：\n{content}')
    expect(placeholderTags(wrapper)).toEqual(['{author_id_str}', '{content}', '{image_note}'])
  })

  it('switching keys swaps the placeholder token list and the textarea value', async () => {
    const wrapper = mountEditor()

    await clickNav(wrapper, '用户请求块')
    expect(textarea(wrapper).value()).toBe('<user_request>\n{parts}\n</user_request>')
    expect(placeholderTags(wrapper)).toEqual(['{parts}'])

    // image_note carries {count} plus its own template text.
    await clickNav(wrapper, '图片注释')
    expect(textarea(wrapper).value()).toBe('[图片 x{count}]')
    expect(placeholderTags(wrapper)).toEqual(['{count}'])
  })

  it('keys without placeholder definitions hide the hint area', async () => {
    const wrapper = mountEditor()
    // system_prompt_persona_header has no TEMPLATE_PLACEHOLDERS entry.
    await clickNav(wrapper, '当前人设标题')
    expect(textarea(wrapper).value()).toBe('')
    expect(wrapper.find('.template-editor-placeholders').exists()).toBe(false)
  })
})

describe('TemplateEditor — security semantic warnings (F-4)', () => {
  it('warns on user_request_block about the {parts} placeholder', async () => {
    const wrapper = mountEditor()
    await clickNav(wrapper, '用户请求块')
    const warning = wrapper.find('.template-editor-security-warning')
    expect(warning.exists()).toBe(true)
    expect(warning.text()).toContain('{parts}')
    expect(warning.text()).toContain('防御')
  })

  it('warns on memory_context about the {data} placeholder', async () => {
    const wrapper = mountEditor()
    await clickNav(wrapper, '长期记忆')
    const warning = wrapper.find('.template-editor-security-warning')
    expect(warning.exists()).toBe(true)
    expect(warning.text()).toContain('{data}')
    expect(warning.text()).toContain('<knowledge>')
  })

  it('shows no warning on other keys', async () => {
    const wrapper = mountEditor()
    // Default key (message_format) has no warning.
    expect(wrapper.find('.template-editor-security-warning').exists()).toBe(false)
    await clickNav(wrapper, '工具输出')
    expect(wrapper.find('.template-editor-security-warning').exists()).toBe(false)
  })
})

describe('TemplateEditor — navigation & editing', () => {
  it('moves the active highlight along the navigation', async () => {
    const wrapper = mountEditor()
    expect(navItems(wrapper).find((n) => n.isActive)?.label).toBe('用户消息格式')

    await clickNav(wrapper, '基础规则标题')
    expect(navItems(wrapper).find((n) => n.isActive)?.label).toBe('基础规则标题')
    expect(textarea(wrapper).value()).toBe('你是一个乐于助人的 AI 助手。')
  })

  it('emits a full update:templates payload on edit', async () => {
    const wrapper = mountEditor()
    await textarea(wrapper).set('新格式：{content}')

    const emitted = wrapper.emitted('update:templates')
    expect(emitted).toBeTruthy()
    const payload = emitted![0][0] as PromptTemplate
    expect(payload.message_format).toBe('新格式：{content}')
    // The other keys are preserved by the spread update.
    expect(payload.system_prompt_foundation_header).toBe('你是一个乐于助人的 AI 助手。')
  })
})

describe('TemplateEditor — operational instructions column', () => {
  it('lists existing instructions and adds a blank one', async () => {
    const wrapper = mountEditor()
    expect(wrapper.findAll('.instruction-item')).toHaveLength(2)

    await clickNav(wrapper, '核心操作指令列表')
    // The middle textarea is replaced by the instructions view.
    expect(wrapper.find('textarea').exists()).toBe(false)
    expect(wrapper.findAll('.instruction-item')).toHaveLength(2)

    const addBtn = wrapper
      .findAll('button')
      .find((b) => b.text().includes('添加新指令'))
    if (!addBtn) throw new Error('add-instruction button not found')
    await addBtn.trigger('click')

    const payload = wrapper.emitted('update:templates')![0][0] as PromptTemplate
    expect(payload.operational_instructions).toEqual([
      '规则一：先回复再行动',
      '规则二：保持简洁',
      '',
    ])
  })

  it('removes an instruction by index', async () => {
    const wrapper = mountEditor()
    await clickNav(wrapper, '核心操作指令列表')

    const removeBtns = wrapper.findAll('.instruction-item button')
    await removeBtns[0].trigger('click')

    const payload = wrapper.emitted('update:templates')![0][0] as PromptTemplate
    expect(payload.operational_instructions).toEqual(['规则二：保持简洁'])
  })
})

describe('TemplateEditor — placeholder click insertion (S4)', () => {
  // Default key (message_format) shows {author_id_str} first.
  const PH = '{author_id_str}'

  /** Focus the textarea and return its raw element (caret math is direct). */
  function focusedTextarea(wrapper: VueWrapper): HTMLTextAreaElement {
    const el = wrapper.find('textarea').element as HTMLTextAreaElement
    el.focus()
    return el
  }

  /** Latest full update:templates payload emitted by the editor. */
  function lastEmittedTemplates(wrapper: VueWrapper): PromptTemplate {
    const emitted = wrapper.emitted('update:templates')
    expect(emitted).toBeTruthy()
    const last = emitted![emitted!.length - 1]
    return last[0] as PromptTemplate
  }

  /** Wait for the rAF callback that restores the caret after the value flush. */
  function flushRaf(): Promise<void> {
    return new Promise((resolve) => requestAnimationFrame(() => resolve()))
  }

  it('clicks a placeholder, inserting it at the caret and emitting the full new value', async () => {
    const wrapper = mountEditor()
    const el = focusedTextarea(wrapper)
    el.value = 'AB'
    el.setSelectionRange(1, 1)

    await wrapper.find('.placeholder-tag').trigger('click')

    const payload = lastEmittedTemplates(wrapper)
    expect(payload.message_format).toBe(`A${PH}B`)
    // Spread emit preserves every other key.
    expect(payload.system_prompt_foundation_header).toBe('你是一个乐于助人的 AI 助手。')
    expect(payload.operational_instructions).toEqual(['规则一：先回复再行动', '规则二：保持简洁'])
  })

  it('replaces the selected text with the placeholder', async () => {
    const wrapper = mountEditor()
    const el = focusedTextarea(wrapper)
    el.value = 'ABCD'
    el.setSelectionRange(1, 3) // "BC" selected

    await wrapper.find('.placeholder-tag').trigger('click')

    expect(lastEmittedTemplates(wrapper).message_format).toBe(`A${PH}D`)
  })

  it('restores the caret right after the inserted placeholder and refocuses the textarea', async () => {
    const wrapper = mountEditor()
    const el = focusedTextarea(wrapper)
    el.value = 'AB'
    el.setSelectionRange(1, 1)

    await wrapper.find('.placeholder-tag').trigger('click')
    await flushRaf()

    expect(el.selectionStart).toBe(1 + PH.length)
    expect(el.selectionEnd).toBe(1 + PH.length)
    expect(document.activeElement).toBe(el)
  })

  it('triggers insertion from the keyboard via Enter and Space (a11y)', async () => {
    const wrapper = mountEditor()
    const el = focusedTextarea(wrapper)
    el.value = 'AB'
    el.setSelectionRange(0, 0)
    const tag = wrapper.find('.placeholder-tag')
    expect(tag.attributes('tabindex')).toBe('0')
    expect(tag.attributes('role')).toBe('button')

    await tag.trigger('keydown.enter')
    expect(lastEmittedTemplates(wrapper).message_format).toBe(`${PH}AB`)

    el.setSelectionRange(0, 0)
    await tag.trigger('keydown.space')
    expect(lastEmittedTemplates(wrapper).message_format).toBe(`${PH}${PH}AB`)
  })

  it('degrades silently (no crash, no emit) when the inner textarea is unavailable', async () => {
    const wrapper = mountEditor()
    const nInput = wrapper.findComponent(NInput)
    const el = wrapper.find('textarea').element as HTMLTextAreaElement
    // Break both lookup paths: DOM removal + exposed ref nulled.
    el.remove()
    const vm = nInput.vm as unknown as { textareaElRef?: unknown }
    vm.textareaElRef = null

    await wrapper.find('.placeholder-tag').trigger('click')

    expect(wrapper.emitted('update:templates')).toBeUndefined()
  })

  it('shows the phInserted toast on successful insertion', async () => {
    const wrapper = mountEditor()
    const el = focusedTextarea(wrapper)
    el.value = 'AB'
    el.setSelectionRange(1, 1)

    await wrapper.find('.placeholder-tag').trigger('click')
    await flushRaf()

    expect(document.body.textContent).toContain('已插入占位符')
    expect(document.body.textContent).toContain(PH)
  })
})
