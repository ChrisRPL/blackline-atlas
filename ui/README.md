# UI

Read-only shell for the future single-page dashboard.

Planned layout:
- left: replay controls, watchlist, metrics
- center: current frame, baseline, anomaly overlay
- right: latest alert, queue, optional Mapbox context

Current scope:
- same-origin shell at `/ui`
- reads `/health`
- reads `/frames/current`
- reads `/frames/baseline`
- renders backend mode truth from `/health.config`
- renders read-only current and baseline snapshots in the center pane
- no replay controls or multi-pane live dashboard yet
