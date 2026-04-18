const urls = {
  health: new URL("/health", window.location.origin),
  assets: new URL("/assets", window.location.origin),
  alerts: new URL("/alerts", window.location.origin),
  replay: new URL("/replay/status", window.location.origin),
  current: new URL("/frames/current", window.location.origin),
  baseline: new URL("/frames/baseline", window.location.origin),
  metrics: new URL("/metrics", window.location.origin),
  agentQuery: new URL("/agent/query", window.location.origin),
};

const state = {
  health: null,
  assets: [],
  alerts: [],
  replay: null,
  currentFrame: null,
  baselineFrame: null,
  metrics: null,
  selectedAssetId: null,
  transcriptSeeded: false,
  map: null,
  mapMarkers: [],
  mapReady: false,
  mobileSheet: null,
  plannerFallbackActive: false,
};

const dom = {
  healthChip: document.querySelector("#health-chip"),
  modeChip: document.querySelector("#mode-chip"),
  alertChip: document.querySelector("#alert-chip"),
  plannerChip: document.querySelector("#planner-chip"),
  mapStage: document.querySelector("#map-stage"),
  mapCanvas: document.querySelector("#map-canvas"),
  mapTrustState: document.querySelector("#map-trust-state"),
  mapMarkers: document.querySelector("#map-markers"),
  channelPanel: document.querySelector(".channel-panel"),
  drawerPanel: document.querySelector(".drawer-panel"),
  siteName: document.querySelector("#site-name"),
  siteImpact: document.querySelector("#site-impact"),
  siteSummary: document.querySelector("#site-summary"),
  siteRegion: document.querySelector("#site-region"),
  siteType: document.querySelector("#site-type"),
  siteCoords: document.querySelector("#site-coords"),
  currentTitle: document.querySelector("#current-title"),
  currentNote: document.querySelector("#current-note"),
  currentStatus: document.querySelector("#current-status"),
  currentCaptured: document.querySelector("#current-captured"),
  baselineTitle: document.querySelector("#baseline-title"),
  baselineNote: document.querySelector("#baseline-note"),
  baselineCaptured: document.querySelector("#baseline-captured"),
  baselineSource: document.querySelector("#baseline-source"),
  chatLog: document.querySelector("#chat-log"),
  chatForm: document.querySelector("#chat-form"),
  chatInput: document.querySelector("#chat-input"),
  channelNote: document.querySelector("#channel-note"),
  sheetToggles: document.querySelectorAll(".sheet-toggle"),
};

function compactLabel(value, fallback = "none") {
  return value === null || value === undefined || value === "" ? fallback : value;
}

function humanizeSlug(value) {
  return compactLabel(value).replaceAll("_", " ").replaceAll("-", " ");
}

function formatTimestamp(value) {
  if (!value) {
    return "unknown";
  }

  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) {
    return value;
  }

  return timestamp.toISOString().replace("T", " ").replace(".000Z", " UTC").replace("Z", " UTC");
}

function siteImpactClass(level) {
  if (level === "high" || level === "accepted") {
    return "status-pill high";
  }
  if (level === "medium" || level === "degraded") {
    return "status-pill medium";
  }
  if (level === "low") {
    return "status-pill low";
  }
  return "status-pill idle";
}

function selectedAsset() {
  return state.assets.find((asset) => asset.asset_id === state.selectedAssetId) || state.assets[0] || null;
}

function currentAlert() {
  return state.alerts[0] || null;
}

function alertForAsset(assetId) {
  return state.alerts.find((alert) => alert.asset_id === assetId) || null;
}

function hasCompareForAsset(assetId) {
  return (
    state.currentFrame?.frame?.asset_id === assetId && state.baselineFrame?.frame?.asset_id === assetId
  );
}

function currentStatusLabel(assetId) {
  if (state.currentFrame?.frame?.asset_id !== assetId) {
    return "watch";
  }
  if (state.currentFrame.accepted_for_alerting === true) {
    return "accepted";
  }
  if (state.currentFrame.accepted_for_alerting === false) {
    return "suppressed";
  }
  return "unknown";
}

