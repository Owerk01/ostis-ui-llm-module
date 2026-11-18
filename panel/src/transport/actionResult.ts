/** Выбор сообщения из структуры результата действия. */

export interface ResultAddress {
  value: number
  isValid(): boolean
}

export interface ResultRow {
  get(alias: string): ResultAddress | undefined
}

/** Среди элементов структуры результата ищем узел assistant-сообщения. */
export async function findMessageInResult(
  rows: ResultRow[],
  isAssistant: (addr: ResultAddress) => Promise<boolean>,
): Promise<ResultAddress | null> {
  for (const row of rows) {
    const element = row.get('_element')
    if (element?.isValid() && (await isAssistant(element))) return element
  }
  return null
}
