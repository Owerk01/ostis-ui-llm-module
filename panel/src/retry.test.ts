import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('./AssistantPanel.tsx', import.meta.url), 'utf8')

test('retry creates a new full turn and keeps the old turn', () => {
  assert.match(source, /void run\(question, true\)/)
  assert.doesNotMatch(source, /previous\.filter\(\(message\) => message\.id !== messageId\)/)
})