function topStatus() {
  if (!state.health) {
    return {
      healthText: "degraded",
      healthClass: "chip degraded",
      modeText: "health missing",
      modeClass: "chip neutral",
    };
  }

  const liveCount = [
    state.health.config.simsat_current_http_enabled,
    state.health.config.simsat_baseline_http_enabled,
  ].filter(Boolean).length;
  const degraded = [
    state.health.simsat_current.status,
    state.health.simsat_baseline.status,
    state.health.mapbox.status,
  ].includes("degraded");

  if (degraded) {
    return {
      healthText: "degraded",
      healthClass: "chip degraded",
      modeText: "fallback active",
      modeClass: "chip neutral",
    };
  }

  if (liveCount > 0) {
    return {
      healthText: "live",
      healthClass: "chip live",
      modeText: liveCount === 1 ? "1 live lane" : `${liveCount} live lanes`,
      modeClass: "chip neutral",
    };
  }

  return {
    healthText: "fixture",
    healthClass: "chip fixture",
    modeText: "replay-safe",
    modeClass: "chip neutral",
  };
}

function computeBounds(assets) {
  if (!assets.length) {
    return { minLat: 0, maxLat: 1, minLon: 0, maxLon: 1 };
  }

  const lats = assets.map((asset) => asset.latitude);
  const lons = assets.map((asset) => asset.longitude);
  let minLat = Math.min(...lats);
  let maxLat = Math.max(...lats);
  let minLon = Math.min(...lons);
  let maxLon = Math.max(...lons);
  const latPad = Math.max((maxLat - minLat) * 0.22, 1.2);
  const lonPad = Math.max((maxLon - minLon) * 0.22, 1.2);
  minLat -= latPad;
  maxLat += latPad;
  minLon -= lonPad;
  maxLon += lonPad;
  return { minLat, maxLat, minLon, maxLon };
}

function project(asset, bounds) {
  const x = ((asset.longitude - bounds.minLon) / Math.max(bounds.maxLon - bounds.minLon, 1)) * 100;
  const y = (1 - (asset.latitude - bounds.minLat) / Math.max(bounds.maxLat - bounds.minLat, 1)) * 100;
  return {
    left: `${Math.min(Math.max(x, 6), 94)}%`,
    top: `${Math.min(Math.max(y, 10), 90)}%`,
  };
}

function appendMessage(role, text) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  article.innerHTML = `
    <p class="message-role">${role === "assistant" ? "atlas" : "operator"}</p>
    <p class="message-body">${text}</p>
  `;
  dom.chatLog.append(article);
  while (dom.chatLog.children.length > 4) {
    dom.chatLog.firstElementChild?.remove();
  }
  dom.chatLog.scrollTop = dom.chatLog.scrollHeight;
}

function setChannelNote(text) {
  if (!dom.channelNote) {
    return;
  }
  dom.channelNote.textContent = text || "";
  dom.channelNote.hidden = !text;
}

function applyPlannerTelemetry(planner) {
  if (!planner) {
    state.plannerFallbackActive = false;
    return "";
  }

  if (planner.mode === "fallback") {
    state.plannerFallbackActive = true;
    return planner.detail;
  }

  if (planner.mode === "live" && state.plannerFallbackActive) {
    state.plannerFallbackActive = false;
    return "Planner restored.";
  }

  state.plannerFallbackActive = false;
  return "";
}

function renderPlannerChip() {
  if (!dom.plannerChip) {
    return;
  }

  dom.plannerChip.hidden = !state.plannerFallbackActive;
}

function seedTranscript() {
  if (state.transcriptSeeded) {
    return;
  }

  dom.chatLog.innerHTML = "";
  const alert = currentAlert();
  const opening = alert
    ? `Atlas online. ${alert.asset_name} is in focus.`
    : "Atlas online. No accepted alert right now.";
  appendMessage("assistant", opening);

  state.transcriptSeeded = true;
}

function selectAsset(assetId) {
  if (!assetId || state.selectedAssetId === assetId) {
    return;
  }
  state.selectedAssetId = assetId;
  if (isMobileSheetMode()) {
    setMobileSheet("site");
  }
  renderMap();
  renderDrawer();
}

