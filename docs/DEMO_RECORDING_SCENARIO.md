# Demo Recording Scenario

## Preflight

- Start the backend with the submission `.env` loaded.
- Confirm `/health` shows SimSat/Sentinel, Liquid VLM, and live lead source status.
- Confirm the browser is at `/ui` with no console errors.
- Keep generated videos, screenshots, and recordings out of git.

## Script

1. Open `/ui`.
2. Show the top bar: live leads, inspectable sites, and evidence quality/AOI.
3. Click refresh if the lead feed is stale, then show live GDELT leads on the map.
4. Ask one region query, for example: `What happened around Ukraine?`
5. Click an evidence-qualified source lead.
6. Select `Inspect site`.
7. Show current and baseline Sentinel frames loading before model analysis completes.
8. Wait for the Liquid VLM site brief. Do not present SAM masks unless a future high-resolution pair returns reliable masks.
9. Read the brief as a visual site assessment: visible scene, likely changes, limits, and source-to-visual relationship.
10. Close with the boundary: civilian resilience and humanitarian transparency only; no tactical targeting, strike support, or real-time surveillance claims.

## Closeout Line

Atlas combines live source leads with dated Sentinel evidence and a Liquid VLM analyst with a fine-tuned adapter. Segmentation is intentionally out of the judge path until imagery resolution supports reliable masks; source-only reports stay labeled as source leads.
