# Blackline Atlas Demo Script

## 0:00

This is Blackline Atlas.

It is source-led satellite triage for civilian disruption.

It turns live public reports into Sentinel-grounded visual site briefs.

The goal is not to create another general AI dashboard.

The goal is one reliable operational workflow:

public lead,

satellite evidence,

Liquid visual brief,

and deterministic guardrails.

## 0:15

The workflow starts with public geolocated source leads.

The model is not inventing incidents.

Atlas uses the source feed to decide where satellite evidence should be
requested.

Here I can refresh live leads, or ask a plain-language question like:

What happened around Ukraine?

## 0:30

Atlas focuses the map and selects the newest reviewable lead.

This source report tells the system where to look.

It does not become visual proof by itself.

That separation is important:

source facts are source facts,

and satellite-visible facts have to come from imagery.

## 0:45

Now Atlas requests Sentinel evidence for the selected coordinate.

It loads a dated current image and a historical baseline.

The product is deliberately narrow here.

It is looking for macro-scale civilian disruption,

not tiny objects,

not tactical movement,

and not military asset ranking.

## 1:00

If the imagery is cloudy, stale, blank, or context-only,

Atlas says that clearly.

It does not turn bad imagery into a confident claim.

When the contact sheet appears, it is only orientation.

The primary evidence remains the best dated current and baseline pair.

## 1:15

Next, the fine-tuned Liquid VLM writes a visual site brief.

The brief explains what is visible,

what likely changed,

what the limitations are,

and how the imagery relates to the source report.

If the model output is invalid or not visually grounded,

Atlas withholds the brief instead of pretending analysis happened.

## 1:35

The final action is bounded.

Atlas can discard,

defer,

or recommend downlink now.

It stays inside civilian resilience and humanitarian transparency.

No targeting.

No strike support.

No military asset ranking.

No source-only casualty claims presented as visual facts.

## 1:50

The fine-tuned Liquid adapter and the training corpus are published on
Hugging Face.

The demo path is intentionally simple:

live public lead,

Sentinel evidence,

Liquid visual brief,

deterministic guardrails.

That is Blackline Atlas.

## Backup Line

If live satellite retrieval is slow:

Live satellite coverage can be sparse.

Atlas keeps source-only reports labeled as source-only,

and shows why visual review did not run.

That is honesty, not a failure.

## One-Line Pitch

Source-led satellite triage that turns live conflict reports into
Sentinel-grounded Liquid VLM site briefs.
