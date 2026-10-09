# Submission plan

The challenge asks each team to upload a **10-page PDF presentation** and a **1–2 minute video** of the developed solution or digital prototype. The package must demonstrate a working basic prototype, simulation, or model.

## Ten-page PDF outline

| Page | Content | Evidence to include |
| ---: | --- | --- |
| 1 | Title and one-sentence decision the tool supports. | Team/project identity. |
| 2 | Problem and why it matters. | Seats versus actual hotel demand; planning use cases. |
| 3 | Data and the country-definition problem. | Actual data sources, periods, grains, origin versus nationality. |
| 4 | System design. | Diagram from data preparation through model, scenario engine, and UI. |
| 5 | Transparent conversion chain. | Seats → passengers → visitors → hotel guests → guest nights, with assumptions. |
| 6 | Country mapping and model approach. | Crosswalk method, seasonal/statistical layer, and uncertainty. |
| 7 | Historical validation. | Held-out dates, WMAPE, benchmark, bias, and weak markets. |
| 8 | Prototype demo. | Screenshot of controls and baseline/scenario comparison. |
| 9 | Scenario result and sensitivity. | Market/season effects, leading drivers, and a plausible range. |
| 10 | Planner action and real-world rollout. | What DCT should do differently, deployment steps, limitations. |

This is a content plan, not a claim that the figures already exist. Keep the final PDF to **exactly ten pages** and show actual measured results rather than placeholders.

## Video storyboard (target: about 90 seconds)

1. **0–15 s:** State the flight-to-hotel planning question and show the app.
2. **15–30 s:** Show the visible seats-to-guest-nights chain and the origin/nationality caveat.
3. **30–60 s:** Change one lever (such as adding a twice-weekly route) and show the updated totals, market/season breakdown, and uncertainty.
4. **60–75 s:** Show the held-out validation result and leading drivers.
5. **75–90 s:** End with one concrete planning action and its qualification.

Use readable screen capture and narration or captions. Ensure the demonstrated figures agree with the submitted PDF.

## Final submission check

- [ ] The simulator runs and changes hotel demand when a relevant input changes.
- [ ] The chain and country reconciliation are explained.
- [ ] The PDF is exactly ten pages and contains the problem, solution, system diagram, demo, and real-world plan.
- [ ] The video is between one and two minutes and demonstrates the developed prototype.
- [ ] Held-out dates, WMAPE, comparator, assumptions, uncertainty, and limitations are visible.
- [ ] Results are broken down by source market and season, with an actionable planner takeaway.
- [ ] All submission claims match reproducible outputs; competition data is shared only as permitted.

The provided brief does not state a submission deadline, upload format beyond PDF/video, or an exact rule for supplementary code. Verify those on the competition portal before final upload.
