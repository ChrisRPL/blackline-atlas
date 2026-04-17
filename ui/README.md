# UI

Read-only shell for the future single-page operator surface.

Current layout:
- left: command channel
- center: theatre map
- right: selected-site drawer

Current scope:
- same-origin shell at `/ui`
- same-origin assets at `/ui-static/*`
- reads `/health`
- reads `/assets`
- reads `/replay/status`
- reads `/frames/current`
- reads `/frames/baseline`
- reads `/alerts`
- reads `/metrics`
- renders real projected watchlist points on a map-first stage
- renders a tiny local command loop for operator-style verbs
- renders selected-site evidence in a compact drawer
- no real globe, no live chat backend, no replay controls yet
