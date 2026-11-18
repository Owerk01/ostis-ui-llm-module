/** Стабильный идентификатор диалога (значение nrel_ui_id). */

export function isStableDialogId(value: string): boolean {
  return /^dialog-[0-9a-f]{12}$/.test(value)
}

export function newDialogId(): string {
  return `dialog-${globalThis.crypto.randomUUID().replaceAll('-', '').slice(0, 12)}`
}
