"use client";

import { useEffect, useRef } from "react";
import { geoDistance, geoInterpolate, geoNaturalEarth1, type GeoProjection } from "d3-geo";

import { PLANE_PATH } from "@/components/logo";
import { countryName, formatDecimal } from "@/lib/format";
import { ABU_DHABI, COUNTRY_COORDINATES, atlasName } from "@/lib/geo";

/**
 * Scenario flow for the selected route, taken from the API response. Weekly
 * flights set how often aircraft depart; the conversion shares decide what the
 * arriving passengers become, so the animation stays proportional to the data.
 */
export type MapFlow = {
  weeklyFlights: number;
  passengers: number;
  destination: number;
  hotel: number;
};

type Props = {
  variant: "hero" | "card";
  origins: string[];
  weeklyFlights?: Record<string, number>;
  selected: string | null;
  flow: MapFlow | null;
  className?: string;
};

type WorldDots = { step: number; names: string[]; dots: number[] };

type Route = {
  key: string;
  coordinates: [number, number];
  distance: number;
  samples: Array<[number, number]>;
  screen: Array<[number, number]>;
  weekly: number;
};

type Plane = { key: string; t: number; duration: number; ambient: boolean };
type Pulse = { age: number };
type Guest = { angle: number; age: number; kind: "hotel" | "other" | "onward"; speed: number };
type View = { k: number; x: number; y: number };

const AUH: [number, number] = [ABU_DHABI[1], ABU_DHABI[0]];
const GOLD = "232,190,120";
const WHITE = "245,242,236";
const SAMPLES = 96;

let worldPromise: Promise<WorldDots> | null = null;
function loadWorld() {
  worldPromise ??= import("@/lib/world-dots.json").then((module) => (module.default ?? module) as WorldDots);
  return worldPromise;
}

function lonLat(key: string): [number, number] | null {
  const coordinates = COUNTRY_COORDINATES[key];
  return coordinates ? [coordinates[1], coordinates[0]] : null;
}

function fonts() {
  const root = getComputedStyle(document.documentElement);
  const sans = root.getPropertyValue("--font-geist-sans").trim() || "system-ui, sans-serif";
  const arabic = root.getPropertyValue("--font-arabic").trim() || "sans-serif";
  return { sans, arabic };
}

