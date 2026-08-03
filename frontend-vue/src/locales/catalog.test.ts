/**
 * Catalog parity tests — every language must expose exactly the same key
 * structure as zh (the default locale), so a missing key can never silently
 * fall back to another language.
 */
import { describe, expect, it } from 'vitest'
import de from './de'
import en from './en'
import es from './es'
import fr from './fr'
import ja from './ja'
import ko from './ko'
import ru from './ru'
import zh from './zh'

const CATALOGS = { zh, en, ja, ko, fr, de, es, ru } as const
const LANGS = Object.keys(CATALOGS)

type Leaf = string | number | boolean | null

/** Collect every dotted key path of a catalog (leaves are values). */
function collectPaths(node: Record<string, unknown>, prefix = ''): string[] {
  const paths: string[] = []
  for (const [key, value] of Object.entries(node)) {
    const path = prefix ? `${prefix}.${key}` : key
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      paths.push(...collectPaths(value as Record<string, unknown>, path))
    } else {
      paths.push(path)
    }
  }
  return paths
}

function collectLeaves(node: Record<string, unknown>, prefix = ''): Record<string, Leaf> {
  const leaves: Record<string, Leaf> = {}
  for (const [key, value] of Object.entries(node)) {
    const path = prefix ? `${prefix}.${key}` : key
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      Object.assign(leaves, collectLeaves(value as Record<string, unknown>, path))
    } else {
      leaves[path] = value as Leaf
    }
  }
  return leaves
}

describe('i18n catalog parity (all 8 languages)', () => {
  it('every language exposes the same key structure as zh', () => {
    const reference = collectPaths(zh).sort()
    for (const lang of LANGS) {
      const paths = collectPaths(CATALOGS[lang as keyof typeof CATALOGS]).sort()
      expect(paths, `${lang} key paths differ from zh`).toEqual(reference)
    }
  })

  it('every language has non-empty values for every key', () => {
    for (const lang of LANGS) {
      const leaves = collectLeaves(CATALOGS[lang as keyof typeof CATALOGS])
      const empty = Object.entries(leaves)
        .filter(([, value]) => value === '' || value === null)
        .map(([path]) => path)
      expect(empty, `${lang} has empty values for: ${empty.join(', ')}`).toEqual([])
    }
  })

  it('placeholder tokens are identical across languages', () => {
    const placeholders = (text: string): string[] =>
      Array.from(text.matchAll(/\{(\w+)\}/g), (m) => m[1]).sort()
    const reference = collectLeaves(zh)
    for (const lang of LANGS) {
      const leaves = collectLeaves(CATALOGS[lang as keyof typeof CATALOGS])
      for (const [path, zhValue] of Object.entries(reference)) {
        if (typeof zhValue !== 'string') continue
        const other = leaves[path]
        if (typeof other !== 'string') continue
        expect(
          placeholders(other),
          `${lang}.${path} placeholder mismatch`,
        ).toEqual(placeholders(zhValue))
      }
    }
  })
})
