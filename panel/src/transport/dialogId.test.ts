import assert from 'node:assert/strict'
import test from 'node:test'

import { isStableDialogId } from './dialogId.ts'

test('raw ScAddr is not a stable dialog id', () => {
  assert.equal(isStableDialogId('70207'), false)
  assert.equal(isStableDialogId(''), false)
})

test('nrel_ui_id value is a stable dialog id', () => {
  assert.equal(isStableDialogId('dialog-a1b2c3d4e5f6'), true)
  assert.equal(isStableDialogId('dialog-xyz'), false)
})
