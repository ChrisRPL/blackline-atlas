# Blackline Atlas Live Preview Teleprompter

## Main 90-120 Second Script

### 0-10s: Open

Screen cue: open `/ui`, click `Start live preview`.

Say:

Hi, I am Krzysztof Romanowski, and this is Blackline Atlas.

Blackline Atlas helps civilian analysts check whether public reports of
infrastructure disruption are visible in satellite imagery.

The problem is that a news report can say a bridge, hospital, road, port, dam,
warehouse, or water station was damaged, but the report alone is not visual
evidence.

Blackline Atlas separates the public report from what the satellite images can
actually show.

### 10-25s: Show The Screen

Screen cue: point to map, command panel, evidence panel.

Say:

The center map shows geolocated public reports.

The left panel lets me refresh reports or ask for a region.

The right panel shows the selected place, the satellite images, image quality
notes, the Liquid model brief, and the final review state.

I start with the live preview button because it opens a site with a current
image and a baseline image. After this, I can refresh live GDELT reports
separately.

### 25-45s: Explain Leads

Screen cue: click `Refresh live leads` or show loaded markers.

Say:

For live reports, Atlas uses GDELT, a global database of news events.

Atlas converts each event into a lead with a title, region, coordinates, date,
source link, category, and review status.

A source-only lead stays as awareness. Atlas does not claim satellite evidence
for it.

An inspectable lead has a site or coordinate that can be checked with a current
Sentinel image and an older Sentinel baseline image.

### 45-70s: Show Satellite Evidence

Screen cue: show current image, baseline image, dates, and quality notes.

Say:

Here Atlas asks SimSat and Sentinel for two images of the same location.

The current image shows the site near the reported event date.

The baseline image shows the same site from an earlier date.

Before any model summary, Atlas checks whether the image is blank, cloudy, too
low-resolution, or only broad map context.

If the before-and-after pair is not clear enough, Atlas says source-only or
context-only and does not run a visual claim.

### 70-95s: Show Liquid Visual Brief

Screen cue: show the Liquid VLM analyst card.

Say:

The visual analyst is `LiquidAI/LFM2.5-VL-450M`.

I fine-tuned this adapter for the site-brief task:
`ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter`.

The model writes a short JSON brief that answers four questions:

What is visible in the images?

What changed between baseline and current?

What limits the image evidence?

How does the image evidence relate to the public report?

The model is not allowed to turn source-only facts into visual facts. For
example, Sentinel imagery cannot prove casualties or injuries.

### 95-115s: Close With Safety And Result

Screen cue: show decision and metrics cards.

Say:

Atlas only has three final review states: discard, defer, and downlink now.

Discard means the images do not support a useful visual disruption claim.

Defer means the site needs a better image or more evidence.

Downlink now means the image pair is strong enough to send for human review.

The model does not make that final decision by itself. Rule checks validate the
model output, image quality, source context, and civilian-scope policy.

Blackline Atlas is for humanitarian visibility, logistics transparency, and
public accountability. It does not support targeting, strike planning, troop
tracking, weapon tracking, military asset ranking, or sabotage guidance.

In one sentence: Blackline Atlas turns public disruption reports into careful
satellite image reviews for civilian infrastructure.

## If Live Imagery Is Slow

Say:

Live satellite coverage is uneven. If Atlas cannot get a dated current image
and a dated baseline image, it keeps the report labeled as source-only, shows
why visual review did not run, and does not pretend missing imagery is evidence.

## Do Not Say

- "real-time surveillance"
- "target"
- "strike"
- "military asset"
- "SAM confirms damage"
- "Mapbox evidence"
- "the model verified casualties"
