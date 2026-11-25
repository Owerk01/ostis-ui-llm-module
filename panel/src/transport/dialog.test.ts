import assert from 'node:assert/strict'
import test from 'node:test'

import { DIALOG_NOT_FOUND_ERROR, DialogNotFoundError } from './types.ts'
import { isStableDialogId, newDialogId } from './dialogId.ts'

const VALID_DIALOG_ID = 'dialog-0123456789ab'

test('DialogNotFoundError carries the code and the dialog id', () => {
  const error = new DialogNotFoundError('dialog-0123456789ab')
  assert.ok(error instanceof Error)
  assert.equal(error.code, DIALOG_NOT_FOUND_ERROR)
  assert.equal(error.code, 'dialog_not_found')
  assert.equal(error.dialogId, 'dialog-0123456789ab')
  assert.equal(error.name, 'DialogNotFoundError')
  assert.match(error.message, /dialog_not_found/)
})

test('DialogNotFoundError identifies a missing dialog, not a broken transport', () => {
  const error = new DialogNotFoundError('dialog-ffffffffffffffff')
  assert.equal(error instanceof DialogNotFoundError, true)
  assert.equal(error instanceof Error, true)
  assert.equal(error.dialogId, 'dialog-ffffffffffffffff')
})

test('stability rules for dialog ids used by ensureDialog', () => {
  assert.equal(isStableDialogId(VALID_DIALOG_ID), true)
  assert.equal(isStableDialogId('dialog-short'), false)
  assert.equal(isStableDialogId('dialog-0123456789abc'), false)
  assert.equal(isStableDialogId('70207'), false)
  assert.equal(newDialogId().startsWith('dialog-'), true)
})
