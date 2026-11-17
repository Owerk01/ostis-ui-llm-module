# 02. Знания

Статус: черновик M0. Полная инструкция заполняется в M4-T3.

## Источники

| Что | Откуда | Коммит |
|---|---|---|
| Типы, свойства, значения по умолчанию | `external/ostis-ui-editor` (`docs/catalog.md`, `client/src/model/catalog.ts`, `client/src/sc/names.ts`) | `f6eb4fa` |
| Формальная схема UI | `external/ostis-ui-editor/docs/abstract_ui_model.scs` | `f6eb4fa` |
| HTML-представление (справка) | `external/ostis-ui` | `a673766` |
| A/B/C-адаптация (справка) | `external/UI-adaptation` | `5c3d627` |

Фактические коммиты — [`../knowledge/provenance.json`](../knowledge/provenance.json).

## Сборка БЗ в M0

`platform/repo.path` ссылается на external-файлы напрямую. Сборка:
`make kb` → `.runtime/kb.bin`. Наши знания (`kb/ui_assistant/`) добавляются
в repo.path в M2.

Пересборка knowledge pack и генерация `ui_catalog_knowledge.scs` — M1-T2/M2-T3.
