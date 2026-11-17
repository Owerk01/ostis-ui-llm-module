# 01. Контракты

Статус: черновик M0. Полная версия заполняется в M4-T2 и отправляется команде на ревью.

## Что фиксируется на этапе 1

- Список существующих идентификаторов, которые только упоминаются (AGENTS.md, 3.6).
- Список новых идентификаторов ассистента (AGENTS.md, 3.6).
- Контракт действия `action_answer_ui_development_question` (AGENTS.md, 3.7).
- Контракт транспортов и `AssistantPanelProps` (AGENTS.md, 3.12).
- Известные ограничения: мягкая отмена в режиме `sc-memory`, синхронный
  `on_event` (AGENTS.md, 3.11).

## M0: платформа

| Параметр | Значение |
|---|---|
| sc-machine | 0.10.5, официальный prebuilt Linux x86_64 |
| sc-builder | 0.10.5 |
| Адрес | `ws://127.0.0.1:8090/ws_json` |
| Docker | не требуется |
| Схема UI | `external/ostis-ui-editor/docs/abstract_ui_model.scs` (не копируется) |
| Базовые онтологии | `external/ostis-example-app/knowledge-base` |

## Открытые вопросы к команде (раздел 7 AGENTS.md)

- [ ] Версия sc-machine: 0.10.0 или 0.10.5?
- [ ] Утверждение 18 новых идентификаторов.
- [ ] Размещение `kb/ui_assistant/` в дереве ostis-example-app.
- [ ] Контракт `AssistantPanelProps` и способ встраивания.
- [ ] Read-only границы этапа 1.
