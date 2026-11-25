/**
 * Точный дамп каталога редактора.
 *
 * Импортирует исходники external/ostis-ui-editor напрямую, ничего не меняя.
 * Печатает JSON в stdout; сборщик knowledge pack читает его.
 *
 * Запуск: npx --yes tsx tools/dump_catalog.ts
 */
import { COMPONENT_CATALOG } from '../external/ostis-ui-editor/client/src/model/catalog'
import {
  ACTION_LINK_SOURCES,
  INPUT_TARGET_TYPES,
  OUTPUT_TARGET_TYPES,
} from '../external/ostis-ui-editor/client/src/model/linkRules'
import { CORE_PROPS } from '../external/ostis-ui-editor/client/src/model/propSets'
import {
  CLASS_INTERFACE,
  PROP_TO_CLASS,
  REL,
  TYPE_TO_CLASS,
} from '../external/ostis-ui-editor/client/src/sc/names'
import { ru } from '../external/ostis-ui-editor/client/src/i18n/ru'

const catalog = {
  class_interface: CLASS_INTERFACE,
  types: COMPONENT_CATALOG.map((entry) => ({
    type_id: entry.typeId,
    // Подпись живёт в i18n редактора: ключ `type.<typeId>`.
    label_ru: ru[`type.${entry.typeId}` as keyof typeof ru],
    preview: entry.preview,
    sc_class: TYPE_TO_CLASS[entry.typeId],
    allowed_props: entry.allowedProps,
    defaults: entry.defaults,
  })),
  properties: CORE_PROPS.map((key) => ({
    key,
    sc_class: PROP_TO_CLASS[key],
  })),
  relations: Object.entries(REL).map(([kind, idtf]) => ({ kind, idtf })),
  link_rules: {
    action_sources: [...ACTION_LINK_SOURCES],
    input_targets: [...INPUT_TARGET_TYPES],
    output_targets: [...OUTPUT_TARGET_TYPES],
  },
}

process.stdout.write(`${JSON.stringify(catalog, null, 2)}\n`)
