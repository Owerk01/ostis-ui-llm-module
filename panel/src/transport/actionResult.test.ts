import assert from 'node:assert/strict'
import test from 'node:test'

import { findMessageInResult } from './actionResult.ts'

interface Addr {
  value: number
  isValid(): boolean
}
interface Row {
  get(alias: string): Addr | undefined
}
const addr = (value: number, valid = true): Addr => ({ value, isValid: () => valid })
const row = (value: number, valid = true): Row => ({ get: () => addr(value, valid) })

test('findMessageInResult picks the assistant message, skips links', async () => {
  const rows = [row(1), row(2), row(3)]
  const found = await findMessageInResult(rows, async (item) => item.value === 2)
  assert.equal(found?.value, 2)
})

test('findMessageInResult returns null when nothing is a message', async () => {
  const found = await findMessageInResult([row(1, false)], async () => true)
  assert.equal(found, null)
})
