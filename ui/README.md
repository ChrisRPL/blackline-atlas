# UI

Same-origin interactive operator shell for the current review build.

Current layout:
- top: plain operator status rail
- center: map-first disruption watch surface
- left: usable command console
- right: selected-site evidence tray

Current scope:
- same-origin shell at `/ui`
- same-origin assets at `/ui-static/*`
- token-free MapLibre basemap
- reads `/health`
- reads `/model/status`
- reads `/assets`
- reads `/leads`
- reads `/replay/status`
- reads `/replay/snapshot`
- reads `/evidence/current`
- reads `/evidence/assets/{asset_id}`
- reads `/frames/current`
- reads `/frames/baseline`
- reads `/alerts`
- reads `/metrics`
- posts `/leads/refresh`
- posts `/agent/query`
- renders real projected watchlist points on a map-first stage
- upgrades to a live MapLibre globe canvas when the browser loads the external map library
- renders a backend agent/query loop for live-source search, focus, compare, explain, and refresh
- renders selected-site evidence in a compact tray
- appends plain-language visual evidence status to selected-site compare notes
- keeps current, baseline, alert, and metrics visible in the same focus tray
- hides technical model diagnostics from the first-use operator flow
- live source search and live refresh are tool-routed through `/agent/query`; the direct refresh button is a fallback/manual control
- no visible replay start/stop controls; `/replay/snapshot` is bootstrapped for fallback/regression state

Live review path:
- Start SimSat on `localhost:9005` for live current/baseline imagery.
- Open `/ui`.
- Click `Refresh live leads` or ask `refresh live leads`.
- Click a marker; ask `Compare current and baseline evidence`.
- If SimSat is degraded, source leads remain live but imagery may return an explicit unavailable state.
