// Builds src/lib/world-dots.json: a dot-matrix world map tagged by country.
// Run once with `node scripts/build-world-dots.mjs` (Natural Earth 1:50m via world-atlas).
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { geoBounds, geoCentroid, geoContains } from "d3-geo";
import { feature } from "topojson-client";

const require = createRequire(import.meta.url);
const topology = JSON.parse(readFileSync(require.resolve("world-atlas/countries-50m.json"), "utf8"));
const countries = feature(topology, topology.objects.countries).features.filter((country) => country.properties.name !== "Antarctica");

const STEP = 1.2;
const names = countries.map((country) => country.properties.name);
const boxes = countries.map((country) => geoBounds(country));
const dots = [];
const counts = new Array(countries.length).fill(0);

const inBox = ([[west, south], [east, north]], lon, lat) =>
  lat >= south && lat <= north && (west <= east ? lon >= west && lon <= east : lon >= west || lon <= east);

for (let lat = 84 - STEP / 2; lat > -58; lat -= STEP) {
  for (let lon = -180 + STEP / 2; lon < 180; lon += STEP) {
    for (let index = 0; index < countries.length; index += 1) {
      if (!inBox(boxes[index], lon, lat)) continue;
      if (geoContains(countries[index], [lon, lat])) {
        dots.push(Math.round(lon * 100) / 100, Math.round(lat * 100) / 100, index);
        counts[index] += 1;
        break;
      }
    }
  }
}

// Small states (Bahrain, Qatar, Lebanon…) can fall between grid points: give them one dot.
countries.forEach((country, index) => {
  if (counts[index] === 0) {
    const [lon, lat] = geoCentroid(country);
    dots.push(Math.round(lon * 100) / 100, Math.round(lat * 100) / 100, index);
  }
});

writeFileSync(new URL("../src/lib/world-dots.json", import.meta.url), JSON.stringify({ step: STEP, names, dots }));
console.log(`${dots.length / 3} dots across ${names.length} countries`);