export function FlightMap({ variant, origins, weeklyFlights, selected, flow, className }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const propsRef = useRef({ variant, origins, weeklyFlights, selected, flow });
  const versionRef = useRef(0);

  useEffect(() => {
    propsRef.current = { variant, origins, weeklyFlights, selected, flow };
    versionRef.current += 1;
  }, [variant, origins, weeklyFlights, selected, flow]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    const ctx: CanvasRenderingContext2D = context;
    const staticLayer = document.createElement("canvas");
    const staticCtx = staticLayer.getContext("2d")!;
    const plane = new Path2D(PLANE_PATH);
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const { sans, arabic } = fonts();

    let world: WorldDots | null = null;
    let width = 0;
    let height = 0;
    let dpr = 1;
    let routes: Route[] = [];
    let byKey = new Map<string, Route>();
    let selectedIndex = -1;
    let seenVersion = -1;
    let view: View | null = null;
    let target: View = { k: 1, x: 0, y: 0 };
    let staticDirty = true;
    let planes: Plane[] = [];
    let pulses: Pulse[] = [];
    let guests: Guest[] = [];
    let spawnDebt = 0;
    let ambientDebt = 0;
    let frame = 0;
    let last = performance.now();
    let visible = true;
    let disposed = false;
    const projection: GeoProjection = geoNaturalEarth1().rotate([-AUH[0], 0]).precision(0.3);

    const applyView = (current: View) => {
      projection.scale(current.k).translate([0, 0]);
      const origin = projection(AUH)!;
      projection.translate([current.x - origin[0], current.y - origin[1]]);
    };

    /** Fits the selected great circle into a screen rectangle, capped at maxK. */
    const fitRoute = (left: number, top: number, right: number, bottom: number, minK: number, maxK: number): View | null => {
      const route = routes[selectedIndex];
      if (!route) return null;
      projection.scale(1).translate([0, 0]);
      const points = route.samples.map((point) => projection(point)!);
      const xs = points.map((point) => point[0]);
      const ys = points.map((point) => point[1]);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);
      const k = Math.min(maxK, Math.max(minK, Math.min((right - left) / Math.max(maxX - minX, 1e-3), (bottom - top) / Math.max(maxY - minY, 1e-3))));
      const auh = projection(AUH)!;
      return {
        k,
        x: (left + right) / 2 + (auh[0] - (minX + maxX) / 2) * k,
        y: (top + bottom) / 2 + (auh[1] - (minY + maxY) / 2) * k,
      };
    };

    const computeTarget = (): View => {
      const { variant: kind } = propsRef.current;
      if (kind === "hero") {
        const desktop = window.innerWidth >= 1024;
        let preferred = { k: width / 2.3, x: width * 0.5, y: height * 0.55 };
        if (desktop) {
          // Size to the taller of width or height, then lift the map so the Arctic meets the top edge.
          const k = Math.max(width / 4.4, height / 2.2);
          projection.scale(k).translate([0, 0]);
          const auh = projection(AUH)!;
          const north = projection([AUH[0], 80])!;
          preferred = { k, x: width * 0.64, y: Math.max(height * 0.42, 40 + (auh[1] - north[1])) };
        }
        // Keep the whole selected route clear of the headline column; zoom out only when needed.
        // Leave room on the right for the Abu Dhabi label.
        const area = desktop ? [width * 0.47, height * 0.14, width - 110, height * 0.74] : [36, 40, width - 48, height - 48];
        const route = routes[selectedIndex];
        if (!route) return preferred;
        applyView(preferred);
        const outside = route.samples.some((point) => {
          const [x, y] = projection(point)!;
          return x < area[0] || x > area[2] || y < area[1] || y > area[3];
        });
        if (!outside) return preferred;
        return fitRoute(area[0], area[1], area[2], area[3], width / 9, preferred.k) ?? preferred;
      }
      // Card: frame Abu Dhabi and the selected origin along the real great circle.
      const pad = 34;
      return fitRoute(pad, pad, width - pad, height - pad - 18, width / 5.2, width * 1.4) ?? { k: width / 1.6, x: width / 2, y: height / 2 };
    };

    const rebuildRoutes = () => {
      const { origins: list, selected: active, weeklyFlights: weekly, flow: current } = propsRef.current;
      const keys = active && !list.includes(active) ? [...list, active] : [...list];
      routes = keys.flatMap((key) => {
        const coordinates = lonLat(key);
        if (!coordinates) return [];
        const interpolate = geoInterpolate(coordinates, AUH);
        const samples = Array.from({ length: SAMPLES }, (_, index) => interpolate(index / (SAMPLES - 1)) as [number, number]);
        const isActive = key === active;
        return [{
          key,
          coordinates,
          distance: geoDistance(coordinates, AUH) * 6371,
          samples,
          screen: [],
          weekly: isActive && current ? current.weeklyFlights : (weekly?.[key] ?? 1),
        }];
      });
      selectedIndex = routes.findIndex((route) => route.key === active);
      byKey = new Map(routes.map((route) => [route.key, route]));
      // Keep aircraft already in the air when only the numbers change.
      planes = planes.filter((item) => byKey.has(item.key) && (item.ambient ? item.key !== active : item.key === active));
    };

    const projectRoutes = () => {
      for (const route of routes) route.screen = route.samples.map((point) => projection(point) as [number, number]);
    };

    const drawStatic = () => {
      staticLayer.width = canvas.width;
      staticLayer.height = canvas.height;
      const g = staticCtx;
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      g.clearRect(0, 0, width, height);
      const { selected: active, variant: kind } = propsRef.current;
      const servedNames = new Set(propsRef.current.origins.map(atlasName));
      const text = (value: string, x: number, y: number, color: string) => {
        g.lineJoin = "round";
        g.lineWidth = 4;
        g.strokeStyle = "rgba(7,7,8,0.9)";
        g.strokeText(value, x, y);
        g.fillStyle = color;
        g.fillText(value, x, y);
      };
      const activeName = active ? atlasName(active) : "";

      if (world) {
        const spacing = (world.step * Math.PI / 180) * projection.scale() * 0.87;
        const r = Math.min(2.4, Math.max(0.75, spacing * 0.24));
        // Dots fade towards the poles and the canvas edges so the map never ends in a hard line.
        const LEVELS = 6;
        const smooth = (value: number) => {
          const clamped = Math.min(1, Math.max(0, value));
          return clamped * clamped * (3 - 2 * clamped);
        };
        const edge = kind === "hero" ? { top: height * 0.2, side: 80, bottom: 0 } : { top: 26, side: 26, bottom: 26 };
        const buckets = new Map<string, number[]>();
        for (let index = 0; index < world.dots.length; index += 3) {
          const lat = world.dots[index + 1];
          const point = projection([world.dots[index], lat]);
          if (!point || point[0] < -4 || point[1] < -4 || point[0] > width + 4 || point[1] > height + 4) continue;
          const latFade = lat > 62 ? 1 - smooth((lat - 62) / 22) * 0.9 : lat < -44 ? 1 - smooth((-44 - lat) / 14) * 0.9 : 1;
          const edgeFade = Math.min(
            smooth(point[1] / edge.top),
            edge.bottom ? smooth((height - point[1]) / edge.bottom) : 1,
            smooth((width - point[0]) / edge.side),
            kind === "hero" ? 1 : smooth(point[0] / edge.side),
          );
          const level = Math.round(latFade * edgeFade * LEVELS);
          if (level <= 0) continue;
          const name = world.names[world.dots[index + 2]];
          const bucket = name === "United Arab Emirates" ? "uae" : name === activeName ? "active" : servedNames.has(name) ? "served" : "base";
          const key = `${bucket}:${level}`;
          let list = buckets.get(key);
          if (!list) buckets.set(key, (list = []));
          list.push(point[0], point[1]);
        }
        const styles: Record<string, { color: string; alpha: number; radius: number }> = {
          base: { color: WHITE, alpha: 0.11, radius: r },
          served: { color: WHITE, alpha: 0.2, radius: r },
          active: { color: GOLD, alpha: 0.72, radius: r * 1.05 },
          uae: { color: GOLD, alpha: 0.95, radius: r * 1.1 },
        };
        for (const bucket of ["base", "served", "active", "uae"]) {
          const style = styles[bucket];
          for (let level = 1; level <= LEVELS; level += 1) {
            const list = buckets.get(`${bucket}:${level}`);
            if (!list) continue;
            g.fillStyle = `rgba(${style.color},${(style.alpha * level) / LEVELS})`;
            g.beginPath();
            for (let index = 0; index < list.length; index += 2) {
              g.moveTo(list[index] + style.radius, list[index + 1]);
              g.arc(list[index], list[index + 1], style.radius, 0, Math.PI * 2);
            }
            g.fill();
          }
        }
      }

      // Other routes: faint great circles.
      g.lineWidth = 1;
      routes.forEach((route, index) => {
        if (index === selectedIndex || !route.screen.length) return;
        g.strokeStyle = `rgba(${WHITE},${kind === "hero" ? 0.07 : 0.05})`;
        g.beginPath();
        route.screen.forEach(([x, y], point) => (point ? g.lineTo(x, y) : g.moveTo(x, y)));
        g.stroke();
        const [ox, oy] = route.screen[0];
        g.fillStyle = `rgba(${WHITE},0.32)`;
        g.beginPath();
        g.arc(ox, oy, 1.6, 0, Math.PI * 2);
        g.fill();
      });

      // Selected route with a soft glow.
      const route = routes[selectedIndex];
      if (route?.screen.length) {
        const [sx, sy] = route.screen[0];
        const [ex, ey] = route.screen[route.screen.length - 1];
        const gradient = g.createLinearGradient(sx, sy, ex, ey);
        gradient.addColorStop(0, `rgba(${GOLD},0.35)`);
        gradient.addColorStop(1, `rgba(${GOLD},0.9)`);
        g.save();
        g.shadowColor = `rgba(${GOLD},0.6)`;
        g.shadowBlur = 8;
        g.strokeStyle = gradient;
        g.lineWidth = 1.5;
        g.setLineDash([]);
        g.beginPath();
        route.screen.forEach(([x, y], point) => (point ? g.lineTo(x, y) : g.moveTo(x, y)));
        g.stroke();
        g.restore();

        g.fillStyle = "#0b0b0d";
        g.strokeStyle = `rgb(${GOLD})`;
        g.lineWidth = 1.5;
        g.beginPath();
        g.arc(sx, sy, 4, 0, Math.PI * 2);
        g.fill();
        g.stroke();

        const label = countryName(route.key);
        const detail = `${formatDecimal(route.weekly)} flights a week`;
        g.font = `500 ${kind === "hero" ? 13 : 12}px ${sans}`;
        const right = sx < width - 140;
        g.textAlign = right ? "left" : "right";
        const lx = sx + (right ? 10 : -10);
        const ly = Math.max(16, sy - (kind === "hero" ? 12 : 8));
        text(label, lx, ly, `rgba(${WHITE},0.95)`);
        if (kind === "hero") {
          g.font = `12px ${sans}`;
          text(detail, lx, ly + 16, `rgba(${WHITE},0.6)`);
        }
      }

      // Abu Dhabi marker: eight-point star.
      const [ax, ay] = projection(AUH)!;
      const glow = g.createRadialGradient(ax, ay, 0, ax, ay, 40);
      glow.addColorStop(0, `rgba(${GOLD},0.28)`);
      glow.addColorStop(1, `rgba(${GOLD},0)`);
      g.fillStyle = glow;
      g.beginPath();
      g.arc(ax, ay, 40, 0, Math.PI * 2);
      g.fill();
      const star = (size: number) => {
        g.beginPath();
        for (let square = 0; square < 2; square += 1) {
          for (let corner = 0; corner <= 4; corner += 1) {
            const angle = square * Math.PI / 4 + corner * Math.PI / 2 + Math.PI / 4;
            const px = ax + Math.cos(angle) * size;
            const py = ay + Math.sin(angle) * size;
            if (corner === 0) g.moveTo(px, py);
            else g.lineTo(px, py);
          }
        }
      };
      star(7);
      g.fillStyle = "#0b0b0d";
      g.fill();
      star(7);
      g.strokeStyle = `rgb(${GOLD})`;
      g.lineWidth = 1.3;
      g.stroke();
      g.textAlign = "center";
      g.font = `600 12px ${sans}`;
      text("Abu Dhabi", ax, ay + 25, `rgba(${WHITE},0.95)`);
      g.font = `12px ${arabic}`;
      text("أبوظبي", ax, ay + 42, `rgba(${GOLD},0.9)`);
      g.textAlign = "left";
      staticDirty = false;
    };

    const positionOn = (route: Route, t: number) => {
      const exact = Math.min(1, Math.max(0, t)) * (route.screen.length - 1);
      const index = Math.min(route.screen.length - 2, Math.floor(exact));
      const fraction = exact - index;
      const [x1, y1] = route.screen[index];
      const [x2, y2] = route.screen[index + 1];
      return { x: x1 + (x2 - x1) * fraction, y: y1 + (y2 - y1) * fraction, heading: Math.atan2(x2 - x1, -(y2 - y1)) };
    };

    const duration = (route: Route) => 1.8 + route.distance / 2600;

    const land = () => {
      pulses.push({ age: 0 });
      const current = propsRef.current.flow;
      if (!current || current.passengers <= 0) return;
      const onward = Math.max(0, 1 - current.destination / current.passengers);
      const hotel = Math.max(0, current.hotel / current.passengers);
      for (let index = 0; index < 6; index += 1) {
        const roll = Math.random();
        guests.push({
          angle: Math.random() * Math.PI * 2,
          age: 0,
          kind: roll < onward ? "onward" : roll < onward + hotel ? "hotel" : "other",
          speed: 10 + Math.random() * 14,
        });
      }
    };

    const drawPlane = (x: number, y: number, heading: number, size: number, alpha: number, glow: boolean) => {
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(heading);
      ctx.scale(size / 24, size / 24);
      ctx.translate(-11.5, -12);
      if (glow) {
        ctx.shadowColor = `rgba(${GOLD},0.8)`;
        ctx.shadowBlur = 10;
      }
      ctx.fillStyle = `rgba(${WHITE},${alpha})`;
      ctx.fill(plane);
      ctx.restore();
    };

    const render = (dt: number) => {
      if (versionRef.current !== seenVersion) {
        seenVersion = versionRef.current;
        rebuildRoutes();
        target = computeTarget();
        if (!view) view = { ...target };
        staticDirty = true;
      }
      if (!view) return;
      const ease = reducedMotion ? 1 : 1 - Math.exp(-dt * 4.5);
      const moving = Math.abs(view.k - target.k) / target.k > 0.002 || Math.abs(view.x - target.x) > 0.5 || Math.abs(view.y - target.y) > 0.5;
      if (moving) {
        view = { k: view.k + (target.k - view.k) * ease, x: view.x + (target.x - view.x) * ease, y: view.y + (target.y - view.y) * ease };
        staticDirty = true;
      }
      if (staticDirty) {
        applyView(view);
        projectRoutes();
        drawStatic();
      }

      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(staticLayer, 0, 0);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const { variant: kind } = propsRef.current;
      const active = routes[selectedIndex];

      if (!reducedMotion && dt > 0) {
        if (active && active.weekly > 0) {
          // Departure rate grows with weekly flights (square-root keeps busy routes readable).
          spawnDebt += Math.min(3, Math.max(0.2, Math.sqrt(active.weekly) * 0.2)) * dt;
          while (spawnDebt >= 1) {
            planes.push({ key: active.key, t: 0, duration: duration(active), ambient: false });
            spawnDebt -= 1;
          }
        }
        if (kind === "hero" && routes.length > 1) {
          const others = routes.map((route, index) => (index === selectedIndex ? 0 : Math.sqrt(Math.max(0, route.weekly))));
          const total = others.reduce((sum, value) => sum + value, 0);
          ambientDebt += total * 0.022 * dt;
          while (ambientDebt >= 1 && total > 0) {
            let roll = Math.random() * total;
            const chosen = others.findIndex((value) => (roll -= value) <= 0);
            if (chosen >= 0) planes.push({ key: routes[chosen].key, t: 0, duration: duration(routes[chosen]) * 1.15, ambient: true });
            ambientDebt -= 1;
          }
        }
      }

      const survivors: Plane[] = [];
      for (const item of planes) {
        const route = byKey.get(item.key);
        if (!route?.screen.length) continue;
        if (!reducedMotion) item.t += dt / item.duration;
        if (item.t >= 1) {
          if (!item.ambient) land();
          continue;
        }
        const { x, y, heading } = positionOn(route, item.t);
        if (!item.ambient) {
          // Fading trail behind the aircraft.
          const tail = Math.max(0, item.t - 0.16);
          const steps = 10;
          for (let step = 0; step < steps; step += 1) {
            const a = positionOn(route, tail + ((item.t - tail) * step) / steps);
            const b = positionOn(route, tail + ((item.t - tail) * (step + 1)) / steps);
            ctx.strokeStyle = `rgba(${GOLD},${(step / steps) * 0.55})`;
            ctx.lineWidth = 1.6;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
        const fade = Math.min(1, item.t * 10, (1 - item.t) * 12);
        drawPlane(x, y, heading, item.ambient ? 9 : kind === "hero" ? 15 : 13, item.ambient ? 0.32 * fade : fade, !item.ambient);
        survivors.push(item);
      }
      planes = survivors;

      const [ax, ay] = projection(AUH)!;
      pulses = pulses.filter((pulse) => {
        pulse.age += dt;
        if (pulse.age > 1.4) return false;
        ctx.strokeStyle = `rgba(${GOLD},${0.5 * (1 - pulse.age / 1.4)})`;
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.arc(ax, ay, 8 + pulse.age * 26, 0, Math.PI * 2);
        ctx.stroke();
        return true;
      });
      guests = guests.filter((guest) => {
        guest.age += dt;
        const life = guest.kind === "onward" ? 1.6 : 1.3;
        if (guest.age > life) return false;
        const distance = 9 + guest.age * guest.speed * (guest.kind === "onward" ? 2.4 : 1);
        const color = guest.kind === "hotel" ? GOLD : guest.kind === "onward" ? "150,156,166" : WHITE;
        ctx.fillStyle = `rgba(${color},${0.9 * (1 - guest.age / life)})`;
        ctx.beginPath();
        ctx.arc(ax + Math.cos(guest.angle) * distance, ay + Math.sin(guest.angle) * distance, guest.kind === "hotel" ? 1.8 : 1.3, 0, Math.PI * 2);
        ctx.fill();
        return true;
      });
    };

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = rect.width;
      height = rect.height;
      canvas.width = Math.max(1, Math.round(width * dpr));
      canvas.height = Math.max(1, Math.round(height * dpr));
      target = computeTarget();
      view = { ...target };
      staticDirty = true;
    };

    const loop = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      if (visible && width > 0) render(dt);
      frame = requestAnimationFrame(loop);
    };

    resize();
    loadWorld().then((data) => {
      if (disposed) return;
      world = data;
      staticDirty = true;
      if (reducedMotion) render(0);
    });
    const observer = new ResizeObserver(() => {
      resize();
      if (reducedMotion) render(0);
    });
    observer.observe(canvas);
    const intersection = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      last = performance.now();
    });
    intersection.observe(canvas);

    let redraw = 0;
    if (reducedMotion) redraw = window.setInterval(() => render(0), 500);
    else frame = requestAnimationFrame(loop);
    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      window.clearInterval(redraw);
      observer.disconnect();
      intersection.disconnect();
    };
  }, []);

  return <canvas ref={canvasRef} className={className} aria-hidden="true" />;
}
