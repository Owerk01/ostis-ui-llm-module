/**
 * Типизированные исходы транспорта.
 *
 * Отличаются от кодов сообщений: там код описывает исход сообщения в БЗ, а здесь —
 * причина, по которой `ask()` не вернул готовый ответ. `outcome` нужен панели,
 * чтобы переиспользовать правило `retryable` из T5.
 */

import type { OutcomeCode } from './outcome.ts'

export const ASSISTANT_TIMEOUT_ERROR = 'assistant_timeout'
export const ASSISTANT_CANCELLED_ERROR = 'assistant_cancelled'
export const ASSISTANT_SCHEMA_MISSING_ERROR = 'assistant_schema_missing'
export const ASSISTANT_DIALOG_NOT_FOUND_ERROR = 'dialog_not_found'
export const ASSISTANT_BUSY_ERROR = 'assistant_busy'

export class AssistantTimeout extends Error {
  readonly code = ASSISTANT_TIMEOUT_ERROR
  // Действие ещё в работе: «Повторить» здесь не годится, нужен «Проверить».
  readonly outcome: OutcomeCode = 'pending'
  readonly actionId: string
  readonly dialogId?: string

  constructor(actionId: string, dialogId?: string) {
    super(`Ответ ещё готовится: действие ${actionId} не завершилось за отведённое время`)
    this.name = 'AssistantTimeout'
    this.actionId = actionId
    this.dialogId = dialogId
  }
}

export class AssistantCancelled extends Error {
  readonly code = ASSISTANT_CANCELLED_ERROR
  readonly outcome: OutcomeCode = 'cancelled'
  readonly actionId?: string

  constructor(actionId?: string) {
    super('Запрос отменён')
    this.name = 'AssistantCancelled'
    this.actionId = actionId
  }
}

export class AssistantSchemaMissing extends Error {
  readonly code = ASSISTANT_SCHEMA_MISSING_ERROR
  readonly outcome: OutcomeCode = 'schema_missing'
  readonly missing: string[]

  constructor(missing: string[] = []) {
    super(
      missing.length
        ? `Схема ассистента не загружена в БЗ: ${missing.join(', ')}. Выполните make kb-load`
        : 'Схема ассистента не загружена в БЗ. Выполните make kb-load',
    )
    this.name = 'AssistantSchemaMissing'
    this.missing = missing
  }
}

export class AssistantDialogNotFound extends Error {
  readonly code = ASSISTANT_DIALOG_NOT_FOUND_ERROR
  readonly outcome: OutcomeCode = 'dialog_not_found'
  readonly dialogId: string

  constructor(dialogId: string) {
    super(`dialog_not_found: диалог ${dialogId} не найден`)
    this.name = 'AssistantDialogNotFound'
    this.dialogId = dialogId
  }
}

export class AssistantBusy extends Error {
  readonly code = ASSISTANT_BUSY_ERROR
  readonly outcome: OutcomeCode = 'busy'

  constructor() {
    super('Сервис занят: очередь запросов переполнена')
    this.name = 'AssistantBusy'
  }
}

/** Преобразование кода ошибки direct-http в типизированный исход транспорта. */
export function transportErrorFromCode(
  code: string,
  context: { actionId?: string; dialogId?: string; missing?: string[] } = {},
): Error | null {
  switch (code) {
    case ASSISTANT_TIMEOUT_ERROR:
      return new AssistantTimeout(context.actionId ?? 'unknown', context.dialogId)
    case ASSISTANT_CANCELLED_ERROR:
    case 'cancelled':
      return new AssistantCancelled(context.actionId)
    case ASSISTANT_SCHEMA_MISSING_ERROR:
    case 'schema_missing':
      return new AssistantSchemaMissing(context.missing)
    case ASSISTANT_DIALOG_NOT_FOUND_ERROR:
      return new AssistantDialogNotFound(context.dialogId ?? 'unknown')
    case ASSISTANT_BUSY_ERROR:
    case 'busy':
      return new AssistantBusy()
    default:
      return null
  }
}