function clearLiveMapMarkers() {
  state.mapMarkers.forEach((marker) => marker.remove());
  state.mapMarkers = [];
}

function currentMapZoom() {
  if (!state.map) {
    return 1.4;
  }
  return state.map.getZoom();
}

function isMobileSheetMode() {
  return window.matchMedia("(max-width: 760px)").matches;
}

function setMobileSheet(target) {
  state.mobileSheet = isMobileSheetMode() ? target : null;
  dom.channelPanel?.classList.toggle("sheet-open", state.mobileSheet === "chat");
  dom.drawerPanel?.classList.toggle("sheet-open", state.mobileSheet === "site");
}

function focusMapOnAsset(asset, { immediate = false } = {}) {
  if (!state.map || !asset) {
    return;
  }

  const targetZoom = Math.max(currentMapZoom(), 3.25);
  const options = {
    center: [asset.longitude, asset.latitude],
    zoom: targetZoom,
    duration: immediate ? 0 : 900,
    essential: true,
  };

  state.map.easeTo(options);
}

function fitMapToAssets() {
  if (!state.map || !state.assets.length || !window.maplibregl) {
    return;
  }

  const bounds = new window.maplibregl.LngLatBounds();
  state.assets.forEach((asset) => bounds.extend([asset.longitude, asset.latitude]));
  state.map.fitBounds(bounds, {
    padding: 120,
    maxZoom: state.assets.length === 1 ? 7 : 2.8,
    duration: 0,
  });
}

function syncLiveMapMarkers() {
  if (!state.map || !state.mapReady || !window.maplibregl) {
    return;
  }

  clearLiveMapMarkers();
  state.assets.forEach((asset) => {
    const alert = alertForAsset(asset.asset_id);
    const selected = state.selectedAssetId === asset.asset_id;
    const markerEl = document.createElement("button");
    markerEl.className = [
      "map-marker",
      alert ? "alert" : "quiet",
      selected ? "selected" : "",
      asset.hero ? "hero" : "",
    ]
      .filter(Boolean)
      .join(" ");
    markerEl.type = "button";
    markerEl.setAttribute("aria-label", `Focus ${asset.asset_name}`);
    markerEl.addEventListener("click", () => {
      selectAsset(asset.asset_id);
      appendMessage("assistant", `Map focused on ${asset.asset_name}.`);
    });

    const marker = new window.maplibregl.Marker({ element: markerEl, anchor: "center" })
      .setLngLat([asset.longitude, asset.latitude])
      .addTo(state.map);

    state.mapMarkers.push(marker);
  });
}

function ensureLiveMap() {
  if (state.map || !dom.mapCanvas || !window.maplibregl) {
    return;
  }

  state.map = new window.maplibregl.Map({
    container: dom.mapCanvas,
    style: "https://demotiles.maplibre.org/globe.json",
    center: [0, 15],
    zoom: 1.4,
    attributionControl: true,
  });

  state.map.addControl(new window.maplibregl.NavigationControl({ visualizePitch: true }), "top-right");

  state.map.on("load", () => {
    state.mapReady = true;
    dom.mapStage.classList.add("is-live-map");
    fitMapToAssets();
    syncLiveMapMarkers();
    const selected = selectedAsset();
    if (selected) {
      focusMapOnAsset(selected, { immediate: true });
    }
  });
}

function focusLatestAlert() {
  const alert = currentAlert();
  if (!alert) {
    appendMessage("assistant", "No accepted alert to focus.");
    return;
  }

  selectAsset(alert.asset_id);
  appendMessage(
    "assistant",
    `Focused ${alert.asset_name}. ${humanizeSlug(alert.event_type)} with ${Math.round(alert.confidence * 100)}% confidence.`,
  );
}

