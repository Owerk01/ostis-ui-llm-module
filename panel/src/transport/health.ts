/** Состояние, которое панель может вывести из последнего ответа в БЗ. */

import type { AssistantMessage, KnowledgeSource } from './types'

export interface HealthFromMessages {
  knowledgeSource: KnowledgeSource
  model: string | null
  packVersion: string
}

export function healthFromMessages(messages: AssistantMessage[]): HealthFromMessages {
  const last = [...messages].reverse().find((message) => message.role === 'assistant')
  const packVersion = last?.promptVersion?.split('|pack:')[1] ?? ''
  return {
    knowledgeSource: last?.knowledgeSource ?? 'unknown',
    model: last?.model ?? null,
    packVersion,
  }
}
