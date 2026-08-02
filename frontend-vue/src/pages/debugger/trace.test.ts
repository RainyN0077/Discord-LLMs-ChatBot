/**
 * Unit tests for the trace step parser (src/pages/debugger/trace.ts).
 *
 * Pure-function tests (no mocks) covering the three-state degradation
 * contract from docs/full-implementation-design.md §3 / §7.1:
 * empty / texts / timeline, degraded flag, unknown-stage fallback and the
 * never-throws guarantee.
 */

import { describe, expect, it } from 'vitest'

import { parseTraceSteps, type TraceStage } from './trace'

const KINDS = ['empty', 'texts', 'timeline'] as const

describe('parseTraceSteps — empty (null/undefined/non-array/[])', () => {
  it('returns empty for null', () => {
    expect(parseTraceSteps(null)).toEqual({ kind: 'empty' })
  })

  it('returns empty for undefined', () => {
    expect(parseTraceSteps(undefined)).toEqual({ kind: 'empty' })
  })

  it('returns empty for non-array values (object/string/number)', () => {
    expect(parseTraceSteps('hello')).toEqual({ kind: 'empty' })
    expect(parseTraceSteps(42)).toEqual({ kind: 'empty' })
    expect(parseTraceSteps({ a: 1 })).toEqual({ kind: 'empty' })
    expect(parseTraceSteps({ intermediate_llm_responses: [] })).toEqual({
      kind: 'empty',
    })
  })

  it('returns empty for an empty array', () => {
    expect(parseTraceSteps([])).toEqual({ kind: 'empty' })
  })
})

describe('parseTraceSteps — texts (real data shape)', () => {
  it('maps a string[] into texts with degraded defaulting to false', () => {
    const result = parseTraceSteps(['first chunk', 'second chunk'])
    expect(result.kind).toBe('texts')
    if (result.kind === 'texts') {
      expect(result.items).toEqual(['first chunk', 'second chunk'])
      expect(result.degraded).toBeUndefined()
    }
  })

  it('filters out empty strings but keeps the rest', () => {
    const result = parseTraceSteps(['a', '', 'b', ''])
    expect(result.kind).toBe('texts')
    if (result.kind === 'texts') {
      expect(result.items).toEqual(['a', 'b'])
    }
  })

  it('falls back to empty when every string is empty', () => {
    expect(parseTraceSteps(['', ''])).toEqual({ kind: 'empty' })
  })
})

describe('parseTraceSteps — timeline (forward-compatible contract)', () => {
  const whitelist: Exclude<TraceStage, 'other'>[] = [
    'request',
    'reasoning',
    'tool_call',
    'tool_result',
    'response',
  ]

  it('maps whitelisted stages onto a timeline preserving order', () => {
    const result = parseTraceSteps([
      { stage: 'request', name: 'openai · gpt-4o' },
      { stage: 'reasoning', content: 'think step by step' },
      { stage: 'tool_call', name: 'search', args: '{"q":"ela"}' },
      { stage: 'tool_result', content: 'results...' },
      { stage: 'response', content: 'final answer' },
    ])
    expect(result.kind).toBe('timeline')
    if (result.kind === 'timeline') {
      expect(result.items.map((n) => n.stage)).toEqual(whitelist)
    }
  })

  it('maps every whitelisted stage name correctly', () => {
    const result = parseTraceSteps(whitelist.map((stage) => ({ stage })))
    expect(result.kind).toBe('timeline')
    if (result.kind === 'timeline') {
      expect(result.items.map((n) => n.stage)).toEqual(whitelist)
      // Whitelisted nodes carry no raw (raw is reserved for 'other').
      expect(result.items.every((n) => n.raw === undefined)).toBe(true)
    }
  })

  it('normalizes unknown stages to other and keeps the raw stage name', () => {
    const result = parseTraceSteps([{ stage: 'weird_stage', content: 'x' }])
    expect(result.kind).toBe('timeline')
    if (result.kind === 'timeline') {
      expect(result.items[0].stage).toBe('other')
      expect(result.items[0].raw).toBe('weird_stage')
      expect(result.items[0].content).toBe('x')
    }
  })

  it('defaults missing fields to empty strings', () => {
    const result = parseTraceSteps([{ stage: 'tool_call' }, { stage: 'response' }])
    expect(result.kind).toBe('timeline')
    if (result.kind === 'timeline') {
      expect(result.items[0]).toEqual({
        stage: 'tool_call',
        label: '',
        name: '',
        content: '',
        args: '',
      })
      expect(result.items[1].content).toBe('')
    }
  })

  it('parses tool_call name/args from node fields', () => {
    const result = parseTraceSteps([
      { stage: 'tool_call', name: 'web_search', args: 'query: ela bot' },
    ])
    expect(result.kind).toBe('timeline')
    if (result.kind === 'timeline') {
      expect(result.items[0].name).toBe('web_search')
      expect(result.items[0].args).toBe('query: ela bot')
    }
  })
})

