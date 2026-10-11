"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { motion, useMotionValueEvent, useScroll, useTransform } from "motion/react";
import { ArrowDown, ArrowRight } from "lucide-react";

const CHAPTERS = [
  {
    title: <>When a new flight lands, <em>where does demand go?</em></>,
    body: "Follow one change in flight capacity through arrivals, visitors and hotel stays.",
    equation: null,
  },
  {
    title: <>Every seat starts a journey. <em>Not every passenger stays.</em></>,
    body: "Flights and load factor set how many passengers arrive. Transfer and transit passengers continue elsewhere.",
    equation: ["Seats", "×", "Load factor", "−", "Transfers and transit"],
  },
  {
    title: <>Visitors reach the city. <em>Some choose a hotel.</em></>,
    body: "Visitor share and hotel capture are visible assumptions. You can change both in the simulator.",
    equation: ["Arrivals", "×", "Visitor share", "×", "Hotel capture"],
  },
  {
    title: <>Then the model <em>turns it into guest nights.</em></>,
    body: "A gradient-boosted model, back-tested on held-out months, estimates hotel guests by nationality and by day.",
    equation: null,
  },
];

export function ScrollStory() {
  const storyRef = useRef<HTMLElement>(null);
  const [chapter, setChapter] = useState(0);
  const { scrollYProgress } = useScroll({ target: storyRef, offset: ["start start", "end end"] });

  const approachOpacity = useTransform(scrollYProgress, [0, 0.18, 0.32], [1, 1, 0]);
  const arrivalsOpacity = useTransform(scrollYProgress, [0.21, 0.32, 0.48, 0.58], [0, 1, 1, 0]);
  const hotelOpacity = useTransform(scrollYProgress, [0.52, 0.64, 1], [0, 1, 1]);
  const approachScale = useTransform(scrollYProgress, [0, 0.33], [1, 1.12]);
  const arrivalsScale = useTransform(scrollYProgress, [0.24, 0.67], [1.08, 1]);
  const hotelScale = useTransform(scrollYProgress, [0.55, 1], [1.1, 1]);
  const progress = useTransform(scrollYProgress, [0, 1], [0, 1]);
  useMotionValueEvent(scrollYProgress, "change", (value) => {
    const next = value < 0.24 ? 0 : value < 0.55 ? 1 : value < 0.82 ? 2 : 3;
    setChapter((previous) => (previous === next ? previous : next));
  });

  return (
    <section className="story" ref={storyRef} aria-label="From flight to hotel night">
      <div className="story-sticky">
        <div className="story-media" aria-hidden="true">
          <motion.div className="story-image" style={{ opacity: approachOpacity, scale: approachScale, backgroundImage: "url('/story/approach.webp')" }} />
          <motion.div className="story-image" style={{ opacity: arrivalsOpacity, scale: arrivalsScale, backgroundImage: "url('/story/arrivals.webp')" }} />
          <motion.div className="story-image" style={{ opacity: hotelOpacity, scale: hotelScale, backgroundImage: "url('/story/hotel.webp')" }} />
          <div className="story-vignette" />
        </div>

        {CHAPTERS.map((item, index) => (
          <div key={index} className={`story-chapter ${chapter === index ? "active" : ""}`} aria-hidden={chapter !== index}>
            <p className="story-step">{index + 1} of 4</p>
            {index === 0 ? <h1>{item.title}</h1> : <h2>{item.title}</h2>}
            <p>{item.body}</p>
            {item.equation && (
              <div className="story-equation">
                {item.equation.map((part, partIndex) => (partIndex % 2 ? <b key={partIndex}>{part}</b> : <span key={partIndex}>{part}</span>))}
              </div>
            )}
            {index === 3 && <Link className="button primary" href="/#simulator">Try it in the simulator <ArrowRight size={17} /></Link>}
          </div>
        ))}

        <div className="story-progress" aria-hidden="true"><motion.i style={{ scaleY: progress }} /></div>
        <div className="story-footer"><span>{chapter === 3 ? "Keep scrolling for the method" : "Illustrative images · scroll to continue"}</span><ArrowDown size={15} /></div>
      </div>
    </section>
  );
}
