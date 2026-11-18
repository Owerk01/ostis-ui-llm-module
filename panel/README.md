# Панель ассистента разработчика ПИ

Изолированный компонент диалога (задача 2.b.i, FR-1, NFR-1). Панель не знает,
откуда приходят ответы: `sc-memory` — боевой транспорт через sc-память,
`direct-http` — отладочный.

## Что внутри

```
src/
├── index.ts                    # публичный API библиотеки (M4-T1)
├── AssistantPanel.tsx          # публичный компонент
├── AssistantPanel.module.css
├── transport/
│   ├── types.ts                # контракт AssistantTransport (AGENTS.md 3.12)
│   ├── scMemory.ts             # боевой транспорт через ts-sc-client
│   └── directHttp.ts           # отладочный HTTP/SSE-транспорт
├── components/
│   ├── MessageList.tsx         # лента сообщений, ошибки, повтор
│   ├── Composer.tsx            # ввод и отправка
│   ├── StatusBar.tsx           # модель, источник знаний, таймер, отмена
│   ├── SourceChips.tsx         # чипы nrel_ui_answer_source
│   └── EmptyState.tsx          # подсказки для пустого диалога
└── dev/                        # dev-стенд (в редактор не встраивается)
```

## Зависимости

Пировые зависимости (должны уже быть в клиенте редактора): `react` 19,
`react-dom` 19, `ts-sc-client` 0.5. Для сборки библиотеки нужны Node 20+ и npm.
UI-кит и глобальные стили редактора не используются.

## Сборка и встраивание в редактор

```bash
cd panel
npm ci
npm run build:lib        # dist-lib/index.js, index.css и .d.ts
```

`dist-lib/` — артефакт сборки (в `.gitignore`). Подключить его можно двумя
способами, без правок кода этого репозитория:

1. Локальной npm-зависимостью в клиенте редактора:

```bash
cd client
npm install file:../ostis-ui-assistant-panel
```

2. Скопировать каталог `panel/dist-lib/` в клиент, например в
   `client/vendor/ostis-ui-assistant-panel/`, и указать тот же `file:`-путь.

```tsx
import { AssistantPanel, ScMemoryTransport } from 'ostis-ui-assistant-panel'
import type { AssistantTransport, SourceRef } from 'ostis-ui-assistant-panel'
import 'ostis-ui-assistant-panel/index.css'   // стили CSS-модулей, префикс oaa-

const transport: AssistantTransport = new ScMemoryTransport(editor.scClient)

export function RightSidebar() {
  return (
    <AssistantPanel
      transport={transport}
      title="Ассистент разработчика ПИ"
      onSourceClick={(ref: SourceRef) => editor.highlightNode(ref.scAddr)}
    />
  )
}
```

`ScMemoryTransport` принимает **уже существующий** `ScClient` редактора: новый
websocket не открывается. Остальной код панели к `ts-sc-client` не обращается.

Требования к транспорту:

- объект должен быть **стабильным** между рендерами (`useMemo`/модульная переменная),
  иначе панель заново загрузит диалог и историю;
- `ensureDialog()` вызывается один раз при монтировании, если не передан `dialogId`;
- `ask()` может вызывать `onDelta` много раз, а завершиться сообщением в состоянии
  `done`, `cancelled` или отклониться с ошибкой;
- `cancel(messageId)` получает локальный id сообщения панели. Транспорт сам
  сопоставляет его со своим запросом; после отмены `ask()` должен разрешиться
  сообщением `cancelled`, а не падать.

### Props

| Prop | Тип | Назначение |
|---|---|---|
| `transport` | `AssistantTransport` | обязательный транспорт |
| `dialogId` | `string?` | возобновить существующий диалог; иначе создаётся новый |
| `title` | `string?` | заголовок, по умолчанию «Ассистент разработчика ПИ» |
| `className` | `string?` | дополнительный класс на корень |
| `onSourceClick` | `(ref: SourceRef) => void` | клик по чипу основания |

Поля этапа 2 (`contextSelection`, `onContextChange`, `onProposedChange`)
зарезервированы в типе и не реализованы.

## Изоляция стилей

- все стили — CSS-модули с классами `oaa-*`;
- нет глобальных селекторов, CSS-переменных и UI-китов;
- нет обращений к роутеру, сторам и глобальному состоянию редактора;
- корень панели — `section.oaa-panel` с собственной типографикой и `box-sizing`.

## Dev-стенд

```bash
make service                 # FastAPI direct-http на 127.0.0.1:8770
make panel                   # Vite на 127.0.0.1:5173
```

В левой колонке можно выбрать транспорт (`sc-memory` по умолчанию или
`direct-http`), указать адрес sc-сервера/сервиса и посмотреть выбранное
основание — так проверяется `onSourceClick`.

Для боевого режима нужны запущенные sc-machine и агент:

```bash
make machine
make agent        # ASSISTANT_TRANSPORT=sc-memory
make panel
```

Для отладочного — `make service` и переключатель `direct-http`.

Проверка сборки и типов:

```bash
cd panel
npm ci
npm run typecheck
npm run build        # dev-стенд → panel/dist
npm run build:lib    # библиотека → panel/dist-lib
```

## Поведение

- при отправке сразу появляются сообщение пользователя и ответ в состоянии
  `pending` со спиннером и секундомером (цель — ≤ 300 мс, фактически ~80 мс);
- «Отмена» доступна всё время генерации; в direct-http она прерывает поток и
  помечает сообщение «Отменено»;
- ошибка показывается красной плашкой с причиной и кнопкой «Повторить»;
- чипы оснований появляются после `done` и кликабельны, если передан `onSourceClick`;
- при `knowledgeSource = fallback` показывается баннер о локальной копии знаний.

## Ограничения этапа 1

- в `sc-memory` отмена **мягкая**: панель перестаёт ждать и помечает сообщение
  «Отменено», агент дописывает ответ в БЗ; после перезагрузки ответ появится
  в истории (жёсткая отмена — этап 2);
- в `sc-memory` нет стриминга: `onDelta` вызывается один раз с полным текстом
  после записи в БЗ;
- в `direct-http` стриминг начинается после полной генерации и валидации:
  FR-13 (никаких выдуманных идентификаторов) важнее потоковости;
- история `direct-http` хранится в памяти сервиса и теряется при перезапуске;
  история `sc-memory` постоянная, в БЗ.
