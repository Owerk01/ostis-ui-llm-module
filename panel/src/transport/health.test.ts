import assert from 'node:assert/strict'
import test from 'node:test'

import { healthFromMessages } from './health.ts'

const assistant = (over: Record<string, unknown> = {}) => ({
  id: 'm', role: 'assistant' as const, text: 'x', state: 'done' as const,
  createdAt: '2026-11-18T00:00:00Z', code: 'ok' as const, retryable: false, ...over,
})

test('health: no messages means unknown source and null model', () => {
  const health = healthFromMessages([])
  assert.equal(health.knowledgeSource, 'unknown')
  assert.equal(health.model, null)
  assert.equal(health.packVersion, '')
})

test('health: values come from the last assistant message', () => {
  const health = healthFromMessages([
    assistant({ knowledgeSource: 'fallback', model: 'old' }),
    assistant({ knowledgeSource: 'kb', model: 'qwen3.5:4b', promptVersion: 'v4|pack:2026-11-18T00:00:00Z' }),
  ])
  assert.equal(health.knowledgeSource, 'kb')
  assert.equal(health.model, 'qwen3.5:4b')
  assert.equal(health.packVersion, '2026-11-18T00:00:00Z')
})
