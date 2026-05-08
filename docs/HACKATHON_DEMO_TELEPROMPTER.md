# Blackline Atlas Demo Script

## 0:00

This is Blackline Atlas.

I built it as a small, operational satellite triage workflow for civilian
disruption.

The basic idea is simple:

start with a public report,

resolve satellite evidence for that place,

ask a Liquid vision-language model for a careful visual brief,

and keep the final decision under deterministic guardrails.

The important part is that the model is not the source of truth.

The source report tells Atlas where to look.

The satellite imagery tells Atlas what can actually be seen.

## 0:20

The frontend is a FastAPI-backed web app with a WebGL map interface.

On the left, I have the operator command rail.

In the middle, live source markers.

On the right, the evidence tray.

The backend exposes typed API contracts for leads, frames, evidence bundles,
Liquid analyst reports, model status, and health checks.

That made the demo much easier to stabilize, because every boundary has a
schema.

## 0:40

The live lead path uses GDELT.

I can refresh the feed, or ask a question like:

What happened around Ukraine?

The planner turns that into a tool call:

search live leads,

focus the map,

or inspect a selected site.

For the demo, Atlas auto-selects the newest lead that is actually reviewable by
satellite.

## 1:00

This selected source report is just a lead.

It is not treated as visual proof.

That distinction matters a lot.

Casualties, source claims, and article language stay source-side.

The visual lane only talks about what is visible in imagery:

roads,

buildings,

ports,

water systems,

clouds,

no-data tiles,

and large-scale disruption patterns.

## 1:25

When I inspect the site, the backend requests Sentinel imagery through the
SimSat endpoints.

It tries to resolve a current image and a historical baseline for the selected
coordinate.

The resolver keeps metadata about each attempt:

AOI size,

cloud cover,

exact or nearby coordinate,

and why an attempt passed or failed.

Blank and no-data tiles are rejected before they can become model evidence.

## 1:50

If there is enough imagery, the UI shows the current frame and the baseline
frame side by side.

There is also an optional contact sheet at three, five, and eight kilometers.

That sheet is useful for orientation,

but I label it clearly as context only.

The primary evidence remains the best dated current-baseline pair.

I originally explored SAM-style segmentation here,

but for low-resolution Sentinel imagery the masks were not defensible enough,

so I removed SAM from the judge path instead of overclaiming.

## 2:20

The Liquid lane uses `LiquidAI/LFM2.5-VL-450M` with a PEFT adapter that I
fine-tuned for this workflow.

The final adapter is on Hugging Face,

and the training corpus is published too.

The model receives the source context,

the baseline image,

the current image,

and, when available, the orientation contact sheet.

But the prompt is strict:

do not treat source facts as visual facts,

do not mention tactical targets,

return structured JSON,

and say when the imagery is too limited.

## 2:55

The Liquid output is not displayed blindly.

The backend parses it into a typed analyst schema.

If the JSON is malformed, tactical, source-only, or not grounded enough,

Atlas withholds the visual brief.

If the imagery is cloud-limited,

confidence is capped,

the action is constrained,

and the UI says the brief is low-confidence.

That fail-closed behavior is a big part of the project.

## 3:20

The final action space is intentionally tiny:

discard,

defer,

or downlink now.

There is no targeting workflow here.

No strike support.

No military asset ranking.

No real-time surveillance claim.

This is framed around civilian resilience,

humanitarian logistics transparency,

and public accountability.

## 3:45

Technically, the stack is:

FastAPI for the backend,

Pydantic schemas at the boundaries,

GDELT for live source leads,

SimSat and Sentinel for satellite evidence,

Mapbox or MapLibre only for map context,

and Liquid for the planner and visual analyst lanes.

The repo also includes deterministic replay and cached fallback paths so the
demo can survive external service issues.

## 4:15

What I like about this version is that it is narrow on purpose.

It does not try to solve every satellite intelligence problem.

It tries to do one thing honestly:

connect a public civilian disruption lead to satellite-visible evidence,

then explain the limits clearly.

That is Blackline Atlas.

## Backup Line

If live satellite retrieval is slow:

Live coverage can be sparse.

In that case Atlas keeps the report labeled as source-only,

shows why visual review did not run,

and does not pretend that missing imagery is evidence.

## Short Version

Blackline Atlas is a source-led satellite triage system.

It uses GDELT leads, SimSat/Sentinel imagery, a fine-tuned Liquid VLM adapter,
and deterministic guardrails to produce careful visual site briefs for civilian
disruption.
