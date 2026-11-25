// Заглушка React для tools/dump_catalog.ts.
//
// `catalog.ts` импортирует i18n, а i18n реэкспортирует LocaleProvider с React.
// Дампу нужны только данные каталога, поэтому React подменяется минимальным
// набором функций. Это не попадает в сборку БЗ и не меняет external/.
const noop = () => {}

module.exports = {
  createContext: (value) => ({ Provider: noop, Consumer: noop, _currentValue: value }),
  useContext: () => null,
  useEffect: noop,
  useMemo: (factory) => factory(),
  useState: (initial) => [typeof initial === 'function' ? initial() : initial, noop],
}
