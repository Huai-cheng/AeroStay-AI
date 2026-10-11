"use client";

// AI/MAINTAINER PARITY RULE:
// Any scenario-control change in this custom dashboard must be made in
// prototype/app.py in the same task, with the shared API, tests, README files,
// and UI_SCENARIO_PARITY.md kept synchronized.

import { useMemo, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowDown, ArrowUp, Check, ChevronDown, RotateCcw } from "lucide-react";

import { FlightMap, type MapFlow } from "@/components/flight-map";
import { ConversionFunnel, describeChange, Drivers, HeroResult, HeroStats, marketLift, MonthlyImpact, takeaway } from "@/components/insights";
import { Logo, PLANE_PATH } from "@/components/logo";
import { Skyline } from "@/components/skyline";
import { AnimatedNumber, Segmented, Select, Slider, Stepper } from "@/components/ui";
import { countryName, formatDecimal, percent, signed } from "@/lib/format";
import type { SimulationPayload } from "@/lib/types";
import { originsFor, useScenario, withMarket, withMode, withOrigin, type RouteMode, type ScenarioState } from "@/lib/use-scenario";

function mapFlow(result: SimulationPayload | null): MapFlow | null {
  if (!result || result.chain.length < 5) return null;
  return {
    weeklyFlights: result.scenario_weekly_flights,
    passengers: result.chain[1].scenario,
    destination: result.chain[2].scenario,
    hotel: result.chain[4].scenario,
  };
}

