// Main gateway airport city (approximate) for each API country key. Used only
// to draw routes on the map; no model input uses them.
export const ABU_DHABI: [number, number] = [24.45, 54.38];

export const COUNTRY_COORDINATES: Record<string, [number, number]> = {
  ARMENIA: [40.18, 44.51],
  AUSTRALIA: [-33.87, 151.21],
  AUSTRIA: [48.21, 16.37],
  AZERBAIJAN: [40.41, 49.87],
  BAHRAIN: [26.23, 50.59],
  BELGIUM: [50.85, 4.35],
  BRAZIL: [-23.55, -46.63],
  CANADA: [43.65, -79.38],
  CHINA: [39.9, 116.4],
  CZECHIA: [50.08, 14.44],
  DENMARK: [55.68, 12.57],
  EGYPT: [30.04, 31.24],
  FINLAND: [60.17, 24.94],
  FRANCE: [48.86, 2.35],
  GERMANY: [50.11, 8.68],
  INDIA: [28.61, 77.21],
  IRELAND: [53.35, -6.26],
  ISRAEL: [32.09, 34.78],
  ITALY: [41.9, 12.5],
  JAPAN: [35.68, 139.69],
  JORDAN: [31.95, 35.93],
  KAZAKHSTAN: [43.24, 76.89],
  KUWAIT: [29.38, 47.99],
  LEBANON: [33.89, 35.5],
  MEXICO: [19.43, -99.13],
  MOROCCO: [33.57, -7.59],
  NETHERLANDS: [52.37, 4.9],
  NORWAY: [59.91, 10.75],
  OMAN: [23.59, 58.41],
  PAKISTAN: [24.86, 67.01],
  PHILIPPINES: [14.6, 120.98],
  POLAND: [52.23, 21.01],
  QATAR: [25.29, 51.53],
  ROMANIA: [44.43, 26.1],
  "RUSSIAN FEDERATION": [55.76, 37.62],
  "SAUDI ARABIA": [24.71, 46.68],
  "SOUTH AFRICA": [-26.2, 28.05],
  "SOUTH KOREA": [37.57, 126.98],
  SPAIN: [40.42, -3.7],
  SWEDEN: [59.33, 18.07],
  SWITZERLAND: [47.38, 8.54],
  TURKEY: [41.01, 28.98],
  "UNITED KINGDOM": [51.51, -0.13],
  "UNITED STATES OF AMERICA": [40.71, -74.01],
  UZBEKISTAN: [41.3, 69.24],
};

/** Natural Earth (world-atlas) country name for an API country key. */
export function atlasName(key: string) {
  if (key === "UNITED STATES OF AMERICA") return "United States of America";
  if (key === "RUSSIAN FEDERATION") return "Russia";
  return key.toLowerCase().replace(/\b\p{L}/gu, (letter) => letter.toUpperCase());
}
