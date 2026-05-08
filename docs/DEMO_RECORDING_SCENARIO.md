# Hackathon Demo Recording Scenario

## Goal

Record one clean 90-120 second run that makes Blackline Atlas understandable
without narration gymnastics:

live public lead -> Sentinel evidence -> Liquid visual brief -> deterministic
civilian guardrails.

## Preflight

- Start SimSat and confirm `/health` shows Sentinel current/baseline ready.
- Start the Liquid VLM bridge with:
  `ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter`.
- Start the app with the submission `.env`.
- Open `http://127.0.0.1:8000/ui`.
- Keep the browser at desktop width, ideally 1440 px or wider.
- Close devtools, extra tabs, and local notifications.
- Do not show terminal logs unless something fails.
- Do not mention WhatsApp, SAM runtime, or Mapbox as evidence.

## Best View

Use the app as the whole screen. Keep the left command rail, map/globe, and
right evidence tray visible together.

Best initial framing:

- top chips visible
- live markers visible
- right tray visible
- command input visible
- no browser chrome zoom below 100%

If the UI auto-selects a live lead, let it. That makes the product feel
operational immediately.

## Recording Script

### 0-10s: Open With The Product

Show `/ui`.

Say:

> Blackline Atlas turns live public disruption reports into satellite-grounded
> visual site briefs for civilian resilience.

Point out:

- live lead count
- inspectable site count
- map markers
- right-side evidence tray

### 10-25s: Refresh Or Ask

Click `Refresh live leads`.

If the feed is already fresh, type:

```text
What happened around Ukraine?
```

Say:

> The first input is a public source lead. The model does not invent an event;
> Atlas starts from geolocated source reports.

### 25-40s: Let Atlas Pick A Lead

Let the newest reviewable lead auto-select, or click a marker that has
satellite review available.

Show the lead popover or right tray title.

Say:

> Atlas separates source context from visual evidence. This report tells us
> where to look, not what the satellite has proven.

### 40-65s: Show Sentinel Evidence

Click `Inspect site` if needed.

Wait for current/baseline frames.

Say:

> The evidence lane asks SimSat/Sentinel for a dated current frame and a
> historical baseline at the selected coordinate. Blank, cloudy, or context-only
> images are caveated or rejected.

Show:

- current image
- baseline image
- capture dates
- evidence quality/AOI metric

If the contact sheet appears, say:

> This contact sheet is orientation only. The primary evidence remains the best
> current/baseline pair.

### 65-90s: Show Liquid VLM Brief

Wait for the Liquid card.

If a valid brief appears, read the first sentence and say:

> Liquid writes a visual site brief: visible scene, likely visual change,
> limitations, and how the imagery relates to the source report.

If the card says visual brief withheld, say:

> If the model output is invalid or not visually grounded, Atlas withholds it
> instead of pretending analysis happened.

### 90-110s: Close With Guardrails

Show the decision/metrics cards.

Say:

> Final action is guarded and civilian-scope only: discard, defer, or downlink
> now. No targeting, no strike support, no military asset ranking, and no
> source-only casualty claims as visual facts.

### 110-120s: Submission Close

Say:

> The fine-tuned Liquid adapter and training corpus are published on Hugging
> Face. The demo path is intentionally narrow: public lead, Sentinel evidence,
> Liquid brief, deterministic guardrails.

## Fallback If Live Imagery Is Slow

Do not wait silently. Say:

> Live satellite retrieval can be sparse. The app keeps source-only reports
> labeled as source-only and shows why visual review did not run.

Then click another inspectable marker or use a cached/replay-ready lead.

## Do Not Say

- "real-time surveillance"
- "target"
- "strike"
- "military asset"
- "SAM confirms damage"
- "Mapbox evidence"
- "the VLM verified casualties"

## Final One-Line Pitch

Source-led satellite triage that turns live conflict reports into
Sentinel-grounded Liquid VLM site briefs.