function scrollToSimulator() {
  document.getElementById("simulator")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function ScenarioApp() {
  const scenario = useScenario();
  const { options, result } = scenario;
  const flow = useMemo(() => mapFlow(result), [result]);
  const weeklyFlights = useMemo(() => {
    if (!options) return undefined;
    return Object.fromEntries(Object.entries(options.route_baselines).map(([key, route]) => [key, route.weekly_flights]));
  }, [options]);

  return (
    <div className="snap-root">
      <Landing scenario={scenario} flow={flow} weeklyFlights={weeklyFlights} />
      <Simulator scenario={scenario} flow={flow} weeklyFlights={weeklyFlights} />
    </div>
  );
}

function Landing({ scenario, flow, weeklyFlights }: { scenario: ScenarioState; flow: MapFlow | null; weeklyFlights?: Record<string, number> }) {
  const { options, result, form } = scenario;
  return (
    <section className="landing snap-section" aria-label="Introduction">
      <FlightMap
        variant="hero"
        className="landing-radar"
        origins={options?.origins ?? []}
        weeklyFlights={weeklyFlights}
        selected={result?.origin_country ?? form?.origin ?? null}
        flow={flow}
      />
      <div className="landing-fade" aria-hidden="true" />
      <header className="landing-nav">
        <Logo />
        <Link href="/how-it-works" className="nav-link">How it works</Link>
      </header>

      <div className="landing-copy">
        <p className="kicker"><span lang="ar" dir="rtl">أبوظبي</span><i aria-hidden="true" />Abu Dhabi hotel demand simulator</p>
        <h1>See how flights become <em>hotel nights.</em></h1>
        <p className="lede">Change a route, a schedule or an aircraft, and watch hotel guest numbers in Abu Dhabi respond by country and by month.</p>

        <div className="landing-live" aria-live="polite">
          <span className="live-label"><i aria-hidden="true" />Live from the model</span>
          {result ? (
            <>
              <strong className="tabular"><AnimatedNumber value={marketLift(result)} format={(value) => signed(value)} /> <small>guest nights</small></strong>
              <span className="live-desc">{describeChange(result)}, for {countryName(result.target_nationality)} guests</span>
            </>
          ) : (
            <>
              <strong className="skeleton-line" aria-hidden="true" />
              <span className="live-desc">{scenario.loadError ? "The scenario service is offline." : "Running the first scenario…"}</span>
            </>
          )}
        </div>

        <div className="landing-actions">
          <button className="button primary" onClick={scrollToSimulator}>Open the simulator <ArrowDown size={17} /></button>
          <Link href="/how-it-works" className="button ghost">How it works</Link>
        </div>
      </div>

      <Skyline className="landing-skyline" />
      <button className="scroll-cue" onClick={scrollToSimulator} aria-label="Scroll to the simulator"><span>Scroll</span><ArrowDown size={14} /></button>
    </section>
  );
}

function Simulator({ scenario, flow, weeklyFlights }: { scenario: ScenarioState; flow: MapFlow | null; weeklyFlights?: Record<string, number> }) {
  const { options, form, result, sensitivity, simulating, error, formError, loadError, retry } = scenario;
  const lift = result ? marketLift(result) : 0;
  return (
    <section id="simulator" className="app snap-section" aria-label="Scenario simulator">
      <header className="app-bar">
        <Logo size={28} />
        <RouteBadge
          origin={form ? countryName(form.origin) : null}
          proposed={form?.mode === "New route"}
          busy={simulating}
          resultKey={result ? `${result.origin_country}:${result.selected_market_scenario_nights}` : null}
        />
        <div className="app-bar-live tabular" aria-hidden="true">
          {result && <><AnimatedNumber value={lift} format={(value) => signed(value)} /><small>nights</small></>}
        </div>
        <nav className="app-nav">
          <Link href="/how-it-works" className="nav-link">How it works</Link>
          <button className="icon-button" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })} aria-label="Back to the top"><ArrowUp size={16} /></button>
        </nav>
      </header>

      <aside className="sidebar" aria-label="Scenario controls">
        {options && form ? <Controls scenario={scenario} /> : <ControlsSkeleton />}
      </aside>

      <main className="main">
        {loadError ? (
          <div className="state-card">
            <AlertCircle size={22} />
            <h2>Can&apos;t reach the model</h2>
            <p>{loadError}</p>
            <button className="button primary" onClick={retry}>Try again</button>
          </div>
        ) : !result ? (
          <MainSkeleton />
        ) : (
          <div className={`main-grid ${simulating ? "is-updating" : ""}`}>
            {(error || formError) && (
              <div className="banner" role="alert"><AlertCircle size={16} /> {formError ?? error} <span>Showing the last valid result.</span></div>
            )}
            <section className="card hero-card">
              <div className="hero-left">
                <HeroResult result={result} />
                <p className="hero-takeaway">{takeaway(result, sensitivity)}</p>
              </div>
              <HeroStats result={result} />
              <div className="hero-right">
                <FlightMap variant="card" className="card-radar" origins={options?.origins ?? []} weeklyFlights={weeklyFlights} selected={result.origin_country} flow={flow} />
                <ul className="radar-legend">
                  <li><i className="gold" />Hotel guests {flow && flow.passengers > 0 ? percent(flow.hotel / flow.passengers) : ""}</li>
                  <li><i className="white" />Other arrivals</li>
                  <li><i className="grey" />Connecting onward {flow && flow.passengers > 0 ? percent(1 - flow.destination / flow.passengers) : ""}</li>
                </ul>
              </div>
            </section>
            <ConversionFunnel result={result} />
            <MonthlyImpact result={result} />
            <Drivers
              sensitivity={sensitivity}
              loading={scenario.sensitivityLoading}
              global={scenario.globalSensitivity}
              globalLoading={scenario.globalLoading}
              onRunGlobal={scenario.runGlobalSensitivity}
            />
            <p className="main-footnote">
              Planning estimates from a pooled Poisson XGBoost model and the conversion steps on the left, not guarantees. <Link href="/how-it-works">Method and limitations</Link>
            </p>
          </div>
        )}
      </main>
    </section>
  );
}

