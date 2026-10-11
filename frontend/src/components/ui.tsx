"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { ChevronDown, Minus, Plus } from "lucide-react";

/** Smoothly tweens to the latest value so live updates feel continuous. */
export function useTweenedNumber(target: number, duration = 650) {
  const [value, setValue] = useState(target);
  const fromRef = useRef(target);
  const valueRef = useRef(target);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      valueRef.current = target;
      const frame = requestAnimationFrame(() => setValue(target));
      return () => cancelAnimationFrame(frame);
    }
    fromRef.current = valueRef.current;
    const start = performance.now();
    let frame = 0;
    const step = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 4);
      const next = fromRef.current + (target - fromRef.current) * eased;
      valueRef.current = next;
      setValue(next);
      if (progress < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target, duration]);

  return value;
}

export function AnimatedNumber({ value, format }: { value: number; format: (value: number) => string }) {
  const tweened = useTweenedNumber(value);
  return <span className="tabular">{format(tweened)}</span>;
}

type SliderProps = {
  label: string;
  hint?: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  display: string;
  baseline?: number;
  baselineLabel?: string;
  onChange: (value: number) => void;
};

export function Slider({ label, hint, value, min, max, step = 1, display, baseline, baselineLabel, onChange }: SliderProps) {
  const id = useId();
  const position = (input: number) => (Math.min(max, Math.max(min, input)) - min) / (max - min);
  // Offset by half a thumb so the fill and marker line up with the thumb centre.
  const along = (fraction: number) => `calc(${fraction * 100}% + ${(0.5 - fraction).toFixed(4)} * var(--thumb))`;
  const fill = along(position(value));
  const mark = baseline === undefined ? null : along(position(baseline));
  return (
    <div className="field">
      <div className="field-row">
        <label htmlFor={id}>{label}</label>
        <output htmlFor={id} className="tabular">{display}</output>
      </div>
      <div className="slider" style={{ "--fill-at": fill } as React.CSSProperties}>
        {mark !== null && <span className="slider-mark" style={{ left: mark }} title={baselineLabel} />}
        <input id={id} type="range" min={min} max={max} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} />
      </div>
      {hint && <p className="field-hint">{hint}</p>}
    </div>
  );
}

type StepperProps = {
  label: string;
  hint?: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
};

export function Stepper({ label, hint, value, min, max, onChange }: StepperProps) {
  const id = useId();
  const [draft, setDraft] = useState(() => formatDraft(value));
  const [focused, setFocused] = useState(false);
  const shown = focused ? draft : formatDraft(value);

  const commit = (next: number) => onChange(Math.min(max, Math.max(min, Math.round(next * 10) / 10)));

  return (
    <div className="field">
      <div className="field-row"><label htmlFor={id}>{label}</label></div>
      <div className="stepper">
        <button type="button" aria-label={`Decrease ${label.toLowerCase()}`} onClick={() => commit(value - 1)} disabled={value <= min}><Minus size={16} /></button>
        <input
          id={id}
          inputMode="decimal"
          className="tabular"
          value={shown}
          onFocus={() => { setDraft(formatDraft(value)); setFocused(true); }}
          onChange={(event) => {
            setDraft(event.target.value);
            const parsed = Number(event.target.value);
            if (event.target.value.trim() !== "" && Number.isFinite(parsed) && parsed >= min && parsed <= max) onChange(parsed);
          }}
          onBlur={() => {
            setFocused(false);
            const parsed = Number(draft);
            if (Number.isFinite(parsed) && draft.trim() !== "") commit(parsed);
          }}
          onKeyDown={(event) => { if (event.key === "Enter") (event.target as HTMLInputElement).blur(); }}
        />
        <button type="button" aria-label={`Increase ${label.toLowerCase()}`} onClick={() => commit(value + 1)} disabled={value >= max}><Plus size={16} /></button>
      </div>
      {hint && <p className="field-hint">{hint}</p>}
    </div>
  );
}

function formatDraft(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

type SelectProps = {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
};

export function Select({ label, value, options, onChange }: SelectProps) {
  const id = useId();
  return (
    <div className="field">
      <div className="field-row"><label htmlFor={id}>{label}</label></div>
      <div className="select">
        <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
          {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        <ChevronDown size={16} aria-hidden="true" />
      </div>
    </div>
  );
}

export function Segmented<T extends string>({ label, value, options, onChange }: {
  label: string;
  value: T;
  options: Array<{ value: T; label: string }>;
  onChange: (value: T) => void;
}) {
  const index = Math.max(0, options.findIndex((option) => option.value === value));
  return (
    <div className="segmented" role="radiogroup" aria-label={label} style={{ "--index": index, "--count": options.length } as React.CSSProperties}>
      <span className="segmented-thumb" aria-hidden="true" />
      {options.map((option) => (
        <button key={option.value} type="button" role="radio" aria-checked={option.value === value} onClick={() => onChange(option.value)}>
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function Card({ title, subtitle, action, children, className }: {
  title: string;
  subtitle?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className ?? ""}`}>
      <header className="card-head">
        <div>
          <h3>{title}</h3>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}
