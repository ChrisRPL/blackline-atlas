# Blackline Atlas Demo Teleprompter

Target length: 100-120 seconds.

Style: calm, operational, cinematic. Let the UI breathe. Do not rush the
satellite frames; the proof is that the system refuses to overclaim.

## Setup Before Recording

- Browser: `http://127.0.0.1:8000/ui`
- Window: desktop width, 1440 px or wider
- Zoom: 100%
- App view: left command rail, globe/map, and right evidence tray all visible
- Services: SimSat ready, Liquid VLM bridge running, final adapter loaded
- Hide: terminal, devtools, notifications, unrelated tabs

## Shot 1: Opening Frame, 0-8s

Show:

- Full app
- Top chips
- Map markers
- Right evidence tray

Say:

> This is Blackline Atlas: source-led satellite triage for civilian disruption.
> It turns live public reports into Sentinel-grounded visual site briefs.

Pause half a second on the full interface.

## Shot 2: The Live Feed, 8-20s

Show:

- Live lead count
- Inspectable site count
- `Refresh live leads`

Action:

- Click `Refresh live leads`, unless the feed is already fresh.

Say:

> The workflow starts with public, geolocated source leads. The model is not
> inventing incidents. Atlas uses the source feed to decide where satellite
> evidence should be requested.

## Shot 3: Ask A Natural Question, 20-32s

Action:

- Type:

```text
What happened around Ukraine?
```

- Press `Run`.

Say:

> An operator can ask a plain-language question. The planner routes it into
> live lead search, map focus, and evidence review.

## Shot 4: Auto-Selected Lead, 32-45s

Show:

- The selected live marker
- The lead title in the tray or popover
- Source summary

Say:

> Atlas auto-selects the newest reviewable lead. This source report tells the
> system where to look. It does not become visual proof by itself.

Pause on the selected lead title.

## Shot 5: Sentinel Evidence Loads, 45-65s

Show:

- Current image
- Baseline image
- Capture dates
- Evidence quality/AOI metric

Say:

> Now Atlas asks SimSat and Sentinel for a dated current image and a historical
> baseline at the selected coordinate. The evidence lane is deliberately narrow:
> before and after imagery, quality checks, and clear caveats.

If the images are cloudy or limited, say:

> Here, visibility is limited. That is important: Atlas does not turn cloudy
> imagery into a confident claim.

## Shot 6: Contact Sheet, 65-78s

Show:

- Orientation sheet if visible
- Label: orientation only / not evidence

Say:

> The contact sheet gives orientation at three scales: three, five, and eight
> kilometers. It is context only. The primary evidence remains the best dated
> current-baseline pair.

## Shot 7: Liquid Visual Brief, 78-98s

Show:

- Liquid VLM analyst card

If a valid brief appears, say:

> The fine-tuned Liquid VLM writes the visual site brief: what is visible, what
> likely changed, what the limitations are, and how the imagery relates to the
> source report.

Then read one short sentence from the brief.

If the card says the visual brief is withheld, say:

> If the model output is invalid or not visually grounded, Atlas withholds the
> brief. That fail-closed behavior is part of the product.

## Shot 8: Guardrails And Metrics, 98-112s

Show:

- Decision card
- Metrics card
- Evidence status

Say:

> The final action is bounded to discard, defer, or downlink now. The system is
> civilian-scope only: no targeting, no strike support, no military asset
> ranking, and no source-only casualty claims as visual facts.

## Shot 9: Closing Line, 112-120s

Show:

- Full app again
- Map and evidence tray together

Say:

> Blackline Atlas connects public leads, Sentinel evidence, and a guarded
> Liquid VLM analyst into one operational workflow for civilian resilience.

Hold the final frame for one second.

## If Live Retrieval Is Slow

Say:

> Live satellite coverage can be sparse. Atlas keeps source-only reports labeled
> as source-only and shows why visual review did not run.

Then:

- Click another inspectable marker, or
- Use a cached/replay-ready lead.

Do not apologize. Treat this as honesty, not failure.

## Lines To Avoid

Do not say:

- real-time surveillance
- target
- strike planning
- military asset
- troop movement
- SAM confirmed damage
- Mapbox evidence
- verified casualties from imagery

## Submission Links To Mention Only If Needed

- Model:
  `ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter`
- Dataset:
  `ChrisRPL/blackline-atlas-training-corpus-v1`
- DPhi endpoints:
  `/data/image/sentinel`, `/data/current/image/sentinel`

## One-Sentence Pitch

Source-led satellite triage that turns live conflict reports into
Sentinel-grounded Liquid VLM site briefs.