function RouteBadge({ origin, proposed, busy, resultKey }: { origin: string | null; proposed: boolean; busy: boolean; resultKey: string | null }) {
  return (
    <div className={`route-badge ${busy ? "is-busy" : ""}`}>
      <span className="route-place" title={origin ?? undefined}>{origin ?? "…"}</span>
      <span className={`route-track ${proposed ? "proposed" : ""}`} aria-label={proposed ? "proposed route to" : "to"}>
        <i className="route-line" />
        <svg className="route-plane" viewBox="0 0 24 24" aria-hidden="true"><path d={PLANE_PATH} transform="rotate(90 12 12)" /></svg>
      </span>
      <span className="route-place dest">Abu Dhabi</span>
      <span className="route-divider" aria-hidden="true" />
      <span className="route-status" role="status" aria-live="polite">
        {busy ? (
          <span className="status-busy"><i className="status-spinner" aria-hidden="true" />Updating</span>
        ) : resultKey ? (
          // Re-keyed on every new result so the "Updated" confirmation replays, then settles to "Live".
          <span className="status-done" key={resultKey}>
            <span className="status-updated"><Check size={13} strokeWidth={2.5} aria-hidden="true" />Updated</span>
            <span className="status-live" aria-hidden="true"><i />Live</span>
          </span>
        ) : (
          <span className="status-busy"><i className="status-spinner" aria-hidden="true" />Loading</span>
        )}
      </span>
    </div>
  );
}

