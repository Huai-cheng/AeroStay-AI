"""Interactive DCT flight-to-hotel scenario simulator."""

# AI/MAINTAINER PARITY RULE:
# Any scenario-control change in this Streamlit app must be made in
# frontend/src/components/scenario-app.tsx in the same task, with the shared
# API, tests, README files, and UI_SCENARIO_PARITY.md kept synchronized.

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from prototype.service import global_sensitivity

from pipeline.modeling import (
    ARTIFACT_DIR,
    MODEL_FEATURES,
    build_features,
    load_hotel_data,
    load_model,
    predict_with_model,
)
from scenario_engine import (
    ScenarioInputs,
    aggregate_origin_baseline,
    available_origins,
    distribute_arrival_delta,
    load_flights,
    scenario_record,
    scenario_chain,
)


ROOT = Path(__file__).resolve().parents[1]
st.set_page_config(
    page_title="DCT Flight-to-Hotel Planner",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --ink: #EAF2FF;
        --muted: #95A6BD;
        --panel: rgba(14, 28, 49, .86);
        --panel-strong: #10213A;
        --line: rgba(148, 163, 184, .18);
        --teal: #2DD4BF;
        --cyan: #38BDF8;
        --purple: #8B5CF6;
        --amber: #F59E0B;
    }
    .stApp {
        background:
          radial-gradient(circle at 78% 0%, rgba(56,189,248,.10), transparent 31rem),
          radial-gradient(circle at 12% 12%, rgba(139,92,246,.09), transparent 26rem),
          #07111F;
        color: var(--ink);
    }
    [data-testid="stAppViewContainer"] > .main .block-container {
        max-width: 1440px;
        padding-top: 1.4rem;
        padding-bottom: 4rem;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0C1729 0%, #101D32 100%);
        border-right: 1px solid var(--line);
    }
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: .72rem; }
    [data-testid="stSidebar"] hr { border-color: var(--line); }
    #MainMenu, footer, [data-testid="stStatusWidget"], [data-testid="stToolbar"], .stDeployButton { visibility: hidden; }
    .hero {
        position: relative;
        overflow: hidden;
        padding: 2rem 2.2rem;
        margin-bottom: 1.15rem;
        border: 1px solid rgba(56,189,248,.20);
        border-radius: 24px;
        background: linear-gradient(118deg, rgba(16,33,58,.98), rgba(12,27,48,.92));
        box-shadow: 0 20px 60px rgba(0,0,0,.24);
    }
    .hero::after {
        content: "";
        position: absolute;
        width: 330px; height: 330px;
        right: -120px; top: -190px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(45,212,191,.25), transparent 68%);
    }
    .eyebrow {
        color: var(--teal); font-size: .76rem; font-weight: 750;
        letter-spacing: .14em; text-transform: uppercase;
    }
    .hero h1 { margin: .35rem 0 .5rem; font-size: clamp(2rem, 4vw, 3.5rem); line-height: 1.03; }
    .hero p { max-width: 790px; color: #B8C5D8; font-size: 1.02rem; margin: 0; }
    .hero-badge {
        display: inline-flex; align-items: center; gap: .42rem;
        margin-top: 1.15rem; padding: .42rem .72rem;
        border-radius: 999px; border: 1px solid rgba(45,212,191,.25);
        color: #BFFCF2; background: rgba(45,212,191,.08); font-size: .78rem;
    }
    .workflow {
        display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .7rem;
        margin: 0 0 1.25rem;
    }
    .workflow-step {
        padding: .8rem 1rem; border: 1px solid var(--line); border-radius: 14px;
        background: rgba(14,28,49,.72); color: #AFC0D4; font-size: .84rem;
    }
    .workflow-step b { color: var(--ink); margin-right: .35rem; }
    .workflow-step.active { border-color: rgba(45,212,191,.38); background: rgba(45,212,191,.07); }
    .sidebar-brand { padding: .25rem 0 .4rem; }
    .sidebar-brand strong { font-size: 1.08rem; color: white; }
    .sidebar-brand span { display: block; color: var(--muted); font-size: .78rem; margin-top: .15rem; }
    .section-kicker {
        margin: .6rem 0 -.15rem; color: var(--teal); font-size: .70rem;
        font-weight: 800; text-transform: uppercase; letter-spacing: .13em;
    }
    [data-testid="stMetric"] {
        min-height: 132px; padding: 1rem 1.05rem;
        background: linear-gradient(145deg, rgba(16,33,58,.96), rgba(11,24,42,.92));
        border: 1px solid var(--line); border-radius: 17px;
        box-shadow: 0 12px 30px rgba(0,0,0,.12);
    }
    [data-testid="stMetricLabel"] { color: #A9B7C9; }
    [data-testid="stMetricValue"] { color: #F7FBFF; letter-spacing: -.035em; }
    [data-testid="stMetricDelta"] { font-weight: 700; }
    [data-baseweb="tab-list"] {
        gap: .35rem; background: rgba(10,22,39,.64); padding: .35rem;
        border: 1px solid var(--line); border-radius: 14px;
    }
    [data-baseweb="tab"] { border-radius: 10px; padding-left: 1rem; padding-right: 1rem; }
    [aria-selected="true"][data-baseweb="tab"] { background: rgba(45,212,191,.11); }
    .decision-card {
        padding: 1.2rem 1.35rem; margin: .9rem 0 1rem;
        border-radius: 16px; border: 1px solid rgba(45,212,191,.27);
        border-left: 4px solid var(--teal); background: rgba(45,212,191,.055);
    }
    .decision-card .label { color: var(--teal); text-transform: uppercase; letter-spacing: .12em; font-size: .7rem; font-weight: 800; }
    .decision-card .value { color: #F3FAFF; font-size: 1.05rem; line-height: 1.55; margin-top: .35rem; }
    .range-strip {
        display: flex; justify-content: space-between; gap: 1rem; align-items: center;
        padding: .78rem 1rem; margin: .65rem 0 1rem; border-radius: 12px;
        border: 1px solid rgba(56,189,248,.20); background: rgba(56,189,248,.055);
        color: #B9C9DB; font-size: .84rem;
    }
    .range-strip b { color: white; }
    .context-strip {
        display: flex; flex-wrap: wrap; gap: .5rem; margin: 0 0 1.1rem;
    }
    .context-pill {
        padding: .42rem .68rem; border-radius: 999px; background: rgba(148,163,184,.08);
        border: 1px solid var(--line); color: #C7D3E3; font-size: .76rem;
    }
    .context-pill b { color: white; }
    .stButton > button, .stDownloadButton > button {
        border-radius: 11px; border-color: rgba(56,189,248,.26); min-height: 2.8rem;
    }
    .stDownloadButton > button:hover { border-color: var(--teal); color: var(--teal); }
    [data-testid="stDataFrame"], [data-testid="stPlotlyChart"] {
        border: 1px solid var(--line); border-radius: 16px; overflow: hidden;
    }
    .method-note { color: var(--muted); font-size: .78rem; line-height: 1.5; }
    @media (max-width: 800px) {
        .workflow { grid-template-columns: 1fr; }
        .hero { padding: 1.5rem; }
        .range-strip { display: block; }
        .range-strip span { display: block; }
        .range-strip span + span { margin-top: .35rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def cached_model():
    return load_model()


@st.cache_data
def cached_data():
    train, test = load_hotel_data()
    flights = load_flights()
    metadata = json.loads((ARTIFACT_DIR / "model_metadata.json").read_text(encoding="utf-8"))
    metrics = json.loads((ARTIFACT_DIR / "holdout_metrics.json").read_text(encoding="utf-8"))
    return train, test, flights, metadata, metrics


def predict_frame(model, train, raw_test):
    features = build_features(
        raw_test,
        train,
        origin_date=train["date"].min(),
    )
    prediction = predict_with_model(model, features)
    output = features[
        ["date", "segment", "market", "new_arrivals", "same_day_guests", "same_day_missing"]
    ].copy()
    output["predicted_guests"] = prediction
    output["predicted_guest_nights"] = np.clip(
        output["predicted_guests"] - output["same_day_guests"].fillna(0),
        0.0,
        None,
    )
    return output


def fmt_count(value: float) -> str:
    return f"{value:,.0f}"


def pct_change(scenario: float, baseline: float) -> float:
    return (scenario - baseline) / baseline if baseline else 0.0


def style_figure(figure: go.Figure, *, height: int = 430) -> go.Figure:
    """Apply the shared presentation theme without altering plotted values."""
    figure.update_layout(
        height=height,
        margin=dict(l=24, r=24, t=62, b=28),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#C9D5E5", family="Inter, Segoe UI, sans-serif"),
        title_font=dict(color="#F4F8FF", size=18),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0)",
        ),
        hoverlabel=dict(bgcolor="#10213A", font_color="#F4F8FF"),
    )
    figure.update_xaxes(showgrid=False, zeroline=False, linecolor="rgba(148,163,184,.16)")
    figure.update_yaxes(gridcolor="rgba(148,163,184,.10)", zeroline=False)
    return figure


def scenario_prediction(model, train, raw_test, inputs, chain):
    adjusted = distribute_arrival_delta(
        raw_test,
        inputs.target_nationality,
        inputs.start_date,
        inputs.end_date,
        chain["allocated_arrival_delta"],
    )
    return predict_frame(model, train, adjusted)


def selected_total(frame: pd.DataFrame, inputs: ScenarioInputs, column: str) -> float:
    mask = frame["date"].between(inputs.start_date, inputs.end_date)
    return float(frame.loc[mask, column].sum())


def selected_market_total(frame: pd.DataFrame, inputs: ScenarioInputs, column: str) -> float:
    mask = (
        frame["date"].between(inputs.start_date, inputs.end_date)
        & frame["segment"].eq("International")
        & frame["market"].eq(inputs.target_nationality)
    )
    return float(frame.loc[mask, column].sum())


def sensitivity_table(model, train, raw_test, baseline_prediction, baseline_flight, inputs):
    levers = [
        ("Weekly frequency", "frequency_change_pct", 10.0),
        ("Seats per flight", "seats_per_flight_change_pct", 10.0),
        ("Load factor", "load_factor_change_points", 5.0),
        ("Transfer share", "transfer_share", 0.05),
        ("Visitor share", "visitor_share", 0.10),
        ("Hotel capture", "hotel_capture_rate", 0.10),
    ]
    rows = []
    base_total = selected_market_total(
        baseline_prediction, inputs, "predicted_guest_nights"
    )
    base_values = inputs.__dict__.copy()
    for label, field, step in levers:
        low_values = base_values.copy()
        high_values = base_values.copy()
        if field in {"transfer_share", "visitor_share", "hotel_capture_rate"}:
            low_values[field] = max(0.0, base_values[field] - step)
            high_values[field] = min(0.95, base_values[field] + step)
        else:
            low_values[field] = base_values[field] - step
            high_values[field] = base_values[field] + step
        low_inputs = ScenarioInputs(**low_values)
        high_inputs = ScenarioInputs(**high_values)
        if low_inputs.transfer_share + low_inputs.transit_share >= 0.98:
            continue
        if high_inputs.transfer_share + high_inputs.transit_share >= 0.98:
            continue
        low_chain = scenario_chain(baseline_flight, low_inputs)
        high_chain = scenario_chain(baseline_flight, high_inputs)
        low_prediction = scenario_prediction(
            model, train, raw_test, low_inputs, low_chain
        )
        high_prediction = scenario_prediction(
            model, train, raw_test, high_inputs, high_chain
        )
        low_total = selected_market_total(
            low_prediction, low_inputs, "predicted_guest_nights"
        )
        high_total = selected_market_total(
            high_prediction, high_inputs, "predicted_guest_nights"
        )
        rows.append(
            {
                "Lever": label,
                "Low impact": low_total - base_total,
                "High impact": high_total - base_total,
                "Range": max(low_total, high_total) - min(low_total, high_total),
            }
        )
    return pd.DataFrame(rows).sort_values("Range", ascending=True)


required = [
    ARTIFACT_DIR / "pooled_poisson_xgboost.joblib",
    ARTIFACT_DIR / "model_metadata.json",
    ARTIFACT_DIR / "holdout_metrics.json",
]
if not all(path.exists() for path in required):
    st.error("Model artifacts are missing. Run the training command first.")
    st.code(r".\.venv\Scripts\python.exe prototype\train_models.py")
    st.stop()

model = cached_model()
train_raw, test_raw, flights, metadata, holdout_metrics = cached_data()
baseline_prediction = predict_frame(model, train_raw, test_raw)

st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">DCT Abu Dhabi · Decision intelligence prototype</div>
      <h1>Flight-to-Hotel Planner</h1>
      <p>Translate aviation capacity changes into an explainable hotel-demand scenario—by market, season and every conversion assumption in between.</p>
      <div class="hero-badge">● Pooled Poisson XGBoost online &nbsp;·&nbsp; Transparent scenario engine</div>
    </div>
    <div class="workflow">
      <div class="workflow-step active"><b>01</b> Define the aviation scenario</div>
      <div class="workflow-step"><b>02</b> Simulate the conversion chain</div>
      <div class="workflow-step"><b>03</b> Decide with evidence</div>
    </div>
    """,
    unsafe_allow_html=True,
)

international_markets = sorted(
    test_raw.loc[test_raw["segment"].eq("International"), "market"].unique().tolist()
)
origins = available_origins(flights)
minimum_date = test_raw["date"].min().date()
maximum_date = test_raw["date"].max().date()

with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
          <div class="eyebrow">Scenario studio</div>
          <strong>Build a planning case</strong>
          <span>Adjust one lever or combine several changes.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    presentation_mode = st.toggle(
        "Presentation mode",
        value=False,
        help="Uses cleaner output language for screenshots and demonstrations.",
    )
    st.markdown('<div class="section-kicker">01 · Scope</div>', unsafe_allow_html=True)
    mode = st.radio("Route mode", ["Existing route", "New route"], horizontal=True)
    start_date = pd.Timestamp(
        st.date_input("Start date", value=minimum_date, min_value=minimum_date, max_value=maximum_date)
    )
    end_date = pd.Timestamp(
        st.date_input("End date", value=maximum_date, min_value=minimum_date, max_value=maximum_date)
    )
    if start_date > end_date:
        st.error("Start date must not be after end date.")
        st.stop()

    if mode == "Existing route":
        origin_country = st.selectbox("Aviation departure origin", origins)
    else:
        unserved = [market for market in international_markets if market not in origins]
        origin_country = st.selectbox(
            "New route origin",
            unserved if unserved else international_markets,
        )

    default_market = origin_country if origin_country in international_markets else international_markets[0]
    target_nationality = st.selectbox(
        "Hotel nationality receiving the incremental arrivals",
        international_markets,
        index=international_markets.index(default_market),
        help="Departure origin and guest nationality are different concepts. This selection makes the bridge explicit.",
    )

    baseline_flight = aggregate_origin_baseline(
        flights, origin_country, start_date, end_date
    )

    st.markdown('<div class="section-kicker">02 · Aviation levers</div>', unsafe_allow_html=True)
    if mode == "Existing route":
        baseline_weekly_flights = float(baseline_flight["average_weekly_frequency"])
        scenario_weekly_flights = st.number_input(
            "Weekly flights",
            min_value=0.0,
            max_value=1000.0,
            value=float(round(baseline_weekly_flights + 2.0, 1)),
            step=1.0,
            help=f"Observed baseline for the selected route and period: {baseline_weekly_flights:.1f} weekly flights.",
        )
        frequency_change = (
            (float(scenario_weekly_flights) / baseline_weekly_flights - 1.0) * 100.0
            if baseline_weekly_flights > 0
            else 0.0
        )
        seat_change = st.slider("Seats per flight change", -40, 60, 0, 5, format="%d%%")
        load_change = st.slider("Load-factor change", -20, 20, 0, 1, format="%d pp")
        new_weekly_flights = 0.0
        new_seats_per_flight = 0.0
        new_load_factor = 0.0
    else:
        new_weekly_flights = st.number_input("Weekly flights", 0.0, 100.0, 2.0, 1.0)
        new_seats_per_flight = st.number_input("Seats per flight", 50.0, 600.0, 180.0, 10.0)
        new_load_factor = st.slider("Expected load factor", 0.30, 1.00, 0.75, 0.01)
        frequency_change = 0.0
        seat_change = 0.0
        load_change = 0.0

    st.markdown('<div class="section-kicker">03 · Conversion assumptions</div>', unsafe_allow_html=True)
    default_transfer = min(0.90, baseline_flight["transfer_share"] if mode == "Existing route" else 0.20)
    default_transit = min(0.20, baseline_flight["transit_share"] if mode == "Existing route" else 0.02)
    transfer_share = st.slider("Transfer share", 0.0, 0.90, float(round(default_transfer, 2)), 0.01)
    transit_share = st.slider("Transit share", 0.0, 0.25, float(round(default_transit, 2)), 0.01)
    visitor_share = st.slider(
        "Visitor share of destination passengers",
        0.20,
        1.00,
        0.75,
        0.01,
        help="Assumption: this field is not supplied in the local data.",
    )
    hotel_capture = st.slider(
        "Hotel-capture rate",
        0.10,
        1.00,
        0.65,
        0.01,
        help="Assumption: share of visitors expected to use hotels.",
    )
    allocation_share = st.slider(
        "Origin-to-nationality allocation",
        0.10,
        1.00,
        1.00 if origin_country == target_nationality else 0.50,
        0.05,
        help="Share of incremental hotel arrivals assigned to the selected hotel nationality.",
    )

if transfer_share + transit_share >= 0.98:
    st.error("Transfer and transit shares must sum to less than 98%.")
    st.stop()

inputs = ScenarioInputs(
    mode=mode,
    origin_country=origin_country,
    target_nationality=target_nationality,
    start_date=start_date,
    end_date=end_date,
    frequency_change_pct=float(frequency_change),
    seats_per_flight_change_pct=float(seat_change),
    load_factor_change_points=float(load_change),
    transfer_share=float(transfer_share),
    transit_share=float(transit_share),
    visitor_share=float(visitor_share),
    hotel_capture_rate=float(hotel_capture),
    nationality_allocation_share=float(allocation_share),
    new_route_weekly_flights=float(new_weekly_flights),
    new_route_seats_per_flight=float(new_seats_per_flight),
    new_route_load_factor=float(new_load_factor),
)

service_payload = {
    "mode": mode,
    "origin_country": origin_country,
    "target_nationality": target_nationality,
    "start_date": str(start_date.date()),
    "end_date": str(end_date.date()),
    "scenario_weekly_flights": float(scenario_weekly_flights) if mode == "Existing route" else None,
    "seats_per_flight_change_pct": float(seat_change),
    "load_factor_change_points": float(load_change),
    "transfer_share": float(transfer_share),
    "transit_share": float(transit_share),
    "visitor_share": float(visitor_share),
    "hotel_capture_rate": float(hotel_capture),
    "nationality_allocation_share": float(allocation_share),
    "new_route_weekly_flights": float(new_weekly_flights),
    "new_route_seats_per_flight": float(new_seats_per_flight),
    "new_route_load_factor": float(new_load_factor),
}

central_chain = scenario_chain(baseline_flight, inputs)
scenario_prediction_frame = scenario_prediction(
    model, train_raw, test_raw, inputs, central_chain
)

low_chain = scenario_chain(
    baseline_flight,
    inputs,
    visitor_share=max(0.0, visitor_share - 0.10),
    hotel_capture_rate=max(0.0, hotel_capture - 0.10),
)
high_chain = scenario_chain(
    baseline_flight,
    inputs,
    visitor_share=min(1.0, visitor_share + 0.10),
    hotel_capture_rate=min(1.0, hotel_capture + 0.10),
)
low_prediction_frame = scenario_prediction(model, train_raw, test_raw, inputs, low_chain)
high_prediction_frame = scenario_prediction(model, train_raw, test_raw, inputs, high_chain)

baseline_guests = selected_total(baseline_prediction, inputs, "predicted_guests")
scenario_guests = selected_total(scenario_prediction_frame, inputs, "predicted_guests")
baseline_nights = selected_total(baseline_prediction, inputs, "predicted_guest_nights")
scenario_nights = selected_total(scenario_prediction_frame, inputs, "predicted_guest_nights")
assumption_low = selected_total(low_prediction_frame, inputs, "predicted_guest_nights")
assumption_high = selected_total(high_prediction_frame, inputs, "predicted_guest_nights")
combined_wmape = holdout_metrics["combined"]["wmape"]
planning_low = max(0.0, min(assumption_low, assumption_high) * (1.0 - combined_wmape))
planning_high = max(assumption_low, assumption_high) * (1.0 + combined_wmape)

scenario_checks: list[tuple[str, str]] = []
if mode == "New route":
    scenario_checks.append(
        (
            "warning",
            "New-route estimate: this route has no direct historical flight record in the selected period. "
            "The result uses pooled XGBoost behavior and a wider planning range.",
        )
    )
else:
    historical_origin = flights[
        flights["Origin Key"].eq(origin_country)
        & flights["Date"].between(pd.Timestamp("2023-01-01"), pd.Timestamp("2025-07-31"))
    ].copy()
    if not historical_origin.empty:
        historical_lf_min = float(historical_origin["Load Factor"].min())
        historical_lf_max = float(historical_origin["Load Factor"].max())
        if not historical_lf_min <= central_chain["scenario_load_factor"] <= historical_lf_max:
            scenario_checks.append(
                (
                    "warning",
                    f"Scenario load factor {central_chain['scenario_load_factor']:.1%} is outside the "
                    f"observed origin range {historical_lf_min:.1%}–{historical_lf_max:.1%}.",
                )
            )
        historical_daily_seats = historical_origin.groupby("Date")["Total Seats"].sum()
        scenario_daily_seats = central_chain["scenario_seats"] / max(
            1, (end_date - start_date).days + 1
        )
        if scenario_daily_seats > float(historical_daily_seats.max()) * 1.10:
            scenario_checks.append(
                (
                    "warning",
                    "Scenario daily seats exceed the selected origin's observed historical maximum by more than 10%.",
                )
            )
if origin_country != target_nationality:
    scenario_checks.append(
        (
            "info",
            "The aviation origin and hotel nationality differ. The allocation control is an explicit assumption, "
            "not an observed passenger-nationality mapping.",
        )
    )
if baseline_prediction.loc[
    baseline_prediction["date"].between(start_date, end_date), "same_day_missing"
].sum() > 0:
    scenario_checks.append(
        (
            "info",
            "Some international same-day values are suppressed or unavailable. Guest nights use zero for the "
            "point estimate and the planning range should be treated as more reliable than a single value.",
        )
    )

st.markdown(
    f"""
    <div class="context-strip">
      <span class="context-pill"><b>{mode}</b></span>
      <span class="context-pill">Origin · <b>{origin_country}</b></span>
      <span class="context-pill">Hotel market · <b>{target_nationality}</b></span>
      <span class="context-pill">Period · <b>{start_date:%d %b %Y}–{end_date:%d %b %Y}</b></span>
      <span class="context-pill">Checks · <b>{len(scenario_checks)}</b></span>
    </div>
    """,
    unsafe_allow_html=True,
)

if scenario_checks:
    with st.expander(
        f"Scenario checks and assumptions ({len(scenario_checks)})",
        expanded=not presentation_mode and any(level == "warning" for level, _ in scenario_checks),
    ):
        for level, message in scenario_checks:
            if level == "warning":
                st.warning(message)
            else:
                st.info(message)

tab_overview, tab_chain, tab_markets, tab_validation = st.tabs(
    ["Overview", "Conversion", "Markets", "Evidence"]
)

with tab_overview:
    selected_baseline = selected_market_total(
        baseline_prediction, inputs, "predicted_guest_nights"
    )
    selected_scenario = selected_market_total(
        scenario_prediction_frame, inputs, "predicted_guest_nights"
    )
    selected_delta = selected_scenario - selected_baseline
    if selected_delta > 0:
        action = "prepare capacity and market activation for additional hotel demand"
        direction = "increase"
    elif selected_delta < 0:
        action = "review exposure and adjust the hotel-demand plan"
        direction = "decrease"
    else:
        action = "maintain the current demand plan"
        direction = "no material change"

    c1, c2 = st.columns(2)
    c1.metric("Baseline guests", fmt_count(baseline_guests))
    c2.metric(
        "Scenario guests",
        fmt_count(scenario_guests),
        delta=fmt_count(scenario_guests - baseline_guests),
    )
    c3, c4 = st.columns(2)
    c3.metric("Baseline guest nights", fmt_count(baseline_nights))
    c4.metric(
        "Scenario guest nights",
        fmt_count(scenario_nights),
        delta=f"{fmt_count(scenario_nights - baseline_nights)} ({pct_change(scenario_nights, baseline_nights):+.1%})",
    )
    st.markdown(
        f"""
        <div class="range-strip">
          <span>Planning range · <b>{fmt_count(planning_low)}–{fmt_count(planning_high)} guest nights</b></span>
          <span>Holdout WMAPE · <b>{combined_wmape:.1%}</b></span>
        </div>
        <div class="decision-card">
          <div class="label">Planner decision</div>
          <div class="value">The selected hotel market shows <b>{direction}</b> of <b>{selected_delta:+,.0f} guest nights</b>. DCT should <b>{action}</b>, subject to the visible conversion assumptions.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    mask = baseline_prediction["date"].between(start_date, end_date)
    baseline_daily = (
        baseline_prediction.loc[mask]
        .groupby("date", as_index=False)["predicted_guest_nights"]
        .sum()
        .rename(columns={"predicted_guest_nights": "Baseline"})
    )
    scenario_daily = (
        scenario_prediction_frame.loc[mask]
        .groupby("date", as_index=False)["predicted_guest_nights"]
        .sum()
        .rename(columns={"predicted_guest_nights": "Scenario"})
    )
    daily = baseline_daily.merge(scenario_daily, on="date").melt(
        id_vars="date", var_name="Series", value_name="Guest nights"
    )
    figure = px.line(
        daily,
        x="date",
        y="Guest nights",
        color="Series",
        color_discrete_map={"Baseline": "#64748B", "Scenario": "#7C3AED"},
        title="Daily hotel guest nights",
    )
    figure.update_layout(legend_title_text="", hovermode="x unified")
    style_figure(figure, height=390)
    st.plotly_chart(figure, width="stretch", config={"displaylogo": False})

    st.markdown(
        '<div class="method-note">Planning range combines ±10 percentage-point visitor/capture assumptions with held-out WMAPE. It is a scenario range, not a formal causal interval.</div>',
        unsafe_allow_html=True,
    )

    export_record = scenario_record(inputs, central_chain)
    export_record.update(
        {
            "baseline_predicted_guests": baseline_guests,
            "scenario_predicted_guests": scenario_guests,
            "baseline_guest_nights": baseline_nights,
            "scenario_guest_nights": scenario_nights,
            "planning_range_low": planning_low,
            "planning_range_high": planning_high,
        }
    )
    download_left, download_right = st.columns(2)
    download_left.download_button(
        "Download scenario summary",
        data=json.dumps(export_record, indent=2),
        file_name="dct_scenario_summary.json",
        mime="application/json",
        width="stretch",
    )
    download_right.download_button(
        "Download daily comparison",
        data=baseline_daily.merge(scenario_daily, on="date").to_csv(index=False),
        file_name="dct_scenario_daily.csv",
        mime="text/csv",
        width="stretch",
    )

with tab_chain:
    chain_table = pd.DataFrame(
        {
            "Stage": [
                "Scheduled seats",
                "Passenger movements",
                "Destination passengers",
                "Visitors",
                "Hotel guest arrivals",
                "Predicted guest nights",
            ],
            "Baseline": [
                central_chain["baseline_seats"],
                central_chain["baseline_passengers"],
                central_chain["baseline_destination_passengers"],
                central_chain["baseline_visitors"],
                central_chain["baseline_hotel_arrivals"],
                selected_market_total(baseline_prediction, inputs, "predicted_guest_nights"),
            ],
            "Scenario": [
                central_chain["scenario_seats"],
                central_chain["scenario_passengers"],
                central_chain["scenario_destination_passengers"],
                central_chain["scenario_visitors"],
                central_chain["scenario_hotel_arrivals"],
                selected_market_total(
                    scenario_prediction_frame, inputs, "predicted_guest_nights"
                ),
            ],
        }
    )
    chain_table["Change"] = chain_table["Scenario"] - chain_table["Baseline"]
    st.markdown("## Conversion chain")
    st.caption("Every stage is inspectable; scenario values reconcile from aviation supply to the hotel-demand output.")
    st.dataframe(
        chain_table.style.format({"Baseline": "{:,.0f}", "Scenario": "{:,.0f}", "Change": "{:+,.0f}"}),
        width="stretch",
        hide_index=True,
    )
    chain_chart = px.bar(
        chain_table.melt(id_vars="Stage", value_vars=["Baseline", "Scenario"]),
        x="Stage",
        y="value",
        color="variable",
        barmode="group",
        labels={"value": "People / guest nights", "variable": "Series"},
        color_discrete_map={"Baseline": "#64748B", "Scenario": "#7C3AED"},
    )
    style_figure(chain_chart, height=410)
    st.plotly_chart(chain_chart, width="stretch", config={"displaylogo": False})
    with st.expander("Formulas and assumptions", expanded=True):
        st.latex(r"Seats=Flights\times SeatsPerFlight")
        st.latex(r"Passengers=Seats\times LoadFactor")
        st.latex(r"DestinationPassengers=Passengers\times(1-TransferShare-TransitShare)")
        st.latex(r"Visitors=DestinationPassengers\times VisitorShare")
        st.latex(r"HotelArrivals=Visitors\times HotelCaptureRate")
        st.latex(r"GuestNights=PredictedGuests-SameDayGuests")
        st.caption(
            "Visitor share, hotel capture, and origin-to-nationality allocation are assumptions because the local data does not provide them."
        )

    if st.checkbox("Calculate one-at-a-time sensitivity", value=False):
        with st.spinner("Evaluating scenario levers..."):
            sensitivity = sensitivity_table(
                model,
                train_raw,
                test_raw,
                baseline_prediction,
                baseline_flight,
                inputs,
            )
        sensitivity_chart = go.Figure()
        sensitivity_chart.add_bar(
            y=sensitivity["Lever"],
            x=sensitivity["Low impact"],
            orientation="h",
            name="Low setting",
            marker_color="#64748B",
        )
        sensitivity_chart.add_bar(
            y=sensitivity["Lever"],
            x=sensitivity["High impact"],
            orientation="h",
            name="High setting",
            marker_color="#7C3AED",
        )
        sensitivity_chart.update_layout(
            barmode="group",
            title="Change in selected-market guest nights",
            xaxis_title="Change from baseline",
            yaxis_title="",
        )
        style_figure(sensitivity_chart, height=430)
        st.plotly_chart(sensitivity_chart, width="stretch", config={"displaylogo": False})
        st.dataframe(sensitivity, width="stretch", hide_index=True)

    st.markdown("### SALib Morris global sensitivity")
    st.caption(
        "Morris varies all scenario levers together across plausible bounds. "
        "Overall influence (μ*) ranks impact; sigma flags interactions or non-linear behavior."
    )
    if st.button("Run global sensitivity", type="secondary"):
        with st.spinner("Running SALib Morris model evaluations..."):
            morris_result = global_sensitivity(service_payload)
        morris_frame = pd.DataFrame(morris_result["drivers"])
        morris_chart = px.bar(
            morris_frame.sort_values("relative_importance"),
            x="relative_importance",
            y="driver",
            orientation="h",
            labels={"relative_importance": "Relative influence", "driver": "Scenario lever"},
            color="sigma",
            color_continuous_scale=["#38BDF8", "#8B5CF6"],
            title="All levers varied together",
        )
        morris_chart.update_xaxes(tickformat=".0%")
        style_figure(morris_chart, height=480)
        st.plotly_chart(morris_chart, width="stretch", config={"displaylogo": False})
        st.dataframe(
            morris_frame[["rank", "driver", "bounds", "relative_importance", "mu_star", "sigma"]]
            .rename(columns={
                "rank": "Rank",
                "driver": "Lever",
                "bounds": "Analysis bounds",
                "relative_importance": "Relative influence",
                "mu_star": "Overall influence (μ*)",
                "sigma": "Interaction / non-linearity (σ)",
            })
            .style.format({"Relative influence": "{:.1%}", "Overall influence (μ*)": "{:,.0f}", "Interaction / non-linearity (σ)": "{:,.0f}"}),
            width="stretch",
            hide_index=True,
        )
        st.caption(f'{morris_result["evaluations"]} full model evaluations. {morris_result["interpretation"]}')

with tab_markets:
    period_mask = baseline_prediction["date"].between(start_date, end_date)
    baseline_market = (
        baseline_prediction.loc[period_mask]
        .groupby(["segment", "market"], as_index=False)["predicted_guest_nights"]
        .sum()
        .rename(columns={"predicted_guest_nights": "Baseline"})
    )
    scenario_market = (
        scenario_prediction_frame.loc[period_mask]
        .groupby(["segment", "market"], as_index=False)["predicted_guest_nights"]
        .sum()
        .rename(columns={"predicted_guest_nights": "Scenario"})
    )
    market_table = baseline_market.merge(scenario_market, on=["segment", "market"])
    market_table["Change"] = market_table["Scenario"] - market_table["Baseline"]
    market_table["Change %"] = np.where(
        market_table["Baseline"] > 0,
        market_table["Change"] / market_table["Baseline"],
        0.0,
    )
    st.markdown("## Market impact")
    st.caption("Hotel demand is grouped by guest nationality; aviation departure origin remains a separate concept.")
    st.dataframe(
        market_table.sort_values("Change", ascending=False).style.format(
            {"Baseline": "{:,.0f}", "Scenario": "{:,.0f}", "Change": "{:+,.0f}", "Change %": "{:+.1%}"}
        ),
        width="stretch",
        hide_index=True,
    )

    monthly_baseline = baseline_prediction.loc[period_mask].copy()
    monthly_scenario = scenario_prediction_frame.loc[period_mask].copy()
    monthly_baseline["Month"] = monthly_baseline["date"].dt.to_period("M").astype(str)
    monthly_scenario["Month"] = monthly_scenario["date"].dt.to_period("M").astype(str)
    monthly = (
        monthly_baseline.groupby("Month", as_index=False)["predicted_guest_nights"]
        .sum()
        .rename(columns={"predicted_guest_nights": "Baseline"})
        .merge(
            monthly_scenario.groupby("Month", as_index=False)["predicted_guest_nights"]
            .sum()
            .rename(columns={"predicted_guest_nights": "Scenario"}),
            on="Month",
        )
    )
    month_chart = px.bar(
        monthly.melt(id_vars="Month", var_name="Series", value_name="Guest nights"),
        x="Month",
        y="Guest nights",
        color="Series",
        barmode="group",
        color_discrete_map={"Baseline": "#64748B", "Scenario": "#7C3AED"},
        title="Monthly guest nights",
    )
    style_figure(month_chart, height=400)
    st.plotly_chart(month_chart, width="stretch", config={"displaylogo": False})

    st.subheader("Aviation origin view")
    st.write(
        f"Origin: **{origin_country}** · Hotel nationality allocation: **{target_nationality}** · "
        f"Allocated share: **{allocation_share:.0%}**"
    )
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Origin": origin_country,
                    "Baseline seats": central_chain["baseline_seats"],
                    "Scenario seats": central_chain["scenario_seats"],
                    "Baseline passengers": central_chain["baseline_passengers"],
                    "Scenario passengers": central_chain["scenario_passengers"],
                    "Allocated arrival change": central_chain["allocated_arrival_delta"],
                }
            ]
        ).style.format(precision=0, thousands=","),
        width="stretch",
        hide_index=True,
    )

