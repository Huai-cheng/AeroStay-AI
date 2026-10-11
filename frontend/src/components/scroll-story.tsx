"use client";

import { useRef, useState } from "react";
import { motion, useMotionValueEvent, useScroll, useTransform } from "motion/react";
import { ArrowDown, ArrowRight, Plane } from "lucide-react";

import type { SimulationPayload } from "@/lib/types";

const count = new Intl.NumberFormat("en", { maximumFractionDigits: 0 });

type ScrollStoryProps = {
  origin: string;
  market: string;
  result: SimulationPayload | null;
};

export function ScrollStory({ origin, market, result }: ScrollStoryProps) {
  const storyRef = useRef<HTMLElement>(null);
  const [chapter, setChapter] = useState(0);
  const { scrollYProgress } = useScroll({
    target: storyRef,
    offset: ["start start", "end end"],
  });

  const approachOpacity = useTransform(scrollYProgress, [0, 0.18, 0.32], [1, 1, 0]);
  const arrivalsOpacity = useTransform(scrollYProgress, [0.21, 0.32, 0.48, 0.58], [0, 1, 1, 0]);
  const hotelOpacity = useTransform(scrollYProgress, [0.52, 0.64, 1], [0, 1, 1]);
  const approachScale = useTransform(scrollYProgress, [0, 0.33], [1, 1.13]);
  const arrivalsScale = useTransform(scrollYProgress, [0.24, 0.67], [1.08, 1]);
  const hotelScale = useTransform(scrollYProgress, [0.55, 1], [1.1, 1]);
  const progressScale = useTransform(scrollYProgress, [0, 1], [0, 1]);
  useMotionValueEvent(scrollYProgress, "change", (progress) => {
    const next = progress < 0.24 ? 0 : progress < 0.55 ? 1 : progress < 0.82 ? 2 : 3;
    setChapter((previous) => previous === next ? previous : next);
  });
  const selectedLift = result
    ? result.selected_market_scenario_nights - result.selected_market_baseline_nights
    : null;

  return (
    <section className="scroll-story" ref={storyRef} aria-label="Flight to hotel demand story">
      <div className="story-sticky">
        <div className="story-media" aria-hidden="true">
          <motion.div className="story-image" style={{ opacity: approachOpacity, scale: approachScale, backgroundImage: "url('/story/approach.webp')" }} />
          <motion.div className="story-image" style={{ opacity: arrivalsOpacity, scale: arrivalsScale, backgroundImage: "url('/story/arrivals.webp')" }} />
          <motion.div className="story-image" style={{ opacity: hotelOpacity, scale: hotelScale, backgroundImage: "url('/story/hotel.webp')" }} />
          <div className="story-vignette" />
        </div>

        <div className="story-topline">
          <span><Plane size={16} /> ABU DHABI / DECISION INTELLIGENCE</span>
        </div>

        <div className={`story-chapter story-chapter-one ${chapter === 0 ? "active" : ""}`} aria-hidden={chapter !== 0}>
          <div className="story-kicker"><i /> 01 / THE QUESTION</div>
          <h1>When a new flight lands, <em>where does demand go?</em></h1>
          <p>Follow an aviation change through arrivals, visitors, and hotel demand. Then test the numbers yourself.</p>
          <a className="story-cta" href="#scenario">Open the planner <ArrowRight size={18} /></a>
        </div>

        <div className={`story-chapter story-chapter-two ${chapter === 1 ? "active" : ""}`} aria-hidden={chapter !== 1}>
          <div className="story-kicker"><i /> 02 / THE ARRIVALS</div>
          <h2>Every seat begins a journey. <em>Not every passenger stays.</em></h2>
          <p>Flights and load factor set arriving passenger volume. Transfer and transit travellers branch away before destination demand is estimated.</p>
          <div className="story-equation"><span>Seats</span><b>×</b><span>Load factor</span><b>−</b><span>Transfers + transit</span></div>
        </div>

        <div className={`story-chapter story-chapter-three ${chapter === 2 ? "active" : ""}`} aria-hidden={chapter !== 2}>
          <div className="story-kicker"><i /> 03 / THE CITY</div>
          <h2>Visitors reach the city. <em>Some become hotel guests.</em></h2>
          <p>Visitor share and hotel capture are visible planning assumptions. Change either one in the live studio and see the result move.</p>
          <div className="story-equation"><span>Destination passengers</span><b>×</b><span>Visitor share</span><b>×</b><span>Hotel capture</span></div>
        </div>

        <div className={`story-chapter story-chapter-four ${chapter === 3 ? "active" : ""}`} aria-hidden={chapter !== 3}>
          <div className="story-kicker"><i /> 04 / THE DECISION</div>
          <h2>Turn the journey <em>into a decision.</em></h2>
          <p>Pooled Poisson XGBoost estimates hotel guests by market and season. The scenario engine shows what changes, why, and which assumptions matter most.</p>
          <div className="story-live-result">
            <span>{origin} → Abu Dhabi · {market} hotel market</span>
            <strong>{selectedLift === null ? "Run a live case" : `${selectedLift >= 0 ? "+" : ""}${count.format(selectedLift)}`}</strong>
            <small>{selectedLift === null ? "The planner is loading" : "Estimated change in guest nights for the selected market"}</small>
          </div>
          <a className="story-cta" href="#scenario">Challenge the forecast <ArrowRight size={18} /></a>
        </div>

        <div className="story-progress" aria-hidden="true"><motion.i style={{ scaleY: progressScale }} /></div>
        <div className="story-footer"><span>{chapter === 3 ? "Continue to the live planner" : "Illustrative journey · scroll to explore"}</span><ArrowDown size={17} /><span>0{chapter + 1} / 04</span></div>
      </div>
    </section>
  );
}