function explainCurrentDecision() {
  const asset = selectedAsset();
  const alert = asset ? alertForAsset(asset.asset_id) : null;

  if (alert) {
    appendMessage(
      "assistant",
      `${alert.asset_name}: ${alert.why} Action is ${humanizeSlug(alert.action)} because the disruption is macro-visible and operator-relevant.`,
    );
    return;
  }

  if (asset && hasCompareForAsset(asset.asset_id) && state.currentFrame.accepted_for_alerting === false) {
    appendMessage(
      "assistant",
      `${asset.asset_name}: current frame stayed local. Filter path held it before alerting, so there is no accepted escalation.`,
    );
    return;
  }

  appendMessage(
    "assistant",
    "No active alert on the selected site. Current shell can explain accepted alerts, suppressed compares, replay state, and watchlist focus.",
  );
}

function compareSelectedSite() {
  const asset = selectedAsset();
  if (!asset || !hasCompareForAsset(asset.asset_id)) {
    appendMessage(
      "assistant",
      "The selected site is not the active compare pair right now. Focus the latest alert or the replay hero asset first.",
    );
    return;
  }

  appendMessage(
    "assistant",
    `${asset.asset_name}: current ${formatTimestamp(state.currentFrame.frame.captured_at)} versus baseline ${formatTimestamp(state.baselineFrame.frame.captured_at)}. ${state.currentFrame.overlay_ref ? "Overlay ready." : "Overlay held."}`,
  );
}

function replaySummary() {
  if (!state.replay) {
    appendMessage("assistant", "Replay state unavailable.");
    return;
  }

  appendMessage(
    "assistant",
    `Replay is ${state.replay.running ? "running" : "idle"}. Asset ${compactLabel(state.replay.asset_id)}. Scenario ${compactLabel(state.replay.scenario_id)}. Hero ${compactLabel(state.replay.hero_asset_id)}.`,
  );
}

function watchlistSummary() {
  if (!state.assets.length) {
    appendMessage("assistant", "Watchlist unavailable.");
    return;
  }

  const assetList = state.assets.map((asset) => asset.asset_name).join(", ");
  appendMessage("assistant", `Watchlist: ${assetList}.`);
}

function applyAgentResponse(response) {
  if (Array.isArray(response.alerts) && response.alerts.length) {
    state.alerts = response.alerts;
  }

  if (response.compare) {
    state.currentFrame = response.compare.current_frame;
    state.baselineFrame = response.compare.baseline_frame;
  }

  if (response.focus_asset_id) {
    state.selectedAssetId = response.focus_asset_id;
  }

  renderTopbar();
  renderMap();
  renderDrawer();
}

async function queryAgent(rawText) {
  const response = await fetch(urls.agentQuery, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      query: rawText,
      selected_asset_id: state.selectedAssetId,
    }),
  });

  if (!response.ok) {
    throw new Error(`/agent/query returned ${response.status}`);
  }

  return response.json();
}

function handleCommandLocally(rawText) {
  const text = rawText.trim();
  if (!text) {
    return;
  }

  const command = text.toLowerCase();

  if (command.includes("latest") || command.includes("biggest") || command.includes("focus")) {
    focusLatestAlert();
    return;
  }

  if (command.includes("explain") || command.includes("why")) {
    explainCurrentDecision();
    return;
  }

  if (command.includes("compare") || command.includes("baseline")) {
    compareSelectedSite();
    return;
  }

  if (command.includes("replay") || command.includes("scenario")) {
    replaySummary();
    return;
  }

  if (command.includes("watchlist") || command.includes("assets")) {
    watchlistSummary();
    return;
  }

  if (command.includes("hero")) {
    const hero = state.assets.find((asset) => asset.hero) || selectedAsset();
    if (hero) {
      selectAsset(hero.asset_id);
      appendMessage("assistant", `Focused hero asset ${hero.asset_name}.`);
    }
    return;
  }

  appendMessage(
    "assistant",
    "Supported commands right now: focus latest alert, explain current decision, compare latest vs baseline, show replay state, or list watchlist assets.",
  );
}

async function handleCommand(rawText) {
  const text = rawText.trim();
  if (!text) {
    return;
  }

  appendMessage("user", text);

  try {
    const response = await queryAgent(text);
    const channelNote = applyPlannerTelemetry(response.planner);
    applyAgentResponse(response);
    appendMessage("assistant", response.summary);
    setChannelNote(channelNote);
    renderPlannerChip();
  } catch (error) {
    state.plannerFallbackActive = false;
    renderPlannerChip();
    handleCommandLocally(text);
    setChannelNote("Agent backend unavailable. Local command fallback active.");
  }
}

