import assert from 'node:assert/strict'
import test from 'node:test'

import { errorHint } from './errorHint.ts'

test('sc-memory error mentions platform and agent', () => {
  assert.match(errorHint('sc-memory'), /make kb-load/)
  assert.match(errorHint('sc-memory'), /make agent/)
  assert.doesNotMatch(errorHint('sc-memory'), /make service/)
})

test('direct-http error mentions service', () => {
  assert.match(errorHint('direct-http'), /make service/)
})
