import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { BacktestMetrics } from "@/components/backtest-metrics";
import { Logo } from "@/components/logo";
import { ScrollStory } from "@/components/scroll-story";

export const metadata: Metadata = {
  title: "How it works | AeroStay",
  description: "The conversion chain, model, back-test and limitations behind the AeroStay simulator.",
};

const CHAIN = [
  { step: "Seats", how: "Scheduled seats on the route for the chosen dates", source: "Flight schedule data" },
  { step: "Passengers", how: "Seats × load factor", source: "Observed load factor, adjustable" },
  { step: "Arriving in Abu Dhabi", how: "Passengers minus transfer and transit passengers", source: "Observed shares, adjustable" },
  { step: "Visitors", how: "Arrivals × visitor share, removing residents returning home", source: "Assumption, default 75%" },
  { step: "Hotel guests", how: "Visitors × hotel capture rate", source: "Assumption, default 65%" },
  { step: "Guest nights", how: "Extra hotel arrivals are assigned to the chosen nationality and passed to the model", source: "Pooled Poisson XGBoost" },
];

export default function HowItWorks() {
  return (
    <div className="doc">
      <header className="doc-nav">
        <Link href="/" aria-label="AeroStay home"><Logo /></Link>
        <Link href="/#simulator" className="button ghost small"><ArrowLeft size={15} /> Back to the simulator</Link>
      </header>

      <ScrollStory />

      <main className="doc-body">
        <section>
          <p className="kicker"><span lang="ar" dir="rtl">كيف يعمل</span><i aria-hidden="true" />The conversion chain</p>
          <h2>Six steps from a seat to a hotel night</h2>
          <p className="doc-lede">Every step is visible in the simulator. Steps based on data start at observed values; steps based on assumptions are labelled and can be changed.</p>
          <ol className="chain-list">
            {CHAIN.map((item, index) => (
              <li key={item.step}>
                <span className="chain-index">{index + 1}</span>
                <div><b>{item.step}</b><p>{item.how}</p></div>
                <small>{item.source}</small>
              </li>
            ))}
          </ol>
          <p className="doc-note">Flight data records where a flight departed. Hotel data records a guest&apos;s nationality. The two are linked by the nationality allocation setting: the share of extra hotel guests from a route who hold the chosen nationality. It defaults to 100% when origin and nationality match and 50% otherwise.</p>
        </section>

        <section>
          <p className="kicker">The model</p>
          <h2>One gradient-boosted model for all markets</h2>
          <div className="two-col">
            <div>
              <p>A single XGBoost model with a Poisson count objective predicts daily hotel guests for each nationality, learning domestic and international demand together.</p>
              <p>Guest nights are the predicted guests minus same-day guests. A flight scenario changes the hotel arrivals for the chosen nationality, and the model turns that into guests and guest nights.</p>
            </div>
            <ul className="feature-list">
              <li>Time trend and annual seasonality</li>
              <li>Month, weekday and weekend</li>
              <li>Domestic or international, and nationality</li>
              <li>New hotel arrivals and same-day guests</li>
              <li>Last year&apos;s guests and arrivals, and the year-on-year change</li>
            </ul>
          </div>
        </section>

        <section>
          <p className="kicker">Validation</p>
          <h2>Tested on months the model never saw</h2>
          <p className="doc-lede">The model was trained only on data before 1 August 2024, then scored on 1 August 2024 to 28 February 2025 (212 days). The error is weighted mean absolute percentage error (WMAPE): lower is better.</p>
          <BacktestMetrics />
        </section>

        <section>
          <p className="kicker">Sensitivity</p>
          <h2>Two ways to find what matters</h2>
          <div className="two-col">
            <div>
              <h3>Quick test</h3>
              <p>Moves one input at a time around your scenario and reruns the full chain and model: weekly flights ±2, load factor ±5 points, visitor share and hotel capture ±10 points.</p>
            </div>
            <div>
              <h3>Full test</h3>
              <p>Uses the Morris method (SALib) to vary all inputs together across plausible ranges in 72 model runs, then ranks each input by its average effect.</p>
            </div>
          </div>
        </section>

        <section>
          <p className="kicker">Limitations</p>
          <h2>What the numbers do and don&apos;t claim</h2>
          <ul className="limits">
            <li>Visitor share, hotel capture and nationality allocation are not in the supplied data. They are planning assumptions you can change.</li>
            <li>The model is trained on hotel records. Flight changes reach it through hotel arrivals for the chosen nationality.</li>
            <li>The planning range covers all Abu Dhabi hotels. It combines visitor share and hotel capture ±10 points with the back-tested error, widened by 25% for new routes.</li>
            <li>New routes have no history, so they rely on the assumptions you set.</li>
            <li>Results are planning estimates under stated assumptions, not causal guarantees.</li>
          </ul>
        </section>
      </main>

      <footer className="doc-footer">
        <Logo size={24} />
        <span>Built for the Department of Culture and Tourism – Abu Dhabi challenge. All data is aggregated.</span>
      </footer>
    </div>
  );
}