function renderTopbar() {
  const summary = topStatus();
  dom.healthChip.textContent = summary.healthText;
  dom.healthChip.className = summary.healthClass;
  dom.modeChip.textContent = summary.modeText;
  dom.modeChip.className = summary.modeClass;
  dom.alertChip.textContent = `${state.alerts.length} ${state.alerts.length === 1 ? "alert" : "alerts"}`;
  dom.alertChip.className = state.alerts.length ? "chip degraded" : "chip neutral";
  renderPlannerChip();
}

function renderMap() {
  const selected = selectedAsset();
  const alert = selected ? alertForAsset(selected.asset_id) : currentAlert();
  const bounds = computeBounds(state.assets);

  ensureLiveMap();

  if (!selected) {
    dom.mapMarkers.innerHTML = "";
    dom.mapTrustState.textContent = "trust pending";
    dom.mapTrustState.className = "map-trust-pill neutral";
    return;
  }

  if (state.mapReady) {
    dom.mapMarkers.innerHTML = "";
    syncLiveMapMarkers();
    focusMapOnAsset(selected);
  } else {
    dom.mapMarkers.innerHTML = state.assets
      .map((asset) => {
        const position = project(asset, bounds);
        const isSelected = selected?.asset_id === asset.asset_id;
        const isAlert = state.alerts.some((item) => item.asset_id === asset.asset_id);
        const classes = [
          "marker",
          isSelected ? "selected" : "",
          isAlert ? "alert" : "",
          asset.hero ? "hero" : "",
        ]
          .filter(Boolean)
          .join(" ");
        return `
          <button
            class="${classes || "marker quiet"}"
            type="button"
            data-asset-id="${asset.asset_id}"
            style="left:${position.left};top:${position.top};"
            aria-label="Focus ${asset.asset_name}"
          >
            <span class="marker-core"></span>
            <span class="marker-label">${asset.asset_name}</span>
          </button>
        `;
      })
      .join("");

    dom.mapMarkers.querySelectorAll(".marker").forEach((button) => {
      button.addEventListener("click", () => {
        const assetId = button.dataset.assetId;
        if (!assetId) {
          return;
        }
        selectAsset(assetId);
        const asset = state.assets.find((item) => item.asset_id === assetId);
        if (asset) {
          appendMessage("assistant", `Map focused on ${asset.asset_name}.`);
        }
      });
    });
  }

  dom.mapTrustState.textContent = alert ? humanizeSlug(alert.action) : currentStatusLabel(selected.asset_id);
  dom.mapTrustState.className = alert
    ? "map-trust-pill degraded"
    : state.currentFrame?.accepted_for_alerting === true
      ? "map-trust-pill live"
      : "map-trust-pill neutral";
}

function renderDrawer() {
  const selected = selectedAsset();
  const alert = selected ? alertForAsset(selected.asset_id) : null;

  if (!selected) {
    dom.siteName.textContent = "Waiting for selection";
    dom.siteImpact.textContent = "quiet";
    dom.siteImpact.className = "status-pill idle";
    dom.siteSummary.textContent = "Choose a site or ask the agent to focus the latest alert.";
    dom.siteRegion.textContent = "-";
    dom.siteType.textContent = "-";
    dom.siteCoords.textContent = "-";
    return;
  }

  dom.siteName.textContent = selected.asset_name;
  dom.siteImpact.textContent = alert ? alert.severity : currentStatusLabel(selected.asset_id);
  dom.siteImpact.className = siteImpactClass(alert ? alert.severity : currentStatusLabel(selected.asset_id));
  dom.siteSummary.textContent = alert
    ? alert.why
    : "Watch posture active on this site.";
  dom.siteRegion.textContent = compactLabel(selected.region);
  dom.siteType.textContent = humanizeSlug(selected.asset_type);
  dom.siteCoords.textContent = `${selected.latitude.toFixed(3)}, ${selected.longitude.toFixed(3)}`;

  if (hasCompareForAsset(selected.asset_id)) {
    dom.currentTitle.textContent = state.currentFrame.frame.frame_id;
    dom.currentNote.textContent =
      state.currentFrame.accepted_for_alerting === true
        ? "Accepted for alerting."
        : "Held before alerting.";
    dom.currentStatus.textContent = currentStatusLabel(selected.asset_id);
    dom.currentCaptured.textContent = formatTimestamp(state.currentFrame.frame.captured_at);
    dom.baselineTitle.textContent = state.baselineFrame.frame.frame_id;
    dom.baselineNote.textContent = "Reference frame.";
    dom.baselineCaptured.textContent = formatTimestamp(state.baselineFrame.frame.captured_at);
    dom.baselineSource.textContent = humanizeSlug(state.baselineFrame.frame.source);
  } else {
    dom.currentTitle.textContent = "No compare";
    dom.currentNote.textContent = "Focus the latest alert to load evidence.";
    dom.currentStatus.textContent = "watch";
    dom.currentCaptured.textContent = "n/a";
    dom.baselineTitle.textContent = "No compare";
    dom.baselineNote.textContent = "No baseline in focus.";
    dom.baselineCaptured.textContent = "n/a";
    dom.baselineSource.textContent = "n/a";
  }
}

