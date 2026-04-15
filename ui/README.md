# UI

Read-only shell for the future single-page dashboard.

Planned layout:
- left: replay controls, watchlist, metrics
- center: current frame, baseline, anomaly overlay
- right: latest alert, queue, optional Mapbox context

Current scope:
- same-origin shell at `/ui`
- reads `/health`
- renders backend mode truth from `/health.config`
- no replay controls or live frame panels yet
