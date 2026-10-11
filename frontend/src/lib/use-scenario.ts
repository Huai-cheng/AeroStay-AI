"use client";

// AI/MAINTAINER PARITY RULE:
// The request fields, defaults and ranges used here must stay equivalent to the
// Streamlit dashboard (prototype/app.py). See UI_SCENARIO_PARITY.md.

import { useCallback, useEffect, useRef, useState } from "react";

import type { GlobalSensitivityPayload, OptionsPayload, SensitivityPayload, SimulationPayload } from "@/lib/types";

export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type RouteMode = "Existing route" | "New route";

export type FormState = {
  mode: RouteMode;
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

export function requestBody(next: FormState) {
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

export function validate(form: FormState): string | null {
  if (!form.startDate || !form.endDate) return "Choose a start and end date.";
  if (form.startDate > form.endDate) return "The start date must be on or before the end date.";
  if (form.transferShare + form.transitShare >= 0.98) return "Transfer and transit shares together must stay below 98%.";
  const maxFlights = form.mode === "New route" ? 100 : 1000;
  if (!Number.isFinite(form.weeklyFlights) || form.weeklyFlights < 0 || form.weeklyFlights > maxFlights) {
    return `Weekly flights must be between 0 and ${maxFlights.toLocaleString("en")}.`;
  }
  return null;
}

export function initialForm(options: OptionsPayload): FormState {
  return {
    mode: "Existing route",
    origin: options.default_origin,
    market: options.default_market,
    startDate: options.minimum_date,
    endDate: options.maximum_date,
    weeklyFlights: options.default_scenario.scenario_weekly_flights,
    seatsPerFlightChange: 0,
    loadFactorPoints: 0,
    seatsPerFlight: 180,
    newRouteLoadFactor: 0.75,
    transferShare: options.default_scenario.transfer_share,
    transitShare: options.default_scenario.transit_share,
    visitorShare: options.default_scenario.visitor_share,
    hotelCapture: options.default_scenario.hotel_capture_rate,
    allocationShare: options.default_scenario.nationality_allocation_share,
  };
}

/** Origins offered for a mode: proposed routes come from markets without service. */
export function originsFor(options: OptionsPayload, mode: RouteMode) {
  return mode === "New route" && options.unserved_markets.length ? options.unserved_markets : options.origins;
}

export function withMode(form: FormState, options: OptionsPayload, mode: RouteMode): FormState {
  const origin = originsFor(options, mode)[0];
  const route = options.route_baselines[origin];
  const market = options.markets.includes(origin) ? origin : form.market;
  return {
    ...form,
    mode,
    origin,
    market,
    weeklyFlights: mode === "New route" ? 2 : (route?.weekly_flights ?? 0) + 2,
    transferShare: mode === "New route" ? 0.2 : (route?.transfer_share ?? 0),
    transitShare: mode === "New route" ? 0.02 : (route?.transit_share ?? 0),
    allocationShare: origin === market ? 1 : 0.5,
  };
}

export function withOrigin(form: FormState, options: OptionsPayload, origin: string): FormState {
  const route = options.route_baselines[origin];
  const market = options.markets.includes(origin) ? origin : form.market;
  return {
    ...form,
    origin,
    market,
    weeklyFlights: form.mode === "New route" ? form.weeklyFlights : (route?.weekly_flights ?? 0) + 2,
    transferShare: form.mode === "New route" ? form.transferShare : (route?.transfer_share ?? 0),
    transitShare: form.mode === "New route" ? form.transitShare : (route?.transit_share ?? 0),
    allocationShare: origin === market ? 1 : 0.5,
  };
}

export function withMarket(form: FormState, market: string): FormState {
  return { ...form, market, allocationShare: form.origin === market ? 1 : 0.5 };
}

async function postJson<T>(path: string, body: unknown, signal: AbortSignal): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    let message = `The scenario service returned ${response.status}.`;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string") message = payload.detail;
      else if (Array.isArray(payload?.detail) && payload.detail[0]?.msg) message = payload.detail[0].msg;
    } catch {
      // keep the generic message
    }
    throw new Error(message);
  }
  return response.json();
}

