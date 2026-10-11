const NAME_OVERRIDES: Record<string, string> = {
  "UNITED STATES OF AMERICA": "United States",
  "RUSSIAN FEDERATION": "Russia",
  "UNITED KINGDOM": "United Kingdom",
  "SOUTH KOREA": "South Korea",
  "SOUTH AFRICA": "South Africa",
  "SAUDI ARABIA": "Saudi Arabia",
};

/** API country keys are upper case; show them as normal names. */
export function countryName(key: string | undefined | null) {
  if (!key) return "";
  if (NAME_OVERRIDES[key]) return NAME_OVERRIDES[key];
  return key.toLowerCase().replace(/\b\p{L}/gu, (letter) => letter.toUpperCase());
}

const integer = new Intl.NumberFormat("en", { maximumFractionDigits: 0 });
const compactFormat = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });
const oneDecimal = new Intl.NumberFormat("en", { maximumFractionDigits: 1 });

export const formatInt = (value: number) => integer.format(Math.round(value));
export const formatCompact = (value: number) => compactFormat.format(value);
export const formatDecimal = (value: number) => oneDecimal.format(value);

export function signed(value: number, formatter: (value: number) => string = formatInt) {
  const rounded = Math.round(value);
  if (rounded === 0) return formatter(0);
  return `${rounded > 0 ? "+" : "−"}${formatter(Math.abs(value))}`;
}

export function signedCompact(value: number) {
  return signed(value, formatCompact);
}

export function percent(value: number, digits = 0) {
  return `${(value * 100).toFixed(digits)}%`;
}

export function signedPercent(value: number, digits = 1) {
  const fixed = (value * 100).toFixed(digits);
  if (Number(fixed) === 0) return `${(0).toFixed(digits)}%`;
  return `${value > 0 ? "+" : "−"}${Math.abs(Number(fixed)).toFixed(digits)}%`;
}

const dateFormat = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const monthFormat = new Intl.DateTimeFormat("en-GB", { month: "short", year: "2-digit", timeZone: "UTC" });

export function formatDate(iso: string) {
  return dateFormat.format(new Date(`${iso}T00:00:00Z`));
}

export function formatDateRange(start: string, end: string) {
  return `${formatDate(start)} – ${formatDate(end)}`;
}

/** "2025-08" → "Aug 25" */
export function formatMonth(period: string) {
  return monthFormat.format(new Date(`${period}-01T00:00:00Z`));
}
