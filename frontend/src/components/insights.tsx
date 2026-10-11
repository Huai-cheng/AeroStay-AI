"use client";

import { useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import { Loader2 } from "lucide-react";

import { AnimatedNumber, Card } from "@/components/ui";
import {
  countryName,
  formatCompact,
  formatDateRange,
  formatDecimal,
  formatInt,
  formatMonth,
  percent,
  signed,
  signedCompact,
  signedPercent,
} from "@/lib/format";
import type { GlobalSensitivityPayload, SensitivityPayload, SimulationPayload } from "@/lib/types";

export function marketLift(result: SimulationPayload) {
  return result.selected_market_scenario_nights - result.selected_market_baseline_nights;
}

/** One sentence describing the supply change exactly as the API applied it. */
export function describeChange(result: SimulationPayload) {
  const origin = countryName(result.origin_country);
  if (result.mode === "New route") {
    return `New route: ${formatDecimal(result.new_route_weekly_flights)} weekly flights from ${origin}, ${formatInt(result.new_route_seats_per_flight)} seats each, ${percent(result.new_route_load_factor)} full`;
  }
  const parts: string[] = [];
  const flightDelta = result.scenario_weekly_flights - result.baseline_weekly_flights;
  if (Math.abs(flightDelta) >= 0.05) {
    parts.push(`${flightDelta > 0 ? "+" : "−"}${formatDecimal(Math.abs(flightDelta))} weekly flights from ${origin} (${formatDecimal(result.baseline_weekly_flights)} → ${formatDecimal(result.scenario_weekly_flights)})`);
  }
  if (result.seats_per_flight_change_pct) parts.push(`${result.seats_per_flight_change_pct > 0 ? "+" : "−"}${Math.abs(result.seats_per_flight_change_pct)}% seats per flight`);
  if (result.load_factor_change_points) parts.push(`load factor ${result.load_factor_change_points > 0 ? "+" : "−"}${Math.abs(result.load_factor_change_points)} pts`);
  if (!parts.length) return `Today's schedule from ${origin} (${formatDecimal(result.baseline_weekly_flights)} weekly flights)`;
  return parts.join(" · ");
}

function monthlyDiff(result: SimulationPayload) {
  return result.monthly.map((row) => ({ month: row.month, diff: row.scenario - row.baseline, baseline: row.baseline, scenario: row.scenario }));
}

export function takeaway(result: SimulationPayload, sensitivity: SensitivityPayload | null) {
  const lift = marketLift(result);
  const market = countryName(result.target_nationality);
  const months = monthlyDiff(result);
  const range = formatDateRange(result.start_date, result.end_date);
  if (Math.abs(lift) < 1) {
    return `This change leaves ${market} guest nights essentially unchanged for ${range}.`;
  }
  const peak = months.reduce((best, row) => (Math.abs(row.diff) > Math.abs(best.diff) ? row : best), months[0]);
  const direction = lift > 0 ? "more" : "fewer";
  let sentence = `Plan for about ${formatCompact(Math.abs(lift))} ${direction} guest nights from ${market} guests over ${range}`;
  sentence += peak && months.length > 1 ? `, with the largest effect in ${formatMonth(peak.month)}.` : ".";
  const top = sensitivity?.drivers[0];
  if (top) sentence += ` The answer is most sensitive to ${top.driver.toLowerCase()}, so validate that first.`;
  return sentence;
}

export function HeroResult({ result }: { result: SimulationPayload }) {
  const lift = marketLift(result);
  const share = result.selected_market_baseline_nights > 0 ? lift / result.selected_market_baseline_nights : 0;
  return (
    <div className="hero-result">
      <p className="hero-label">Change in hotel guest nights from {countryName(result.target_nationality)} guests</p>
      <div className={`hero-number ${lift < -0.5 ? "negative" : ""}`}>
        <AnimatedNumber value={lift} format={(value) => signed(value)} />
      </div>
      <p className="hero-sub">
        <AnimatedNumber value={share} format={(value) => signedPercent(value)} /> vs. {formatInt(result.selected_market_baseline_nights)} expected without the change
      </p>
      <p className="hero-change">{describeChange(result)} · {formatDateRange(result.start_date, result.end_date)}</p>
    </div>
  );
}

export function HeroStats({ result }: { result: SimulationPayload }) {
  const cityLift = result.scenario_guest_nights - result.baseline_guest_nights;
  const wmape = result.metrics?.combined?.wmape;
  return (
    <dl className="hero-stats">
      <div>
        <dt>All Abu Dhabi hotels</dt>
        <dd className="tabular">{formatCompact(result.scenario_guest_nights)} <span>{signedCompact(cityLift)} nights</span></dd>
      </div>
      <div>
        <dt>Planning range, all hotels</dt>
        <dd className="tabular">{formatCompact(result.planning_range_low)} – {formatCompact(result.planning_range_high)}</dd>
      </div>
      <div>
        <dt>Back-tested error</dt>
        <dd className="tabular">{wmape === undefined ? "—" : percent(wmape, 1)} <span>WMAPE</span></dd>
      </div>
    </dl>
  );
}

const STAGES = [
  { label: "Seats", note: "Flight schedule" },
  { label: "Passengers", note: "Seats × load factor" },
  { label: "Arriving in Abu Dhabi", note: "Minus transfer and transit" },
  { label: "Visitors", note: "× visitor share (assumption)" },
  { label: "Hotel guests", note: "× hotel capture (assumption)" },
];

export function ConversionFunnel({ result }: { result: SimulationPayload }) {
  const stages = result.chain.slice(0, 5);
  const top = Math.max(1, stages[0]?.scenario ?? 1);
  const assigned = result.allocated_arrival_delta;
  const modelled = result.chain[5];
  return (
    <Card title="How flights become hotel guests" subtitle={`${countryName(result.origin_country)} route totals for the period, change vs. today`}>
      <ol className="funnel">
        {stages.map((stage, index) => (
          <li key={stage.stage}>
            <div className="funnel-row">
              <span className="funnel-name">{STAGES[index]?.label ?? stage.stage} <small>{STAGES[index]?.note ?? stage.source}</small></span>
              <span className="funnel-value tabular"><AnimatedNumber value={stage.scenario} format={formatInt} /></span>
            </div>
            <div className="funnel-track">
              <div className="funnel-bar"><i style={{ width: `${Math.max(1.5, (stage.scenario / top) * 100)}%` }} /></div>
              <span className={`tabular ${stage.change < -0.5 ? "neg" : stage.change > 0.5 ? "pos" : ""}`}>{signed(stage.change)}</span>
            </div>
          </li>
        ))}
      </ol>
      <div className="funnel-result">
        <div>
          <span>Extra hotel arrivals assigned to {countryName(result.target_nationality)} ({percent(result.nationality_allocation_share)})</span>
          <b className="tabular">{signed(assigned)} arrivals</b>
        </div>
        <div>
          <span>Guest-night change (model)</span>
          <b className="tabular gold">{modelled ? signed(modelled.change) : "—"}</b>
        </div>
      </div>
    </Card>
  );
}

export function MonthlyImpact({ result }: { result: SimulationPayload }) {
  const rows = useMemo(() => monthlyDiff(result), [result]);
  const option = useMemo(() => ({
    backgroundColor: "transparent",
    animationDuration: 500,
    animationDurationUpdate: 450,
    grid: { left: 4, right: 8, top: 12, bottom: 4, containLabel: true },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow", shadowStyle: { color: "rgba(255,255,255,0.04)" } },
      backgroundColor: "#151517",
      borderColor: "rgba(255,255,255,0.1)",
      textStyle: { color: "#f5f2ec", fontSize: 12 },
      formatter: (items: Array<{ dataIndex: number }>) => {
        const row = rows[items[0]?.dataIndex ?? 0];
        if (!row) return "";
        return `<b>${formatMonth(row.month)}</b><br/>Change: ${signed(row.diff)} guest nights<br/><span style="color:#9a9a9f">All hotels: ${formatInt(row.baseline)} → ${formatInt(row.scenario)}</span>`;
      },
    },
    xAxis: {
      type: "category",
      data: rows.map((row) => formatMonth(row.month)),
      axisLine: { lineStyle: { color: "rgba(255,255,255,0.12)" } },
      axisTick: { show: false },
      axisLabel: { color: "#8b8b90", fontSize: 11 },
    },
    yAxis: {
      type: "value",
      splitNumber: 3,
      axisLabel: { color: "#6f6f75", fontSize: 11, formatter: (value: number) => formatCompact(value) },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
    },
    series: [{
      type: "bar",
      barMaxWidth: 28,
      data: rows.map((row) => ({
        value: Math.round(row.diff),
        itemStyle: { color: row.diff >= 0 ? "#e8be78" : "#e0786b", borderRadius: row.diff >= 0 ? [4, 4, 0, 0] : [0, 0, 4, 4] },
      })),
    }],
  }), [rows]);
  return (
    <Card title="When the change lands" subtitle="Guest-night change by month, all hotels">
      <div className="chart-box">
        <ReactECharts option={option} style={{ height: "100%", width: "100%" }} notMerge={false} lazyUpdate opts={{ renderer: "canvas" }} />
      </div>
    </Card>
  );
}