describe('parseTraceSteps — degraded texts (unpredictable shapes)', () => {
  it('degrades mixed string/object arrays to texts with degraded: true', () => {
    const result = parseTraceSteps(['plain', { stage: 'response', content: 'obj' }])
    expect(result.kind).toBe('texts')
    if (result.kind === 'texts') {
      expect(result.degraded).toBe(true)
      expect(result.items[0]).toBe('plain')
      // 对象被 String() 化为 '[object Object]'（原始 JSON 由 UI 层折叠展示）。
      expect(result.items[1]).toBe('[object Object]')
    }
  })

  it('degrades arrays containing null without throwing (String() fallback)', () => {
    const result = parseTraceSteps([null, 'text'])
    expect(result.kind).toBe('texts')
    if (result.kind === 'texts') {
      expect(result.degraded).toBe(true)
      expect(result.items[0]).toBe('null')
      expect(result.items[1]).toBe('text')
    }
  })

  it('degrades object arrays whose stage is missing or not a string', () => {
    expect(parseTraceSteps([{ content: 'no stage here' }])).toMatchObject({
      kind: 'texts',
      degraded: true,
    })
    const withNumberStage = parseTraceSteps([{ stage: 42 }])
    expect(withNumberStage).toMatchObject({ kind: 'texts', degraded: true })
  })

  it('degrades arrays of non-string scalars (numbers) via String()', () => {
    const result = parseTraceSteps([1, 2, 3])
    expect(result.kind).toBe('texts')
    if (result.kind === 'texts') {
      expect(result.degraded).toBe(true)
      expect(result.items).toEqual(['1', '2', '3'])
    }
  })
})

describe('parseTraceSteps — input size guard (perf LOW-3)', () => {
  it('caps string arrays above 500 items to the first 500', () => {
    const big = Array.from({ length: 600 }, (_, i) => `chunk ${i}`)
    const result = parseTraceSteps(big)
    expect(result.kind).toBe('texts')
    if (result.kind === 'texts') {
      expect(result.items.length).toBe(500)
      expect(result.items[0]).toBe('chunk 0')
      expect(result.items[499]).toBe('chunk 499')
    }
  })

  it('caps timeline-shaped arrays above 500 items to the first 500', () => {
    const big = Array.from({ length: 600 }, (_, i) => ({
      stage: 'response',
      content: `r${i}`,
    }))
    const result = parseTraceSteps(big)
    expect(result.kind).toBe('timeline')
    if (result.kind === 'timeline') {
      expect(result.items.length).toBe(500)
      expect(result.items[499].content).toBe('r499')
    }
  })
})

describe('parseTraceSteps — never throws (fuzz)', () => {
  it('returns one of the three kinds for assorted malformed inputs', () => {
    const malformed: unknown[] = [
      [undefined],
      [NaN],
      [Symbol('sym')],
      [Object(Symbol('boxed')) as unknown],
      [Object(Symbol('in-array')) as unknown],
      [{ toString: () => { throw new Error('boom') } }],
      [[1, 2]],
      [{ stage: 'response', content: ['nested', 'array'] }],
      ['a', null, { stage: 'x' }, 42],
      [() => 'fn'],
      [BigInt(7)],
      [[]],
      [['inner'], ['inner2']],
    ]
    for (const input of malformed) {
      expect(KINDS).toContain(parseTraceSteps(input).kind)
    }
    // Never throws even for the whole set at once (nested Symbol in arrays
    // is the hardest case: String(array) implicitly converts every element).
    expect(KINDS).toContain(parseTraceSteps(malformed).kind)
  })
})