with tab_validation:
    st.markdown("## Model evidence")
    st.caption("Chronological validation only: training observations always precede the holdout period.")
    metric_columns = st.columns(3)
    for column, scope in zip(metric_columns, ["combined", "domestic", "international"]):
        values = holdout_metrics[scope]
        column.metric(f"{scope.title()} WMAPE", f"{values['wmape']:.2%}")
        column.caption(f"Bias {values['bias_pct']:+.2%} · RMSE {values['rmse']:,.0f}")
    st.write(
        "Training ended on **2024-07-31**. The held-out test covers **2024-08-01 through 2025-02-28**, "
        "matching the official 212-day seasonal horizon. Rows were split globally by date."
    )

    st.subheader("Model")
    st.json(
        {
            "approach": metadata["approach"],
            "target": metadata["target"],
            "guest_night_derivation": metadata["guest_night_derivation"],
            "training_period": f"{metadata['train_start']} to {metadata['train_end']}",
            "fitted_estimators": metadata["models"],
        }
    )

    st.subheader("Assumption register")
    assumptions = pd.DataFrame(
        [
            ["Visitor share", f"{visitor_share:.0%}", "Editable; absent from local data"],
            ["Hotel-capture rate", f"{hotel_capture:.0%}", "Editable; absent from local data"],
            ["Origin-to-nationality allocation", f"{allocation_share:.0%}", "Editable bridge assumption"],
            ["Transfer share", f"{transfer_share:.1%}", "Observed baseline or scenario override"],
            ["Transit share", f"{transit_share:.1%}", "Observed baseline or scenario override"],
            ["Same-day missing values", "0 for point estimate", "Suppressed/unavailable values widen uncertainty"],
        ],
        columns=["Assumption", "Current value", "Status"],
    )
    st.dataframe(assumptions, width="stretch", hide_index=True)

    st.subheader("Limitations")
    st.markdown(
        """
        - Scenario effects are conditional estimates, not causal guarantees.
        - Future `New Arrivals` in the challenge test are supplied; a real deployment needs an operational arrivals forecast.
        - The local flight data is monthly in 2022 and daily from 2023 onward.
        - Origin country and hotel nationality are different concepts.
        - The local pack does not contain visitor purpose, hotel capture, average length of stay, occupancy, room supply, events, or public holidays.
        - New-route results use pooled model behavior and require wider uncertainty.
        """
    )
