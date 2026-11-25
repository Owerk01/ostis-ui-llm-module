# Панель ассистента разработчика ПИ

Изолированный компонент диалога. Панель не знает, откуда приходят ответы:
`sc-memory` — основной транспорт через sc-память, `direct-http` — отладочный.

> **AssistantPanel — не продуктовый UI.** Это эталонный dev-стенд и пример
> встраивания. Продуктовый чат делает редактор, подключая standalone-транспорт
> без React (`npm run build:transport` → `dist-transport/`) и свой UI-кит.

## Что внутри

```
src/
├── index.ts                    # публичный API библиотеки
├── AssistantPanel.tsx          # публичный компонент
├── AssistantPanel.module.css
├── transport/
│   ├── index.ts                # публичный API standalone-пакета без React
│   ├── types.ts                # контракт AssistantTransport
│   ├── scMemory.ts             # боевой транспорт через ts-sc-client
│   ├── directHttp.ts           # отладочный HTTP/SSE-транспорт
│   └── contract.ts             # CONTRACT_VERSION из корневого VERSION
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
npm run build:lib        # dist-lib/index.js, index.css и .d.ts (React, dev-стенд)
npm run build:transport  # dist-transport/ — пакет логики без React
```

Для продуктового UI используйте `dist-transport/`: там нет React, CSS и
`AssistantPanel`, а `ts-sc-client` остаётся peerDependency. Импорт:

```ts
import { ScClient, ScMemoryTransport } from 'ostis-ui-assistant-dialog-transport'

// Конструктор сам открывает WebSocket; метода connect() у ts-sc-client нет.
const client = new ScClient('ws://127.0.0.1:8090/ws_json')
const transport = new ScMemoryTransport(client, 35_000)
```

Полная последовательность вызовов и обработка всех кодов — в
[`docs/04_INTEGRATION.md`](../docs/04_INTEGRATION.md).

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
- `ensureDialog(dialogId?)` вызывается один раз при монтировании: с переданным
  `dialogId` — открыть существующий, без — создать новый; неизвестный id бросает
  `DialogNotFoundError`;
- `ask(dialogId, question, options?)` принимает `options.context` и плоские
  `onDelta`/`signal` для совместимости; может вызывать `onDelta` много раз, а
  завершиться сообщением `done`/`cancelled` или ошибкой; при неизвестном
  диалоге — `dialog_not_found`, без подмены диалога;
- `cancel(messageId)` получает локальный id сообщения панели. Транспорт сам
  сопоставляет его со своим запросом; после отмены `ask()` должен разрешиться
  сообщением `cancelled`, а не падать.

### Props

| Prop | Тип | Назначение |
|---|---|---|
| `transport` | `AssistantTransport` | обязательный транспорт |
| `dialogId` | `string?` | возобновить существующий диалог через `ensureDialog(dialogId)`; иначе создаётся новый |
| `title` | `string?` | заголовок, по умолчанию «Ассистент разработчика ПИ» |
| `className` | `string?` | дополнительный класс на корень |
| `onSourceClick` | `(ref: SourceRef) => void` | клик по чипу основания |
| `context` | `DialogContextOptions?` | контекст экземпляра: `none`/`selection`/`whole`, `interfaceId`, `componentIds` |

Поля `onContextChange`, `onProposedChange` зарезервированы и не реализованы.

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

## Ограничения текущей версии

- в `sc-memory` отмена **мягкая**: панель перестаёт ждать и помечает сообщение
  «Отменено», агент дописывает ответ в БЗ; после перезагрузки ответ появится
  в истории (жёсткая отмена пока не реализована);
- в `sc-memory` нет стриминга: `onDelta` вызывается один раз с полным текстом
  после записи в БЗ;
- в `direct-http` стриминг начинается после полной генерации и валидации:
  отсутствие выдуманных идентификаторов важнее потоковости;
- история `direct-http` хранится в памяти сервиса и теряется при перезапуске;
  история `sc-memory` постоянная, в БЗ.
