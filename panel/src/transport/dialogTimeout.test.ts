import assert from 'node:assert/strict'
import test from 'node:test'

import { resolveClientTimeoutMs } from './timeout.ts'

test('resolveClientTimeoutMs: явно переданный clientTimeoutMs = 500, а не 30 с', () => {
  assert.equal(resolveClientTimeoutMs(500), 500)
})

test('resolveClientTimeoutMs: по умолчанию 35000 (не 30000)', () => {
  assert.equal(resolveClientTimeoutMs(undefined), 35_000)
})

test('resolveClientTimeoutMs: некорректное значение заменяется на fallback', () => {
  assert.equal(resolveClientTimeoutMs(-1), 35_000)
  assert.equal(resolveClientTimeoutMs(NaN as unknown as number), 35_000)
})
