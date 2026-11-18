import assert from 'node:assert/strict'
import test from 'node:test'

import { formatElapsed } from './formatElapsed.ts'

test('formatElapsed: zero and ordinary values', () => {
  assert.equal(formatElapsed(0), '0,0 с')
  assert.equal(formatElapsed(950), '0,9 с')
  assert.equal(formatElapsed(1500), '1,5 с')
})

test('formatElapsed: clamps negative and values above transport timeout', () => {
  assert.equal(formatElapsed(-1000), '0,0 с')
  assert.equal(formatElapsed(180_000), '180,0 с')
  assert.equal(formatElapsed(10_000_000), '180,0 с')
})
