/**
 * Точный дамп каталога редактора.
 *
 * Импортирует исходники external/ostis-ui-editor напрямую, ничего не меняя.
 * Печатает JSON в stdout; сборщик knowledge pack читает его.
 *
 * Запуск: npx --yes tsx tools/dump_catalog.ts
 */
import { COMPONENT_CATALOG } from '../external/ostis-ui-editor/client/src/model/catalog'
import { CORE_PROPS } from '../external/ostis-ui-editor/client/src/model/propSets'
import {
  CLASS_INTERFACE,
  PROP_TO_CLASS,
  REL,
  TYPE_TO_CLASS,
} from '../external/ostis-ui-editor/client/src/sc/names'

const catalog = {
  class_interface: CLASS_INTERFACE,
  types: COMPONENT_CATALOG.map((entry) => ({
    type_id: entry.typeId,
    label_ru: entry.label,
    preview: entry.preview,
    sc_class: TYPE_TO_CLASS[entry.typeId],
    defaults: entry.defaults,
  })),
  properties: CORE_PROPS.map((key) => ({
    key,
    sc_class: PROP_TO_CLASS[key],
  })),
  relations: Object.entries(REL).map(([kind, idtf]) => ({ kind, idtf })),
}

process.stdout.write(`${JSON.stringify(catalog, null, 2)}\n`)
