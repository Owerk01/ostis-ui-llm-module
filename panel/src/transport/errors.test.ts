import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  ASSISTANT_BUSY_ERROR,
  ASSISTANT_CANCELLED_ERROR,
  ASSISTANT_SCHEMA_MISSING_ERROR,
  ASSISTANT_TIMEOUT_ERROR,
  AssistantBusy,
  AssistantCancelled,
  AssistantDialogNotFound,
  AssistantSchemaMissing,
  AssistantTimeout,
  transportErrorFromCode,
} from './errors.ts'
import { outcomeCodeFromError } from './outcome.ts'
import { DialogNotFoundError } from './types.ts'

const contract = JSON.parse(
  readFileSync(new URL('../../../contract/identifiers.json', import.meta.url), 'utf8'),
) as { transportErrors: Record<string, string> }

test('типизированные исходы несут код, данные и name', () => {
  const timeout = new AssistantTimeout('70207', 'dialog-1')
  assert.equal(timeout.actionId, '70207')
  assert.equal(timeout.dialogId, 'dialog-1')
  assert.equal(timeout.code, ASSISTANT_TIMEOUT_ERROR)
  assert.equal(timeout.name, 'AssistantTimeout')
  // Таймаут — не «повторить», а «проверить».
  assert.equal(outcomeCodeFromError(timeout), 'pending')

  const cancelled = new AssistantCancelled('70207')
  assert.equal(cancelled.actionId, '70207')
  assert.equal(cancelled.code, ASSISTANT_CANCELLED_ERROR)
  assert.equal(outcomeCodeFromError(cancelled), 'cancelled')

  const schema = new AssistantSchemaMissing(['nrel_ui_message_code'])
  assert.equal(schema.code, ASSISTANT_SCHEMA_MISSING_ERROR)
  assert.match(schema.message, /nrel_ui_message_code/)
  assert.equal(outcomeCodeFromError(schema), 'schema_missing')

  const busy = new AssistantBusy()
  assert.equal(busy.code, ASSISTANT_BUSY_ERROR)
  assert.equal(outcomeCodeFromError(busy), 'busy')

  const missing = new AssistantDialogNotFound('dialog-2')
  assert.equal(missing.code, 'dialog_not_found')
  assert.equal(missing.dialogId, 'dialog-2')
  assert.equal(outcomeCodeFromError(missing), 'dialog_not_found')
})

test('Legacy DialogNotFoundError — подтип AssistantDialogNotFound', () => {
  const error = new DialogNotFoundError('dialog-3')
  assert.ok(error instanceof AssistantDialogNotFound)
  assert.equal(error.code, 'dialog_not_found')
  assert.equal(error.dialogId, 'dialog-3')
})

test('коды исходов транспорта совпадают с contract/identifiers.json', () => {
  assert.equal(contract.transportErrors.timeout, ASSISTANT_TIMEOUT_ERROR)
  assert.equal(contract.transportErrors.cancelled, ASSISTANT_CANCELLED_ERROR)
  assert.equal(contract.transportErrors.schemaMissing, ASSISTANT_SCHEMA_MISSING_ERROR)
  assert.equal(contract.transportErrors.dialogNotFound, 'dialog_not_found')
  assert.equal(contract.transportErrors.busy, ASSISTANT_BUSY_ERROR)
})

test('transportErrorFromCode различает исходы и не подменяет неизвестные', () => {
  assert.ok(transportErrorFromCode('assistant_timeout', { actionId: '1' }) instanceof AssistantTimeout)
  assert.ok(transportErrorFromCode('assistant_cancelled') instanceof AssistantCancelled)
  assert.ok(transportErrorFromCode('cancelled') instanceof AssistantCancelled)
  assert.ok(transportErrorFromCode('schema_missing') instanceof AssistantSchemaMissing)
  assert.ok(transportErrorFromCode('dialog_not_found') instanceof AssistantDialogNotFound)
  assert.ok(transportErrorFromCode('assistant_busy') instanceof AssistantBusy)
  assert.ok(transportErrorFromCode('busy') instanceof AssistantBusy)
  assert.equal(transportErrorFromCode('llm_unavailable'), null)
})
