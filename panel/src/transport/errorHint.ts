/** Подсказка в баннере ошибки зависит от выбранного транспорта. */

export function errorHint(kind: 'direct-http' | 'sc-memory'): string {
  return kind === 'sc-memory'
    ? 'Проверьте, что запущены sc-machine и агент: `make kb-load`, `make agent`'
    : 'Проверьте, что сервис запущен: `make service`'
}
