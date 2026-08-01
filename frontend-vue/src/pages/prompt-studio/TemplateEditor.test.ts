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
 * Mount cost is low (no stores/router needed), so the full editor is
 * exercised instead of a reduced logical subset.
 */

import { describe, expect, it } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { i18n } from '@/locales'
import TemplateEditor from '@/pages/prompt-studio/TemplateEditor.vue'
import type { PromptTemplate } from '@/api/prompts'

function makeTemplates(): PromptTemplate {
  return {
    message_format: '「{author_name}」说：\n{content}',
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

function mountEditor(templates: PromptTemplate = makeTemplates()): VueWrapper {
  return mount(TemplateEditor, {
    props: { templates },
    global: { plugins: [i18n] },
  })
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
    expect(textarea(wrapper).value()).toBe('「{author_name}」说：\n{content}')
    expect(placeholderTags(wrapper)).toEqual(['{author_id}', '{content}', '{image_note}'])
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
