"""Planner-facing Streamlit interface."""

from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


API_URL = os.environ.get("DTC_API_URL", "http://localhost:8000")


def _get(path: str):
    response = requests.get(API_URL + path, timeout=15)
    response.raise_for_status()
    return response.json()


st.set_page_config(page_title="Air to hotel demand", layout="wide")
st.title("Air to hotel demand")
st.caption("Compare a flight change with the current plan. Estimates are for planning and include explicit assumptions.")

try:
    health = _get("/health")
except requests.RequestException as error:
    st.error(f"The model API is unavailable: {error}")
    st.stop()

if health["status"] != "ready":
    st.warning("No evaluated model is packaged. Run training, evaluation, and packaging first.")
    st.stop()

st.caption(f"Model run: {health['run_id']}")
with st.sidebar.form("scenario"):
    st.subheader("Flight change")
    month = st.text_input("Month (YYYY-MM)", "2025-12")
    country = st.text_input("Flight departure country", "India")
    city = st.text_input("Departure city", "Delhi")
    flights_delta = st.number_input("Change in flights per week", value=2.0, step=1.0)
    seats = st.number_input("Seats per flight", min_value=1, max_value=1000, value=200)
    with st.expander("Conversion assumptions"):
        st.caption("Leave a value blank to use the model's documented estimate.")
        load = st.text_input("Load factor (0–1)", "")
        transfer = st.text_input("Transfer and transit share (0–1)", "")
        visitor = st.text_input("Nonresident visitor share (0–1)", "")
        capture = st.text_input("Hotel conversion share (0–1)", "")
        stay = st.text_input("Average stay proxy (nights)", "")
        origin_share = st.text_input("Same-origin nationality share (0–1)", "")
    submitted = st.form_submit_button("Run scenario", width="stretch")

if not submitted:
    st.info("The example is ready: add two weekly flights from Delhi in December 2025, then select Run scenario.")
    st.stop()

payload = {
    "month": month,
    "departure_country": country,
    "departure_city": city or None,
    "flights_per_week_delta": flights_delta,
    "seats_per_flight": seats,
}
try:
    for field, value in (("load_factor", load), ("transfer_transit_share", transfer),
                         ("nonresident_visitor_share", visitor), ("hotel_capture_rate", capture),
                         ("average_length_of_stay", stay), ("same_origin_nationality_share", origin_share)):
        if value.strip():
            payload[field] = float(value)
    response = requests.post(API_URL + "/v1/scenarios/simulate", json=payload, timeout=30)
    response.raise_for_status()
    result = response.json()
except (ValueError, requests.RequestException) as error:
    st.error(f"Could not run the scenario: {error}")
    st.stop()

left, right = st.columns(2)
left.metric("Hotel check-ins", f"{result['scenario']['hotel_checkins']:,.0f}", f"{result['change']['hotel_checkins']:+,.0f}")
right.metric("Estimated guest nights", f"{result['scenario']['estimated_guest_nights']:,.0f}",
             f"{result['change']['estimated_guest_nights']:+,.0f}")
st.caption(f"Baseline: {result['baseline']['hotel_checkins']:,.0f} check-ins and "
           f"{result['baseline']['estimated_guest_nights']:,.0f} estimated guest nights. "
           "The night figure uses a guest-day/arrival stay proxy.")

st.subheader("How the change was calculated")
chain = pd.DataFrame([{"Stage": key.replace("_", " ").title(), "Change": value}
                      for key, value in result["chain_change"].items()])
st.dataframe(chain, hide_index=True, width="stretch")
with st.expander("Rates and allocation used"):
    st.json(result["assumptions"])

st.subheader("Guest nationality markets")
markets = pd.DataFrame(result["market_results"])
markets = markets.sort_values("change_estimated_guest_nights", ascending=False)
st.dataframe(markets, hide_index=True, width="stretch")
st.plotly_chart(px.bar(markets.head(15), x="guest_nationality", y="change_estimated_guest_nights",
                       labels={"guest_nationality": "Guest nationality", "change_estimated_guest_nights": "Change in estimated guest nights"}),
                width="stretch")

range_data = result["estimated_guest_nights_assumption_range"]
st.caption(f"Assumption range for scenario guest nights: {range_data['low']:,.0f}–{range_data['high']:,.0f}. "
           "This is not a calibrated confidence interval.")

st.subheader("What moves the estimate")
st.dataframe(pd.DataFrame(result["sensitivity"]), hide_index=True, width="stretch")
for warning in result["warnings"]:
    st.warning(warning)

with st.expander("Historical validation"):
    try:
        model = _get("/v1/model")
        st.json(model["holdout_metrics"])
    except requests.RequestException as error:
        st.error(str(error))

st.download_button("Download scenario JSON", data=__import__("json").dumps(result, indent=2),
                   file_name=f"scenario-{month}.json", mime="application/json")
