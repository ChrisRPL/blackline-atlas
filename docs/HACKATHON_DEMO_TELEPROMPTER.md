Hi, I am Krzysztof Romanowski, and this is Blackline Atlas.

Blackline Atlas is a source-led satellite triage app for civilian disruption.

The idea is simple: start with a public report, find the location on the map,
pull current and baseline Sentinel imagery, and only then ask a Liquid
vision-language model for a cautious site brief.

I built it this way because conflict and disaster reports are noisy. A source
can tell us where to look, but it should not automatically become visual
evidence.

On the first screen, you can see the operator view. The map is the center of
the app, the command rail is on the left, and the evidence tray is on the
right.

Under the hood, this is a FastAPI backend with typed Pydantic schemas and a
browser UI that talks to dedicated endpoints for health, live leads, map
assets, Sentinel frames, metrics, and analyst status.

The first thing I show is the live lead feed. Blackline Atlas loads geolocated
public reports and places them on the globe.

For this demo, the live feed is coming from GDELT. The backend normalizes those
reports into structured lead objects, stores a replayable cache, and marks which
leads are actually reviewable with satellite imagery.

Now I can ask a normal question, like: what happened around Ukraine?

The app does not treat that as a chat conversation. It turns the command into a
structured operator action, like searching live leads, focusing the map, or
opening a site comparison.

The planner lane is designed for `LiquidAI/LFM2.5-1.2B-Instruct-GGUF`, served
through an OpenAI-compatible local endpoint. For a stable recording, the app can
also fall back to the same typed planner contract without showing a broken
planner state.

After the live feed loads, Atlas auto-selects the newest lead that is useful for
satellite review.

This is important: the report tells the app where to look, but it does not count
as visual proof.

Under the hood, each lead is scored for macro-scale satellite relevance. If it
describes something that could plausibly be visible from Sentinel imagery, the
lead is linked to a reviewable site.

Now I open the evidence tray.

Atlas requests a current Sentinel image and a historical baseline for the same
coordinate.

The app shows the current frame, the baseline frame, timestamps, cloud or image
quality, and whether the pair is strong enough to support analysis.

Under the hood, the resolver tries exact-coordinate areas first, then nearby and
regional fallbacks. It tracks AOI size, coordinate offset, cloud cover, no-data
tiles, and the reason each attempt passed or failed.

This is one of the main things I wanted to get right. If the image is blank,
cloudy, stale, or only useful as context, Atlas says that clearly.

It does not turn weak imagery into a confident alert.

The contact sheet is a fast orientation view. It shows the same coordinate at
three, five, and eight kilometers, with baseline and current columns.

Under the hood, that contact sheet is generated from a bounded six-panel
Sentinel request. It is useful for orientation, but the UI labels it as context
only, not primary evidence.

The Liquid visual analyst is the next layer.

The base vision-language model is `LiquidAI/LFM2.5-VL-450M`.

I fine-tuned a PEFT adapter for this workflow:
`ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter`.

The training dataset is
`ChrisRPL/blackline-atlas-training-corpus-v1`.

The model task is not general image captioning. It is a guarded site brief:
what is visible, what may have changed, what the limitations are, and how the
imagery relates to the source report.

The local serving path is an OpenAI-compatible `/v1/chat/completions` bridge,
so the app can treat the Liquid VLM as a structured backend component.

The prompt asks for JSON, and the backend parses the answer into a Pydantic
schema before anything is shown in the UI.

If the model returns malformed JSON, tactical language, unsupported source
claims, or a weak visual read, Atlas withholds the brief.

That is not a failure in this product. That is the safety behavior.

In a demo runtime where the local Liquid VLM bridge is not attached, the app
still shows the Sentinel evidence and clearly says that the visual brief is
withheld.

The final decision space is deliberately small.

Atlas can discard, defer, or recommend downlink now.

The model is never autonomous alert authority. The final triage goes through
deterministic guardrails after the model lane.

I also kept SAM out of the judge path on purpose.

SAM-style segmentation can be useful for future high-resolution evaluation, but
low-resolution Sentinel masks are not defensible enough for this workflow. For
this submission, the honest path is source lead, Sentinel evidence, Liquid VLM
brief, and deterministic guardrails.

The safety boundary is civilian from end to end.

Blackline Atlas is for humanitarian visibility, logistics transparency, and
civilian resilience. It does not support targeting, strike planning, military
asset ranking, troop tracking, or sabotage guidance.

Technically, that boundary is not just in the README. It is reflected in the
schemas, prompts, parser, UI copy, model output validation, and final action
space.

The core pitch is this:

Blackline Atlas turns live public disruption reports into Sentinel-grounded
Liquid VLM site briefs, while staying honest about uncertainty and failing
closed when the evidence is weak.

The workflow is narrow, but that is the point.

Public lead.

Sentinel current and baseline imagery.

Liquid visual brief.

Deterministic civilian guardrails.

That is Blackline Atlas.

If live imagery is slow during recording, I can say this:

Live Sentinel coverage can be sparse, and Atlas is designed for that. If a dated
before-and-after pair is not available, it keeps the report source-side, shows
why visual review did not run, and does not pretend missing imagery is evidence.
