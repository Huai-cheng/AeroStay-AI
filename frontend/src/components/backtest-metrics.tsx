"use client";

import { useEffect, useState } from "react";

import { percent } from "@/lib/format";
import type { OptionsPayload, SimulationPayload } from "@/lib/types";
import { API, initialForm, requestBody } from "@/lib/use-scenario";

type Metrics = SimulationPayload["metrics"];

const SCOPES = [
  { key: "combined", label: "All hotels" },
  { key: "domestic", label: "Domestic guests" },
  { key: "international", label: "International guests" },
];

/** Reads the held-out metrics from the live service so the page never drifts from the model. */
export function BacktestMetrics() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const options: OptionsPayload = await fetch(`${API}/options`, { signal: controller.signal }).then((response) => {
          if (!response.ok) throw new Error();
          return response.json();
        });
        const result: SimulationPayload = await fetch(`${API}/simulate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(requestBody(initialForm(options))),
          signal: controller.signal,
        }).then((response) => {
          if (!response.ok) throw new Error();
          return response.json();
        });
        setMetrics(result.metrics);
      } catch (cause) {
        if (!(cause instanceof DOMException && cause.name === "AbortError")) setFailed(true);
      }
    })();
    return () => controller.abort();
  }, []);

  return (
    <div className="metric-row">
      {SCOPES.map((scope) => {
        const value = metrics?.[scope.key];
        return (
          <div key={scope.key} className="metric">
            <span>{scope.label}</span>
            <b className="tabular">{value ? percent(value.wmape, 1) : failed ? "—" : "…"}</b>
            <small className="tabular">{value ? `Bias ${value.bias_pct >= 0 ? "+" : "−"}${percent(Math.abs(value.bias_pct), 1)}` : failed ? "Service offline" : "Loading"}</small>
          </div>
        );
      })}
    </div>
  );
}
