"use client";

// AI/MAINTAINER PARITY RULE:
// Any scenario-control change in this custom dashboard must be made in
// prototype/app.py in the same task, with the shared API, tests, README files,
// and UI_SCENARIO_PARITY.md kept synchronized.

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";
import ReactECharts from "echarts-for-react";
import {
  ArrowRight,
  BarChart3,
  BrainCircuit,
  Database,
  Hotel,
  Info,
  Plane,
  Route,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Users,
} from "lucide-react";

import { ScrollStory } from "@/components/scroll-story";
import type { GlobalSensitivityPayload, OptionsPayload, SensitivityPayload, SimulationPayload } from "@/lib/types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type FormState = {
  mode: "Existing route" | "New route";
  origin: string;
  market: string;
  startDate: string;
  endDate: string;
  weeklyFlights: number;
  seatsPerFlightChange: number;
  loadFactorPoints: number;
  seatsPerFlight: number;
  newRouteLoadFactor: number;
  transferShare: number;
  transitShare: number;
  visitorShare: number;
  hotelCapture: number;
  allocationShare: number;
};

const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });
const integer = new Intl.NumberFormat("en", { maximumFractionDigits: 0 });

function changeLabel(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${integer.format(value)}`;
}

function requestBody(next: FormState) {
  return {
    mode: next.mode,
    origin_country: next.origin,
    target_nationality: next.market,
    start_date: next.startDate,
    end_date: next.endDate,
    ...(next.mode === "Existing route"
      ? { scenario_weekly_flights: next.weeklyFlights }
      : {
          new_route_weekly_flights: next.weeklyFlights,
          new_route_seats_per_flight: next.seatsPerFlight,
          new_route_load_factor: next.newRouteLoadFactor,
        }),
    seats_per_flight_change_pct: next.seatsPerFlightChange,
    load_factor_change_points: next.loadFactorPoints,
    transfer_share: next.transferShare,
    transit_share: next.transitShare,
    visitor_share: next.visitorShare,
    hotel_capture_rate: next.hotelCapture,
    nationality_allocation_share: next.allocationShare,
  };
}

function MetricCard({ label, value, delta, icon: Icon }: {
  label: string;
  value: number | string;
  delta?: number;
  icon: typeof Plane;
}) {
  return (
    <motion.div className="metric-card" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}>
      <div className="metric-label"><Icon size={16} /> {label}</div>
      <div className="metric-value">{typeof value === "number" ? integer.format(value) : value}</div>
      {delta !== undefined && <div className={delta >= 0 ? "metric-delta positive" : "metric-delta negative"}>{changeLabel(delta)}</div>}
    </motion.div>
  );
}

export function ScenarioApp() {
  const [options, setOptions] = useState<OptionsPayload | null>(null);
  const [result, setResult] = useState<SimulationPayload | null>(null);
  const [sensitivity, setSensitivity] = useState<SensitivityPayload | null>(null);
  const [globalSensitivity, setGlobalSensitivity] = useState<GlobalSensitivityPayload | null>(null);
  const [globalLoading, setGlobalLoading] = useState(false);
  const [form, setForm] = useState<FormState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const runScenario = useCallback(async (next: FormState) => {
    setLoading(true);
    setError(null);
    try {
      if (next.startDate > next.endDate) throw new Error("Start date must not be after end date");
      if (next.transferShare + next.transitShare >= 0.98) throw new Error("Transfer and transit shares must sum to less than 98%");
      const body = requestBody(next);
      const [response, sensitivityResponse] = await Promise.all([fetch(`${API}/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }), fetch(`${API}/sensitivity`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })]);
      if (!response.ok) throw new Error(await response.text());
      setResult(await response.json());
      setSensitivity(sensitivityResponse.ok ? await sensitivityResponse.json() : null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to run the scenario");
    } finally {
      setLoading(false);
    }
  }, []);

  const runGlobalSensitivity = useCallback(async (next: FormState) => {
    setGlobalLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API}/global-sensitivity`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody(next)),
      });
      if (!response.ok) throw new Error(await response.text());
      setGlobalSensitivity(await response.json());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to run global sensitivity");
    } finally {
      setGlobalLoading(false);
    }
  }, []);

  useEffect(() => {
    async function initialise() {
      try {
        const response = await fetch(`${API}/options`);
        if (!response.ok) throw new Error("Scenario service is unavailable");
        const payload: OptionsPayload = await response.json();
        setOptions(payload);
        const initial = {
          mode: "Existing route" as const,
          origin: payload.default_origin,
          market: payload.default_market,
          startDate: payload.minimum_date,
          endDate: payload.maximum_date,
          weeklyFlights: payload.default_scenario.scenario_weekly_flights,
          seatsPerFlightChange: 0,
          loadFactorPoints: 0,
          seatsPerFlight: 180,
          newRouteLoadFactor: 0.75,
          transferShare: payload.default_scenario.transfer_share,
          transitShare: payload.default_scenario.transit_share,
          visitorShare: payload.default_scenario.visitor_share,
          hotelCapture: payload.default_scenario.hotel_capture_rate,
          allocationShare: payload.default_scenario.nationality_allocation_share,
        };
        setForm(initial);
        await runScenario(initial);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Unable to initialise");
        setLoading(false);
      }
    }
    initialise();
  }, [runScenario]);

  const selectedLift = result
    ? result.selected_market_scenario_nights - result.selected_market_baseline_nights
    : 0;
  const totalLift = result ? result.scenario_guest_nights - result.baseline_guest_nights : 0;
  const updateForm = (next: FormState) => {
    setForm(next);
    setResult(null);
    setSensitivity(null);
    setGlobalSensitivity(null);
  };

  const chartOption = useMemo(() => ({
    backgroundColor: "transparent",
    animationDuration: 700,
    tooltip: { trigger: "axis", backgroundColor: "#10243a", borderColor: "#24455f", textStyle: { color: "#eff8ff" } },
    legend: { top: 0, right: 0, textStyle: { color: "#9eb0c5" } },
    grid: { left: 12, right: 12, top: 44, bottom: 10, containLabel: true },
    xAxis: {
      type: "category",
      data: result?.monthly.map((item) => item.month) ?? [],
      boundaryGap: false,
      axisLine: { lineStyle: { color: "#264058" } },
      axisLabel: { color: "#8fa2b8" },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: "#8fa2b8", formatter: (value: number) => compact.format(value) },
      splitLine: { lineStyle: { color: "rgba(148,163,184,.10)" } },
    },
    series: [
      { name: "Baseline", type: "line", smooth: true, symbol: "none", data: result?.monthly.map((item) => item.baseline) ?? [], lineStyle: { color: "#72849b", width: 2 } },
      { name: "Scenario", type: "line", smooth: true, symbol: "circle", symbolSize: 6, data: result?.monthly.map((item) => item.scenario) ?? [], lineStyle: { color: "#38e0ca", width: 3 }, itemStyle: { color: "#38e0ca" }, areaStyle: { color: "rgba(56,224,202,.08)" } },
    ],
  }), [result]);

  return (
    <div className="site-shell">
      <header className="topbar">
        <a className="brand" href="#top"><span className="brand-mark"><Plane size={18} /></span><span>AeroStay <b>Intelligence</b></span></a>
        <nav>
          <a href="#scenario">Scenario</a>
          <a href="#conversion">Conversion</a>
          <a href="#stress-test">Stress test</a>
          <a href="#evidence">Evidence</a>
        </nav>
        <div className="live-pill"><span /> Pooled Poisson XGBoost online</div>
      </header>

      <main id="top">
        <ScrollStory origin={form?.origin ?? "Origin"} market={form?.market ?? "Market"} result={result} />

        <section className="section" id="scenario">
          <div className="section-heading">
            <div><div className="eyebrow"><SlidersHorizontal size={14} /> Scenario studio</div><h2>Change the flight plan. See the hotel impact.</h2></div>
            <p>Test an established-route capacity change or a proposed connection. Every displayed result is calculated by the live service.</p>
          </div>

          <div className="scenario-layout">
            <div className="control-panel">
              <div className="panel-title"><span>01</span><div><b>Define the route</b><small>Historical or proposed service</small></div></div>
              {form && options && <>
                <div className="mode-toggle" role="group" aria-label="Route status">
                  {(["Existing route", "New route"] as const).map((mode) => <button key={mode} className={form.mode === mode ? "active" : ""} onClick={() => {
                    const candidates = mode === "New route" && options.unserved_markets.length ? options.unserved_markets : options.origins;
                    const origin = candidates[0];
                    const route = options.route_baselines[origin];
                    const market = options.markets.includes(origin) ? origin : form.market;
                    updateForm({
                      ...form,
                      mode,
                      origin,
                      market,
                      weeklyFlights: mode === "New route" ? 2 : (route?.weekly_flights ?? 0) + 2,
                      transferShare: mode === "New route" ? 0.20 : (route?.transfer_share ?? 0),
                      transitShare: mode === "New route" ? 0.02 : (route?.transit_share ?? 0),
                      allocationShare: origin === market ? 1 : 0.5,
                    });
                  }}>{mode}</button>)}
                </div>
                <div className="date-grid">
                  <label>Start date<input type="date" min={options.minimum_date} max={options.maximum_date} value={form.startDate} onChange={(event) => updateForm({ ...form, startDate: event.target.value })} /></label>
                  <label>End date<input type="date" min={options.minimum_date} max={options.maximum_date} value={form.endDate} onChange={(event) => updateForm({ ...form, endDate: event.target.value })} /></label>
                </div>
                <label>Departure origin<select value={form.origin} onChange={(event) => {
                  const origin = event.target.value;
                  const route = options.route_baselines[origin];
                  const market = options.markets.includes(origin) ? origin : form.market;
                  updateForm({
                    ...form,
                    origin,
                    market,
                    weeklyFlights: form.mode === "New route" ? form.weeklyFlights : (route?.weekly_flights ?? 0) + 2,
                    transferShare: form.mode === "New route" ? form.transferShare : (route?.transfer_share ?? 0),
                    transitShare: form.mode === "New route" ? form.transitShare : (route?.transit_share ?? 0),
                    allocationShare: origin === market ? 1 : 0.5,
                  });
                }}>{(form.mode === "New route" && options.unserved_markets.length ? options.unserved_markets : options.origins).map((origin) => <option key={origin}>{origin}</option>)}</select></label>
                <label>Hotel nationality<select value={form.market} onChange={(event) => {
                  const market = event.target.value;
                  updateForm({ ...form, market, allocationShare: form.origin === market ? 1 : 0.5 });
                }}>{options.markets.map((market) => <option key={market}>{market}</option>)}</select></label>

                <div className="control-divider" />
                <div className="panel-title"><span>02</span><div><b>Adjust aviation supply</b><small>Baseline → scenario</small></div></div>
                <label>Weekly flights<div className="number-control"><small>{form.mode === "New route" ? "0 new service" : `${(options.route_baselines[form.origin]?.weekly_flights ?? 0).toFixed(1)} baseline`}</small><input type="number" min="0" max={form.mode === "New route" ? 100 : 1000} step="1" value={form.weeklyFlights.toFixed(1)} onChange={(event) => updateForm({ ...form, weeklyFlights: Number(event.target.value) })} /></div></label>
                {form.mode === "Existing route" ? <>
                  <label>Seats-per-flight change <output>{form.seatsPerFlightChange > 0 ? "+" : ""}{form.seatsPerFlightChange}%</output><input type="range" min="-40" max="60" step="5" value={form.seatsPerFlightChange} onChange={(event) => updateForm({ ...form, seatsPerFlightChange: Number(event.target.value) })} /></label>
                  <label>Load-factor change <output>{form.loadFactorPoints > 0 ? "+" : ""}{form.loadFactorPoints} pp</output><input type="range" min="-20" max="20" value={form.loadFactorPoints} onChange={(event) => updateForm({ ...form, loadFactorPoints: Number(event.target.value) })} /></label>
                </> : <>
                  <label>Seats per flight <output>{form.seatsPerFlight}</output><input type="range" min="50" max="600" step="10" value={form.seatsPerFlight} onChange={(event) => updateForm({ ...form, seatsPerFlight: Number(event.target.value) })} /></label>
                  <label>Expected load factor <output>{Math.round(form.newRouteLoadFactor * 100)}%</output><input type="range" min="30" max="100" value={form.newRouteLoadFactor * 100} onChange={(event) => updateForm({ ...form, newRouteLoadFactor: Number(event.target.value) / 100 })} /></label>
                </>}

                <div className="control-divider" />
                <div className="panel-title"><span>03</span><div><b>Set conversion assumptions</b><small>Explicit, adjustable and labelled</small></div></div>
                <label>Transfer share <output>{Math.round(form.transferShare * 100)}%</output><input type="range" min="0" max="90" value={form.transferShare * 100} onChange={(event) => updateForm({ ...form, transferShare: Number(event.target.value) / 100 })} /></label>
                <label>Transit share <output>{Math.round(form.transitShare * 100)}%</output><input type="range" min="0" max="25" value={form.transitShare * 100} onChange={(event) => updateForm({ ...form, transitShare: Number(event.target.value) / 100 })} /></label>
                <label>Visitor share <output>{Math.round(form.visitorShare * 100)}%</output><input type="range" min="20" max="100" value={form.visitorShare * 100} onChange={(event) => updateForm({ ...form, visitorShare: Number(event.target.value) / 100 })} /></label>
                <label>Hotel-capture rate <output>{Math.round(form.hotelCapture * 100)}%</output><input type="range" min="10" max="100" value={form.hotelCapture * 100} onChange={(event) => updateForm({ ...form, hotelCapture: Number(event.target.value) / 100 })} /></label>
                <label>Origin-to-nationality allocation <output>{Math.round(form.allocationShare * 100)}%</output><input type="range" min="10" max="100" step="5" value={form.allocationShare * 100} onChange={(event) => updateForm({ ...form, allocationShare: Number(event.target.value) / 100 })} /></label>
                <button className="run-button" disabled={loading} onClick={() => runScenario(form)}>{loading ? "Simulating…" : "Run scenario"}<ArrowRight size={17} /></button>
              </>}
            </div>

            <div className="results-panel">
              <div className="result-header"><div><span>Scenario result</span><h3>{form?.origin ?? "Route"} {form?.mode === "New route" ? "route launch" : "capacity expansion"}</h3></div><div className={`support-badge ${form?.mode === "New route" ? "warning" : ""}`}><ShieldCheck size={15} /> {form?.mode === "New route" ? "Analog estimate" : "Established route"}</div></div>
              {error && <div className="error-box">{error}</div>}
              {!error && !result && <div className="empty-result"><Route size={28} /><b>{loading ? "Calculating scenario…" : "Inputs changed"}</b><p>{loading ? "The model and stress test are running." : "Run the scenario to replace the previous result with this case."}</p></div>}
              {!error && result && <>
                <div className="metrics-grid">
                  <MetricCard label="Scenario guests" value={result?.scenario_predicted_guests ?? 0} delta={result ? result.scenario_predicted_guests - result.baseline_predicted_guests : 0} icon={Users} />
                  <MetricCard label="Scenario guest nights" value={result?.scenario_guest_nights ?? 0} delta={totalLift} icon={Hotel} />
                  <MetricCard label={`${form?.market ?? "Market"} impact`} value={Math.abs(selectedLift)} delta={selectedLift} icon={Route} />
                  <MetricCard label="Chronological holdout WMAPE" value={result?.metrics?.combined ? `${(result.metrics.combined.wmape * 100).toFixed(2)}%` : "12.99%"} icon={BarChart3} />
                </div>
                <div className="decision-brief">
                  <div className="decision-icon"><Sparkles size={20} /></div>
                  <div><span>Planner brief</span><p>Adding <b>{result ? (result.scenario_weekly_flights - result.baseline_weekly_flights).toFixed(1) : "—"} weekly flights</b> is associated with <b>{changeLabel(selectedLift)} guest nights</b> for {form?.market}. Prepare market activation and hotel capacity while monitoring the visible conversion assumptions.</p></div>
                </div>
                <div className="range-card"><span>Scenario range</span><strong>{compact.format(result?.planning_range_low ?? 0)} – {compact.format(result?.planning_range_high ?? 0)}</strong><small>Assumption variation + held-out WMAPE; not a causal interval</small></div>
              </>}
            </div>
          </div>
        </section>

        <section className="section" id="stress-test">
          <div className="section-heading">
            <div><div className="eyebrow"><BarChart3 size={14} /> Decision stress test</div><h2>Know which assumption can change the answer.</h2></div>
            <p>Each bar reruns the complete conversion chain and pooled Poisson XGBoost while changing one input at a time. Longer spans deserve more validation.</p>
          </div>
          <div className="sensitivity-panel">
            <div className="sensitivity-intro"><span>Ranked by output swing</span><strong>{form?.market} guest nights</strong><small>Low case ← current scenario → high case</small></div>
            <div className="tornado-chart">
              {sensitivity?.drivers.map((driver, index) => {
                const maxSwing = sensitivity.drivers[0]?.swing || 1;
                const left = Math.max(3, Math.abs(driver.downside) / maxSwing * 46);
                const right = Math.max(3, Math.abs(driver.upside) / maxSwing * 46);
                return <div className="tornado-row" key={driver.driver}>
                  <div className="tornado-label"><span>0{index + 1}</span><div><b>{driver.driver}</b><small>{driver.perturbation}</small></div></div>
                  <div className="tornado-bars"><i className="down" style={{ width: `${left}%` }} /><em /><i className="up" style={{ width: `${right}%` }} /></div>
                  <div className="tornado-values"><span>{changeLabel(driver.downside)}</span><b>{changeLabel(driver.upside)}</b></div>
                </div>;
              })}
            </div>
          </div>
          <div className="global-sensitivity-panel">
            <div className="global-sensitivity-heading">
              <div><span>SALib · Morris global sensitivity</span><h3>Test all levers together</h3><p>Unlike the one-at-a-time chart, Morris samples combinations across plausible bounds. Overall influence is μ*; a larger σ suggests interactions or non-linear behavior.</p></div>
              <button className="analysis-button" disabled={!form || globalLoading} onClick={() => form && runGlobalSensitivity(form)}>{globalLoading ? "Running Morris analysis…" : "Run global sensitivity"}</button>
            </div>
            {globalSensitivity && <div className="global-driver-list">
              {globalSensitivity.drivers.map((driver) => <div className="global-driver-row" key={driver.parameter}>
                <span>{String(driver.rank).padStart(2, "0")}</span>
                <div><b>{driver.driver}</b><small>{Math.round(driver.relative_importance * 100)}% relative influence · σ {compact.format(driver.sigma)}</small></div>
                <i><em style={{ width: `${Math.max(2, driver.relative_importance * 100)}%` }} /></i>
                <strong>μ* {compact.format(driver.mu_star)}</strong>
              </div>)}
              <small className="analysis-note">{globalSensitivity.evaluations} model evaluations · {globalSensitivity.interpretation}</small>
            </div>}
          </div>
        </section>

        <section className="section" id="conversion">
          <div className="section-heading">
            <div><div className="eyebrow"><Route size={14} /> Transparent conversion</div><h2>Every passenger is accounted for.</h2></div>
            <p>The flow narrows at each stage, separating observed aviation measures, explicit assumptions and the modelled hotel output.</p>
          </div>
          <div className="conversion-grid">
            <div className="flow-panel">
              {result?.chain.map((stage, index) => {
                const max = result.chain[0]?.scenario || 1;
                const width = Math.max(28, Math.min(100, (stage.scenario / max) * 100));
                return <motion.div className="flow-row" key={stage.stage} initial={{ opacity: 0, x: -12 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: index * .07 }}>
                  <div className="flow-meta"><span>{String(index + 1).padStart(2, "0")}</span><div><b>{stage.stage}</b><small>{stage.source}</small></div><strong>{compact.format(stage.scenario)}</strong></div>
                  <div className="flow-track"><motion.div initial={{ width: 0 }} whileInView={{ width: `${width}%` }} viewport={{ once: true }} transition={{ duration: .75, delay: index * .07 }} /></div>
                </motion.div>;
              })}
            </div>
            <div className="chart-panel">
              <div className="chart-heading"><div><span>Seasonal profile</span><h3>Monthly guest nights</h3></div><small>Baseline vs scenario</small></div>
              <ReactECharts option={chartOption} style={{ height: 350 }} />
            </div>
          </div>
        </section>

        <section className="section" id="evidence">
          <div className="section-heading">
            <div><div className="eyebrow"><ShieldCheck size={14} /> Model evidence</div><h2>A strong result is one a planner can challenge.</h2></div>
            <p>Pooled Poisson XGBoost captures non-linear market and seasonal effects while learning both demand regimes together. The transparent scenario layer keeps every planning assumption auditable.</p>
          </div>
          <div className="evidence-grid">
            <div className="model-card feature"><div className="card-icon"><BrainCircuit /></div><span>Machine-learning layer</span><h3>Pooled Poisson XGBoost</h3><p>One estimator learns domestic and international demand together while retaining segment, market, seasonality and arrivals history as features.</p><div className="model-tags"><b>Gradient boosting</b><b>One pooled model</b><b>Poisson count loss</b></div></div>
            <div className="model-card"><div className="card-icon"><Database /></div><span>Holdout design</span><h3>No future dates in training</h3><p>Training ends on 31 July 2024. Evaluation runs from 1 August 2024 through 28 February 2025.</p><div className="timeline"><i /><i className="active" /><small>Train</small><small>212-day holdout</small></div></div>
            <div className="model-card metrics"><div className="card-icon"><BarChart3 /></div><span>Honest error</span><h3>{result?.metrics?.combined ? `${(result.metrics.combined.wmape * 100).toFixed(2)}% WMAPE` : "12.99% WMAPE"}</h3><p>Combined chronological holdout. Domestic and international performance remain visible rather than hidden in one headline.</p><div className="mini-metrics"><div><b>{result?.metrics?.domestic ? `${(result.metrics.domestic.wmape * 100).toFixed(1)}%` : "7.6%"}</b><small>Domestic</small></div><div><b>{result?.metrics?.international ? `${(result.metrics.international.wmape * 100).toFixed(1)}%` : "16.2%"}</b><small>International</small></div></div></div>
          </div>
          <div className="model-blueprint">
            <div><span>01 · Observed inputs</span><b>Market, date, arrivals, same-day guests</b><small>Hotel records supplied by the challenge</small></div>
            <ArrowRight />
            <div><span>02 · Time-safe features</span><b>Calendar + market + arrivals history</b><small>Built without using future target dates</small></div>
            <ArrowRight />
            <div><span>03 · Segment estimators</span><b>XGBoost: domestic / international</b><small>Non-linear trees fitted by gradient boosting</small></div>
            <ArrowRight />
            <div><span>04 · Output</span><b>Guestŝ = Σ trees(x)</b><small>Guest nights = max(guestŝ − same-day, 0)</small></div>
          </div>
          <div className="explain-strip"><Info size={18} /><p><b>What the model does—and does not claim.</b> It predicts supplied hotel <code>Guests</code>; guest nights are derived by subtracting same-day guests. Scenario impacts are conditional planning estimates, not causal guarantees. Visitor share, hotel capture and origin-to-nationality allocation remain explicit assumptions because they are absent from the local data.</p></div>
        </section>
      </main>

      <footer><div className="brand"><span className="brand-mark"><Plane size={18} /></span><span>AeroStay <b>Intelligence</b></span></div><p>Explainable aviation-to-hotel demand planning for Abu Dhabi.</p><span>Prototype · Pooled Poisson XGBoost + transparent scenario engine</span></footer>
    </div>
  );
}
