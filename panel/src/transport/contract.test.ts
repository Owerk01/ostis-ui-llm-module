import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { CONTRACT_VERSION } from './contract.ts'

const rootVersion = readFileSync(new URL('../../../VERSION', import.meta.url), 'utf8').trim()

test('CONTRACT_VERSION совпадает с корневым VERSION', () => {
  assert.equal(CONTRACT_VERSION, rootVersion)
  assert.match(CONTRACT_VERSION, /^\d+\.\d+\.\d+$/)
})
