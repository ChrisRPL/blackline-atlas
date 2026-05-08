# Blackline Atlas Demo Script

## 0:00 - Intro

Hi, I am Krzysztof Romanowski.

This is Blackline Atlas.

Blackline Atlas is a source-led satellite triage workflow for civilian
disruption.

It takes live public reports, connects them to Sentinel imagery, and produces a
careful Liquid VLM visual site brief.

Under the hood, it is a FastAPI app with typed evidence schemas, a WebGL map UI,
GDELT live lead ingestion, SimSat/Sentinel imagery retrieval, and a guarded
Liquid model lane.

## 0:20 - What The App Shows First

The first screen is the operational view.

On the left is the operator command rail.

In the middle is the live map with source markers.

On the right is the evidence tray where the selected site is reviewed.

Under the hood, the frontend talks to typed backend endpoints for health,
assets, leads, metrics, frames, and model status, so the UI can show degraded
states instead of pretending everything is ready.

## 0:40 - Live Lead Feed

The first real feature is live lead discovery.

I can refresh live leads, and Atlas loads public geolocated disruption reports.

The important point is that Atlas starts from a public source lead, not from a
model hallucination.

Under the hood, the backend uses GDELT Cloud when available, falls back to
public GDELT exports, normalizes the reports into lead objects, and keeps a
file-backed cache for replayable demos.

## 1:00 - Natural Language Command

I can also ask a natural question, for example:

What happened around Ukraine?

Atlas turns that into an operator action: search live leads, focus the map, or
inspect a selected site.

Under the hood, the planner returns a structured tool plan, not free-form UI
instructions, so the app can keep the workflow deterministic.

## 1:20 - Auto-Selected Reviewable Lead

After the feed loads, Atlas auto-selects the newest lead that is reviewable by
satellite.

This source report tells Atlas where to look.

It does not count as visual proof.

Under the hood, each lead is scored for satellite relevance and linked to a
synthetic review asset only when it describes something that could plausibly be
visible at macro scale.

## 1:45 - Source Context Boundary

This boundary is central to the product.

Source facts stay source-side.

Satellite-visible facts have to come from imagery.

So if an article mentions casualties, that is not treated as something the VLM
can verify visually.

Under the hood, the prompt and parser both enforce this: source-only casualty
language is stripped or withheld from the visual brief.

## 2:05 - Sentinel Evidence Review

Now I inspect the site.

Atlas requests a current Sentinel image and a historical baseline for the
selected coordinate.

The tray shows the current frame, the baseline frame, timestamps, and evidence
quality.

Under the hood, the evidence resolver tries exact-coordinate AOIs first, then
nearby/context fallbacks, while tracking cloud cover, AOI size, offset, and why
each attempt passed or failed.

## 2:35 - Quality Checks

Atlas is intentionally conservative about imagery.

If the tile is blank, no-data, cloudy, stale, or only context imagery, the UI
says that clearly.

It does not turn weak imagery into a strong alert.

Under the hood, low-information tiles are rejected before model analysis, and
cloud-limited imagery caps confidence and prevents visual confirmation claims.

## 3:00 - Contact Sheet

When available, Atlas also shows a contact sheet.

This gives a quick orientation view at three, five, and eight kilometers.

It is useful for the operator, but it is labeled as orientation only, not
primary evidence.

Under the hood, the resolver builds a bounded six-panel sheet from exact
coordinate baseline/current pairs, and the Liquid model receives it only as
context.

## 3:25 - Liquid Visual Brief

Next is the Liquid visual analyst.

The model writes a short site brief: what is visible, what likely changed, what
the limitations are, and how the imagery relates to the source report.

Under the hood, this uses `LiquidAI/LFM2.5-VL-450M` with a PEFT adapter I
fine-tuned for source-led satellite triage. The prompt asks for structured JSON
and explicitly separates source context from visual evidence.

## 3:55 - Fail-Closed Model Handling

The VLM output is not displayed blindly.

If the model returns malformed JSON, tactical language, unsupported source
claims, or a weak visual read, Atlas withholds the brief.

Under the hood, the backend parses the response into a Pydantic analyst schema,
repairs only safe low-risk drift, and otherwise returns null so the UI can say
visual brief withheld.

## 4:20 - Decision And Metrics

The final action space is deliberately small.

Atlas can discard, defer, or recommend downlink now.

The decision card and metrics make that visible to the operator.

Under the hood, deterministic guardrails sit after the model lane, so the model
is never autonomous alert authority.

## 4:45 - Safety Scope

Blackline Atlas is scoped to civilian resilience and humanitarian transparency.

It does not support targeting, strike planning, military asset ranking, troop
tracking, or sabotage guidance.

Under the hood, that boundary appears in the schemas, prompts, parser, UI copy,
README, and demo path.

## 5:05 - Model And Dataset

For the Liquid track, I also published the fine-tuned adapter and the training
corpus on Hugging Face.

The adapter is for guarded visual site briefs, not autonomous decisions.

Under the hood, the training corpus contains planner examples, paired satellite
image brief examples, hard negatives, and safety examples for separating source
facts from visual facts.

## 5:25 - Closing

The final product is intentionally narrow.

Blackline Atlas connects a public civilian disruption lead to satellite-visible
evidence, explains the limitations, and fails closed when evidence is weak.

That is the core workflow:

public lead,

Sentinel evidence,

Liquid visual brief,

deterministic guardrails.

That is Blackline Atlas.

## Backup Line

If live satellite retrieval is slow:

Live satellite coverage can be sparse.

Atlas keeps source-only reports labeled as source-only, shows why visual review
did not run, and does not pretend missing imagery is evidence.

## One-Line Pitch

Blackline Atlas is source-led satellite triage that turns live conflict reports
into Sentinel-grounded Liquid VLM site briefs.
