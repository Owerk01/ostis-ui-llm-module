import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const sources = [
  'AssistantPanel.tsx',
  'transport/scMemory.ts',
  'transport/directHttp.ts',
  'transport/health.ts',
  'transport/actionResult.ts',
]

test('library code does not require window timers', () => {
  for (const name of sources) {
    const text = readFileSync(new URL(`./${name}`, import.meta.url), 'utf8')
    assert.doesNotMatch(text, /window\.(setInterval|clearInterval|setTimeout|clearTimeout)/, name)
  }
})
