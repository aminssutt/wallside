/** Formatting helpers and the chart palette (validated slot order, dark-surface steps). */
export const SERIES = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#5cc27a']

export const pct = (value, digits = 1) =>
  value == null ? '–' : `${(100 * value).toFixed(digits)}%`

export const pctNum = (value, digits = 1) =>
  value == null ? '–' : (100 * value).toFixed(digits)

export const dec = (value, digits = 2) =>
  value == null ? '–' : Number(value).toFixed(digits)

export const intEn = (value) => Number(value).toLocaleString('en-US')
