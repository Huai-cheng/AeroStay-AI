# Scroll story: flight to hotel demand

The opening is a pinned, four-chapter visual explanation. Scroll position controls image scale, image transitions, chapter text, progress, and the final live estimate. The imagery is illustrative; the number in chapter four comes from the scenario API.

| Chapter | Visual | Message | Interactive link |
| --- | --- | --- | --- |
| 1. The question | Jet approaching Abu Dhabi at dawn | A change in flight capacity raises a planning question. | Open the planner |
| 2. The arrivals | Airport arrivals concourse | Seats become passengers; transfers and transit reduce destination arrivals. | Conversion flow below |
| 3. The city | Visitors at a waterfront hotel | Visitor share and hotel capture are explicit assumptions. | Scenario sliders below |
| 4. The decision | Hotel scene with live estimate | Pooled Poisson XGBoost estimates market-level hotel demand. | Challenge the forecast |

## Art direction

Warm architectural editorial photography: dawn light, plausible aircraft and airport, polished stone and glass, Abu Dhabi atmosphere, restrained teal. Text and data stay in accessible HTML over the imagery. The generated images are not presented as documentary photographs of a named location.

## Generated assets and prompts

These three project assets were created with the built-in image generation tool, then converted to WebP for the site:

- `public/story/approach.webp` — A realistic, unbranded commercial jet descending toward a contemporary Abu Dhabi airport at dawn; cinematic three-quarter rear view; terminal and hazy skyline; aircraft center-right and space on the left for HTML text; warm gold and deep blue; no text or logos.
- `public/story/arrivals.webp` — An elegant international airport arrivals concourse with glass walls, geometric ceiling detail, natural travellers with luggage, sunrise light, central perspective, and space for HTML text; no text or logos.
- `public/story/hotel.webp` — A contemporary Abu Dhabi waterfront hotel at golden hour with small-scale visitors entering; stone, glass, palm trees, distant skyline, and space for HTML text; no text or logos.

## Motion and performance

The opening uses three optimized stills with scroll-linked zoom and crossfades. Discrete text chapters switch as the scroll reaches each part of the story. It does not seek through a video file. This keeps scrolling reversible and the live result separate from illustrative footage. The three WebP assets total roughly 660 KB. A reduced-motion presentation retains the first frame and main explanation.