function Controls({ scenario }: { scenario: ScenarioState }) {
  const { options, form, update, reset, formError } = scenario;
  const [assumptionsOpen, setAssumptionsOpen] = useState(false);
  if (!options || !form) return null;
  const route = options.route_baselines[form.origin];
  const isNew = form.mode === "New route";
  const dateError = form.startDate > form.endDate;
  const shareError = form.transferShare + form.transitShare >= 0.98;

  return (
    <div className="controls">
      <div className="group">
        <h2>Route</h2>
        <Segmented<RouteMode>
          label="Route type"
          value={form.mode}
          options={[{ value: "Existing route", label: "Existing route" }, { value: "New route", label: "New route" }]}
          onChange={(mode) => mode !== form.mode && update(withMode(form, options, mode))}
        />
        <Select
          label="Flights from"
          value={form.origin}
          options={originsFor(options, form.mode).map((key) => ({ value: key, label: countryName(key) }))}
          onChange={(origin) => update(withOrigin(form, options, origin))}
        />
        <Select
          label="Hotel guests of nationality"
          value={form.market}
          options={options.markets.map((key) => ({ value: key, label: countryName(key) }))}
          onChange={(market) => update(withMarket(form, market))}
        />
        <div className="date-pair">
          <div className="field">
            <div className="field-row"><label htmlFor="start-date">From</label></div>
            <input id="start-date" type="date" className={dateError ? "invalid" : ""} min={options.minimum_date} max={options.maximum_date} value={form.startDate} onChange={(event) => update({ ...form, startDate: event.target.value })} />
          </div>
          <div className="field">
            <div className="field-row"><label htmlFor="end-date">To</label></div>
            <input id="end-date" type="date" className={dateError ? "invalid" : ""} min={options.minimum_date} max={options.maximum_date} value={form.endDate} onChange={(event) => update({ ...form, endDate: event.target.value })} />
          </div>
        </div>
        {dateError && <p className="field-error">{formError}</p>}
      </div>

      <div className="group">
        <h2>Flights</h2>
        <Stepper
          label="Weekly flights"
          hint={isNew ? "New service, up to 100 a week" : `Today: ${formatDecimal(route?.weekly_flights ?? 0)} a week`}
          value={form.weeklyFlights}
          min={0}
          max={isNew ? 100 : 1000}
          onChange={(weeklyFlights) => update({ ...form, weeklyFlights })}
        />
        {isNew ? (
          <>
            <Slider label="Seats per flight" hint="Aircraft size for the new service" value={form.seatsPerFlight} min={50} max={600} step={10} display={String(form.seatsPerFlight)} onChange={(seatsPerFlight) => update({ ...form, seatsPerFlight })} />
            <Slider label="Expected load factor" hint="Share of seats filled" value={Math.round(form.newRouteLoadFactor * 100)} min={30} max={100} display={percent(form.newRouteLoadFactor)} onChange={(value) => update({ ...form, newRouteLoadFactor: value / 100 })} />
          </>
        ) : (
          <>
            <Slider label="Seats per flight" hint="Larger or smaller aircraft than today" value={form.seatsPerFlightChange} min={-40} max={60} step={5} baseline={0} baselineLabel="Today" display={`${form.seatsPerFlightChange > 0 ? "+" : ""}${form.seatsPerFlightChange}%`} onChange={(seatsPerFlightChange) => update({ ...form, seatsPerFlightChange })} />
            <Slider label="Load factor" hint={`Today ${percent(route?.load_factor ?? 0)} of seats are filled`} value={form.loadFactorPoints} min={-20} max={20} baseline={0} baselineLabel="Today" display={`${form.loadFactorPoints > 0 ? "+" : ""}${form.loadFactorPoints} pts`} onChange={(loadFactorPoints) => update({ ...form, loadFactorPoints })} />
          </>
        )}
      </div>

      <div className={`group collapsible ${assumptionsOpen ? "open" : ""}`}>
        <h2>
          <button className="group-toggle" aria-expanded={assumptionsOpen} aria-controls="assumptions" onClick={() => setAssumptionsOpen((open) => !open)}>
            <span>
              <span className="group-title">Conversion assumptions</span>
              <small>{percent(form.transferShare)} transfer · {percent(form.visitorShare)} visitors · {percent(form.hotelCapture)} hotel</small>
            </span>
            <ChevronDown size={18} aria-hidden="true" />
          </button>
        </h2>
        <div className="collapsible-body" id="assumptions" inert={!assumptionsOpen}>
          <div>
            <Slider label="Transfer share" hint="Passengers connecting to another flight" value={Math.round(form.transferShare * 100)} min={0} max={90} baseline={!isNew && route ? route.transfer_share * 100 : undefined} baselineLabel="Observed" display={percent(form.transferShare)} onChange={(value) => update({ ...form, transferShare: value / 100 })} />
            <Slider label="Transit share" hint="Passengers who never enter the city" value={Math.round(form.transitShare * 100)} min={0} max={25} baseline={!isNew && route ? route.transit_share * 100 : undefined} baselineLabel="Observed" display={percent(form.transitShare)} onChange={(value) => update({ ...form, transitShare: value / 100 })} />
            {shareError && <p className="field-error">{formError}</p>}
            <Slider label="Visitor share" hint="Arrivals who are visitors, not residents" value={Math.round(form.visitorShare * 100)} min={20} max={100} display={percent(form.visitorShare)} onChange={(value) => update({ ...form, visitorShare: value / 100 })} />
            <Slider label="Hotel capture rate" hint="Visitors who stay in a hotel" value={Math.round(form.hotelCapture * 100)} min={10} max={100} display={percent(form.hotelCapture)} onChange={(value) => update({ ...form, hotelCapture: value / 100 })} />
            <Slider label="Nationality allocation" hint={`Extra hotel guests counted as ${countryName(form.market)} nationals`} value={Math.round(form.allocationShare * 100)} min={10} max={100} step={5} display={percent(form.allocationShare)} onChange={(value) => update({ ...form, allocationShare: value / 100 })} />
          </div>
        </div>
      </div>

      <button className="reset" onClick={reset}><RotateCcw size={14} /> Reset to defaults</button>
    </div>
  );
}

function ControlsSkeleton() {
  return <div className="controls" aria-hidden="true">{Array.from({ length: 7 }, (_, index) => <div key={index} className="skeleton-block" />)}</div>;
}

function MainSkeleton() {
  return (
    <div className="main-grid" aria-busy="true" aria-label="Loading results">
      <div className="card hero-card skeleton-card" />
      <div className="card skeleton-card" />
      <div className="card skeleton-card" />
      <div className="card skeleton-card" />
    </div>
  );
}
