/**
 * Единая точка доступа к ts-sc-client.
 *
 * Пакет ts-sc-client 0.5 публикует CommonJS: в Node namespace-импорт содержит
 * `default`, а в браузерной сборке Vite — именованные экспорты. Нормализуем оба
 * варианта, чтобы transport работал и в редакторе, и в Node-скрипте без React.
 */

import * as Sc from 'ts-sc-client'

type ScModule = typeof Sc
const api = ((Sc as unknown as { default?: ScModule }).default ?? Sc) as ScModule

export const ScAddr = api.ScAddr
export const ScClient = api.ScClient
export const ScConstruction = api.ScConstruction
export const ScEventSubscription = api.ScEventSubscription
export const ScEventSubscriptionParams = api.ScEventSubscriptionParams
export const ScEventType = api.ScEventType
export const ScHelper = api.ScHelper
export const ScLinkContent = api.ScLinkContent
export const ScLinkContentType = api.ScLinkContentType
export const ScTemplate = api.ScTemplate
export const ScType = api.ScType

export type ScAddr = InstanceType<typeof api.ScAddr>
export type ScClient = InstanceType<typeof api.ScClient>
export type ScConstruction = InstanceType<typeof api.ScConstruction>
export type ScEventSubscription = InstanceType<typeof api.ScEventSubscription>
export type ScEventSubscriptionParams = InstanceType<typeof api.ScEventSubscriptionParams>
export type ScHelper = InstanceType<typeof api.ScHelper>
export type ScLinkContent = InstanceType<typeof api.ScLinkContent>
export type ScTemplate = InstanceType<typeof api.ScTemplate>