function renderHealthFallback() {
  dom.healthChip.textContent = "degraded";
  dom.healthChip.className = "chip degraded";
  dom.modeChip.textContent = "health missing";
  dom.modeChip.className = "chip neutral";
  renderPlannerChip();
  setChannelNote("Backend health degraded. Local command fallback active.");
}

async function loadJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${url.pathname} returned ${response.status}`);
  }
  return response.json();
}

function pickInitialSelection() {
  if (state.selectedAssetId) {
    return;
  }

  const latest = currentAlert();
  if (latest) {
    state.selectedAssetId = latest.asset_id;
    return;
  }

  if (state.currentFrame?.frame?.asset_id) {
    state.selectedAssetId = state.currentFrame.frame.asset_id;
    return;
  }

  if (state.assets[0]) {
    state.selectedAssetId = state.assets[0].asset_id;
  }
}

function bindEvents() {
  dom.sheetToggles.forEach((button) => {
    button.addEventListener("click", () => {
      const target = button.dataset.sheetTarget || null;
      if (!target || !isMobileSheetMode()) {
        return;
      }
      setMobileSheet(state.mobileSheet === target ? null : target);
    });
  });

  dom.chatForm.addEventListener("submit", (event) => {
    event.preventDefault();
    if (isMobileSheetMode()) {
      setMobileSheet("chat");
    }
    handleCommand(dom.chatInput.value);
    dom.chatInput.value = "";
  });

  window.addEventListener("resize", () => {
    if (!isMobileSheetMode()) {
      setMobileSheet(null);
    }
  });
}

async function boot() {
  bindEvents();

  const [
    healthResult,
    assetsResult,
    alertsResult,
    replayResult,
    currentResult,
    baselineResult,
    metricsResult,
  ] = await Promise.allSettled([
    loadJson(urls.health),
    loadJson(urls.assets),
    loadJson(urls.alerts),
    loadJson(urls.replay),
    loadJson(urls.current),
    loadJson(urls.baseline),
    loadJson(urls.metrics),
  ]);

  if (healthResult.status === "fulfilled") {
    state.health = healthResult.value;
  }
  if (assetsResult.status === "fulfilled") {
    state.assets = assetsResult.value;
  }
  if (alertsResult.status === "fulfilled") {
    state.alerts = alertsResult.value;
  }
  if (replayResult.status === "fulfilled") {
    state.replay = replayResult.value;
  }
  if (currentResult.status === "fulfilled") {
    state.currentFrame = currentResult.value;
  }
  if (baselineResult.status === "fulfilled") {
    state.baselineFrame = baselineResult.value;
  }
  if (metricsResult.status === "fulfilled") {
    state.metrics = metricsResult.value;
  }

  pickInitialSelection();
  renderTopbar();
  renderMap();
  renderDrawer();
  seedTranscript();
  setMobileSheet(null);

  if (healthResult.status !== "fulfilled") {
    renderHealthFallback();
  }
}

boot();
