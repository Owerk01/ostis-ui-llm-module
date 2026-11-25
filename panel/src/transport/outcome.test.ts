import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  codedError,
  DEFAULT_CODE,
  isRetryable,
  OUTCOME_CODES,
  outcomeCodeFromError,
  PENDING_CODE,
  toOutcomeCode,
  type OutcomeCode,
} from './outcome.ts'

const contract = JSON.parse(
  readFileSync(new URL('../../../contract/identifiers.json', import.meta.url), 'utf8'),
) as {
  relation: string
  outcomeCodes: string[]
  retryableCodes: string[]
  pendingCode: string
  defaultCode: string
}

test('коды исхода совпадают с contract/identifiers.json', () => {
  assert.equal(contract.relation, 'nrel_ui_message_code')
  assert.deepEqual([...OUTCOME_CODES], contract.outcomeCodes)
  assert.equal(PENDING_CODE, contract.pendingCode)
  assert.equal(DEFAULT_CODE, contract.defaultCode)
})

test('каждый код из контракта читается transports', () => {
  const codes: OutcomeCode[] = [...OUTCOME_CODES, PENDING_CODE]
  for (const code of codes) assert.equal(toOutcomeCode(code), code)
  assert.equal(toOutcomeCode(null), DEFAULT_CODE)
  assert.equal(toOutcomeCode('busy'), 'busy')
  assert.equal(toOutcomeCode('неизвестный', 'internal'), 'internal')
})

test('Повторить доступен только для временных ошибок', () => {
  const retryable = new Set(contract.retryableCodes)
  for (const code of [...OUTCOME_CODES, PENDING_CODE]) {
    assert.equal(isRetryable(code), retryable.has(code), code)
  }
  assert.equal(isRetryable('schema_missing'), false)
  assert.equal(isRetryable('invalid_request'), false)
  assert.equal(isRetryable(PENDING_CODE), false)
})

test('код ошибки из типизированного исключения', () => {
  assert.equal(outcomeCodeFromError(codedError('занято', 'busy')), 'busy')
  assert.equal(outcomeCodeFromError(new Error('сеть')), 'internal')
  assert.equal(outcomeCodeFromError({ code: 'llm_timeout' }), 'llm_timeout')
})
