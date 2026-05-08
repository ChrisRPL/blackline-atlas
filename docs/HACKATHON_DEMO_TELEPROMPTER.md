Hi, I am Krzysztof Romanowski, and this is Blackline Atlas.

Blackline Atlas is source-led satellite triage for civilian disruption.

The problem I am solving is that public conflict and disaster reports move
fast, but they are noisy and hard to verify visually.

An operator may know that something happened near a bridge, hospital, road, or
city block, but still needs a careful way to connect that public source lead to
satellite-visible evidence.

Blackline Atlas does that in one workflow.

It starts with a live public report, places it on the globe, checks whether it
is reviewable from satellite imagery, requests current and baseline Sentinel
frames, and then prepares a guarded Liquid VLM site brief.

The important design choice is that the source report is only a lead.

It tells Atlas where to look, but it does not become visual proof.

On screen, this is the operator view.

The map shows live geolocated leads.

The left rail is where I can refresh reports or ask a natural language question.

The right tray is where Atlas shows the selected site, the evidence pair,
quality checks, and the final triage state.

Under the hood, the app is a FastAPI backend with typed Pydantic schemas and a
browser UI. The frontend calls separate endpoints for health, leads, assets,
Sentinel frames, site comparison, model status, and metrics.

First, I refresh the live lead feed.

For this demo, the lead source is GDELT.

Atlas normalizes GDELT events into structured lead objects, keeps a replayable
cache, and marks which leads are useful for satellite review.

Now I can ask something like: what happened around Ukraine?

The app does not treat this as free-form chat.

It turns the command into a structured tool action, such as searching live
leads, focusing the map, or opening a current-versus-baseline comparison.

The planner lane is designed for `LiquidAI/LFM2.5-1.2B-Instruct-GGUF` through
an OpenAI-compatible local endpoint.

For recording stability, the same planner contract can also run deterministically
when that local bridge is not attached.

After the live feed loads, Atlas auto-selects the newest lead that can be
reviewed by satellite.

That is the start of the judge path: live source lead, then satellite evidence,
then model brief, then deterministic guardrails.

Now I open the selected site.

Atlas asks SimSat and Sentinel for a current frame and a historical baseline at
the selected coordinate.

The evidence tray shows the current image, the baseline image, capture times,
quality metadata, and whether the pair is strong enough to use.

Under the hood, the evidence resolver tries exact-coordinate areas first. If
that fails, it tries nearby and regional fallback windows, while tracking cloud
cover, AOI size, coordinate offset, no-data tiles, and every pass or fail
reason.

This matters because the app should be honest under bad satellite conditions.

If the tile is blank, cloudy, stale, or only useful for orientation, Atlas says
that clearly.

It does not convert weak imagery into a confident alert.

The contact sheet gives a wider view.

It shows the same coordinate at three, five, and eight kilometers, with baseline
and current columns.

This helps the viewer understand the site, but the UI labels it as orientation
only.

Under the hood, it is a bounded six-panel Sentinel contact sheet. It can help
context, but it is not treated as primary evidence.

The model layer is built around Liquid.

The main vision-language model is `LiquidAI/LFM2.5-VL-450M`.

I fine-tuned a PEFT adapter for the visual analyst role:
`ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter`.

The dataset I used is `ChrisRPL/blackline-atlas-training-corpus-v1`.

That dataset contains source-led satellite triage examples, paired
Sentinel/SimSat current and baseline image examples, planner examples, hard
negatives, and safety examples.

The model is trained to produce a guarded site brief, not a general caption and
not an autonomous alert.

It should answer what is visible, what may have changed, what the limitations
are, and how the image evidence relates to the source report.

The local serving path is an OpenAI-compatible `/v1/chat/completions` bridge, so
the app can treat the Liquid VLM like a structured backend component.

The prompt asks for JSON.

The backend parses the answer into a Pydantic schema before anything is shown
to the operator.

If the Liquid output is malformed, tactical, based only on source text, or too
weak visually, Atlas withholds the brief.

That is intentional.

For this kind of product, a withheld brief is better than a false visual claim.

The final decision space is deliberately small.

Atlas can discard, defer, or recommend downlink now.

The model never has autonomous alert authority.

After the model lane, deterministic guardrails decide what can be shown as a
civilian triage result.

I also kept SAM out of the judge runtime path.

SAM-style segmentation is interesting for future high-resolution evaluation,
but low-resolution Sentinel masks are not defensible enough for this demo.

So the final submission path is cleaner and more honest: GDELT lead,
SimSat/Sentinel evidence, Liquid VLM brief, and deterministic civilian
guardrails.

The whole system is scoped to civilian resilience.

It is meant for humanitarian visibility, logistics transparency, and public
accountability.

It does not support targeting, strike planning, military asset ranking, troop
tracking, or sabotage guidance.

That boundary is implemented in the schemas, prompts, parser, UI copy, model
validation, and final action set.

So the full answer to what Blackline Atlas is:

It is an operational workflow for turning live public disruption reports into
Sentinel-grounded Liquid VLM site briefs.

The problem it solves is the gap between noisy public reports and cautious
satellite-visible evidence.

How I use it is simple: refresh live leads, select or auto-select a reviewable
site, inspect current and baseline imagery, check the contact sheet and quality
metadata, and then read the guarded triage result.

The models are `LiquidAI/LFM2.5-1.2B-Instruct-GGUF` for the planner lane and
`LiquidAI/LFM2.5-VL-450M` for the visual analyst lane.

The fine-tuned adapter is
`ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter`.

The dataset is `ChrisRPL/blackline-atlas-training-corpus-v1`.

And the app works end to end as:

public lead,

satellite retrieval,

current-versus-baseline evidence,

Liquid visual brief,

deterministic civilian guardrails.

That is Blackline Atlas.

If live Sentinel imagery is slow during recording, I can say this:

Live satellite coverage can be sparse, and Atlas is designed for that. If a
dated before-and-after pair is not available, it keeps the report source-side,
shows why visual review did not run, and does not pretend missing imagery is
evidence.