const isAbort = (cause: unknown) => cause instanceof DOMException && cause.name === "AbortError";

export type ScenarioState = ReturnType<typeof useScenario>;

/**
 * Owns the scenario form and keeps results live: every change re-runs the
 * simulation after a short pause, and stale responses are cancelled so a slow
 * reply can never overwrite a newer scenario.
 */
export function useScenario() {
  const [options, setOptions] = useState<OptionsPayload | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [result, setResult] = useState<SimulationPayload | null>(null);
  const [sensitivity, setSensitivity] = useState<SensitivityPayload | null>(null);
  const [globalSensitivity, setGlobalSensitivity] = useState<GlobalSensitivityPayload | null>(null);
  const [simulating, setSimulating] = useState(false);
  const [sensitivityFor, setSensitivityFor] = useState<FormState | null>(null);
  const [globalLoading, setGlobalLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const globalController = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API}/options`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("The scenario service is unavailable.");
        return response.json() as Promise<OptionsPayload>;
      })
      .then((payload) => {
        setOptions(payload);
        setForm((current) => current ?? initialForm(payload));
        setLoadError(null);
      })
      .catch((cause) => {
        if (isAbort(cause)) return;
        setLoadError("We couldn't reach the scenario service. Check that the API is running, then try again.");
      });
    return () => controller.abort();
  }, [attempt]);

  const formError = form ? validate(form) : null;
  // Sensitivity lags the main result; it is loading until it matches the current form.
  const sensitivityLoading = form !== null && !formError && sensitivityFor !== form;

  useEffect(() => {
    if (!form || formError) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setSimulating(true);
      try {
        const payload = await postJson<SimulationPayload>("/simulate", requestBody(form), controller.signal);
        setResult(payload);
        setError(null);
      } catch (cause) {
        if (isAbort(cause)) return;
        setError(cause instanceof Error ? cause.message : "Unable to run the scenario.");
      } finally {
        if (!controller.signal.aborted) setSimulating(false);
      }
    }, 220);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [form, formError]);

  useEffect(() => {
    if (!form || formError) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const payload = await postJson<SensitivityPayload>("/sensitivity", requestBody(form), controller.signal);
        setSensitivity(payload);
        setSensitivityFor(form);
      } catch (cause) {
        if (isAbort(cause)) return;
        setSensitivity(null);
        setSensitivityFor(form);
      }
    }, 650);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [form, formError]);

  const update = useCallback((next: FormState | ((current: FormState) => FormState)) => {
    globalController.current?.abort();
    setGlobalLoading(false);
    setGlobalSensitivity(null);
    setForm((current) => (current === null ? current : typeof next === "function" ? next(current) : next));
  }, []);

  const reset = useCallback(() => {
    if (options) update(initialForm(options));
  }, [options, update]);

  const runGlobalSensitivity = useCallback(async () => {
    if (!form || formError) return;
    globalController.current?.abort();
    const controller = new AbortController();
    globalController.current = controller;
    setGlobalLoading(true);
    try {
      setGlobalSensitivity(await postJson<GlobalSensitivityPayload>("/global-sensitivity", requestBody(form), controller.signal));
    } catch (cause) {
      if (!isAbort(cause)) setError(cause instanceof Error ? cause.message : "Unable to run the full sensitivity test.");
    } finally {
      if (!controller.signal.aborted) setGlobalLoading(false);
    }
  }, [form, formError]);

  const retry = useCallback(() => {
    setLoadError(null);
    setAttempt((value) => value + 1);
  }, []);

  return {
    options,
    form,
    formError,
    result,
    sensitivity,
    globalSensitivity,
    simulating,
    sensitivityLoading,
    globalLoading,
    error,
    loadError,
    update,
    reset,
    retry,
    runGlobalSensitivity,
  };
}