export function Drivers({ sensitivity, loading, global, globalLoading, onRunGlobal }: {
  sensitivity: SensitivityPayload | null;
  loading: boolean;
  global: GlobalSensitivityPayload | null;
  globalLoading: boolean;
  onRunGlobal: () => void;
}) {
  const [view, setView] = useState<"quick" | "full">("quick");
  const maxShare = Math.max(0.0001, ...(global?.drivers.map((driver) => driver.relative_importance) ?? [1]));
  const maxSwing = Math.max(1, ...(sensitivity?.drivers.map((driver) => Math.max(Math.abs(driver.downside), Math.abs(driver.upside))) ?? [1]));
  return (
    <Card
      title="What moves it most"
      subtitle={view === "quick" ? "Change one input at a time, rerun the model" : "Vary every input together (Morris method)"}
      action={
        <div className="tabs" role="tablist" aria-label="Sensitivity view">
          <button role="tab" aria-selected={view === "quick"} onClick={() => setView("quick")}>Quick</button>
          <button role="tab" aria-selected={view === "full"} onClick={() => setView("full")}>Full</button>
        </div>
      }
    >
      {view === "quick" ? (
        <div className={`drivers ${loading ? "is-loading" : ""}`}>
          {!sensitivity && <p className="placeholder">{loading ? "Testing each input…" : "Sensitivity is unavailable for this scenario."}</p>}
          {sensitivity?.drivers.map((driver) => (
            <div className="driver" key={driver.driver}>
              <div className="driver-head">
                <span>{driver.driver}</span>
                <small>{driver.perturbation.replace("percentage points", "pts")}</small>
              </div>
              <div className="driver-bar" aria-hidden="true">
                <i className="down" style={{ width: `${(Math.abs(driver.downside) / maxSwing) * 50}%` }} />
                <i className="up" style={{ width: `${(Math.abs(driver.upside) / maxSwing) * 50}%` }} />
              </div>
              <div className="driver-values tabular">
                <span>{signed(driver.downside)}</span>
                <span>{signed(driver.upside)}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="drivers">
          {!global && (
            <div className="full-run">
              <p>Runs the model 72 times across plausible ranges of all inputs and ranks their overall influence. Takes a few seconds.</p>
              <button className="button" onClick={onRunGlobal} disabled={globalLoading}>
                {globalLoading ? <><Loader2 size={15} className="spin" /> Running 72 model runs…</> : "Run full test"}
              </button>
            </div>
          )}
          {global?.drivers.map((driver) => (
            <div className="driver" key={driver.parameter}>
              <div className="driver-head">
                <span>{driver.driver}</span>
                <small className="tabular">{percent(driver.relative_importance)} of influence</small>
              </div>
              <div className="driver-bar single" aria-hidden="true"><i style={{ width: `${Math.max(1, (driver.relative_importance / maxShare) * 100)}%` }} /></div>
            </div>
          ))}
          {global && <p className="footnote">Ranked by average effect on the selected market&apos;s guest nights across {global.evaluations} model runs.</p>}
        </div>
      )}
    </Card>
  );
}
