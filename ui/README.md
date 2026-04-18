# UI

Read-only shell for the future single-page operator surface.

Current layout:
- top: thin status rail
- center: theatre map
- left-bottom: compact command dock
- bottom: selected-site evidence tray

Current scope:
- same-origin shell at `/ui`
- same-origin assets at `/ui-static/*`
- token-free MapLibre basemap via official demo style
- reads `/health`
- reads `/assets`
- reads `/replay/status`
- reads `/frames/current`
- reads `/frames/baseline`
- reads `/alerts`
- reads `/metrics`
- posts `/agent/query`
- renders real projected watchlist points on a map-first stage
- upgrades to a live MapLibre canvas when the browser loads the external map library
- renders a deterministic backend agent/query loop for operator-style verbs
- renders selected-site evidence in a compact tray
- no real globe, no text-model control plane yet, no replay controls yet
