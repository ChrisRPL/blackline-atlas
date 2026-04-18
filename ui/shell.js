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
  liveAlerts: [],
  replay: null,
  metrics: null,
  selectedAssetId: null,
  selectedSiteContext: null,
  selectedSiteLoading: false,
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

function evidenceLabel(value) {
  const labels = {
    live_demo: "live",
    reference_event: "archive",
    reference_control: "control",
    watch_only: "watch",
    loading: "loading",
  };
  return labels[value] || humanizeSlug(value);
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

function liveAlert() {
  return state.liveAlerts[0] || null;
}

function liveAlertForAsset(assetId) {
  return state.liveAlerts.find((alert) => alert.asset_id === assetId) || null;
}

function selectedSiteContext() {
  if (!state.selectedSiteContext) {
    return null;
  }
  if (
    state.selectedSiteContext.focus_asset_id
    && state.selectedSiteContext.focus_asset_id !== state.selectedAssetId
  ) {
    return null;
  }
  return state.selectedSiteContext;
}

function selectedCompare() {
  return selectedSiteContext()?.compare || null;
}

function selectedSiteAlerts() {
  const context = selectedSiteContext();
  return Array.isArray(context?.alerts) ? context.alerts : [];
}

function hasCompareForAsset(assetId) {
  return selectedCompare()?.asset_id === assetId;
}

function siteEvidenceState(asset) {
  if (!asset) {
    return "watch_only";
  }
  if (asset.asset_id === selectedAsset()?.asset_id && state.selectedSiteLoading) {
    return "loading";
  }
  return compactLabel(asset.evidence_state, "watch_only");
}

function selectedStatusLabel(asset) {
  const alert = selectedSiteAlerts()[0] || null;
  const compare = selectedCompare();
  if (alert) {
    return alert.severity;
  }
  if (!compare || compare.asset_id !== asset?.asset_id) {
    return "watch";
  }
  if (compare.current_frame.accepted_for_alerting === true) {
    return "accepted";
  }
  if (compare.current_frame.accepted_for_alerting === false) {
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
  const alert = liveAlert();
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
  void loadSelectedSiteContext(assetId);
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
  dom.mapStage?.classList.toggle("site-sheet-open", state.mobileSheet === "site");
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
    const alert = liveAlertForAsset(asset.asset_id);
    const selected = state.selectedAssetId === asset.asset_id;
    const evidenceState = siteEvidenceState(asset);
    const markerEl = document.createElement("button");
    markerEl.className = [
      "map-marker",
      alert ? "alert" : evidenceState,
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
  const alert = liveAlert();
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
  const alert = selectedSiteAlerts()[0] || null;
  const compare = selectedCompare();

  if (alert) {
    appendMessage(
      "assistant",
      `${alert.asset_name}: ${alert.why} Action is ${humanizeSlug(alert.action)} because the disruption is macro-visible and operator-relevant.`,
    );
    return;
  }

  if (asset && compare?.asset_id === asset.asset_id && compare.current_frame.accepted_for_alerting === false) {
    appendMessage(
      "assistant",
      `${asset.asset_name}: reference control stayed local. Compare exists, but no defendable disruption cleared the alert threshold.`,
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
  const compare = selectedCompare();
  if (!asset || compare?.asset_id !== asset.asset_id) {
    appendMessage(
      "assistant",
      "Selected site compare is not loaded yet.",
    );
    return;
  }

  appendMessage(
    "assistant",
    `${asset.asset_name}: current ${formatTimestamp(compare.current_frame.frame.captured_at)} versus baseline ${formatTimestamp(compare.baseline_frame.frame.captured_at)}. ${compare.current_frame.overlay_ref ? "Overlay ready." : "Reference compare only."}`,
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

  const counts = state.assets.reduce(
    (memo, asset) => {
      memo[siteEvidenceState(asset)] = (memo[siteEvidenceState(asset)] || 0) + 1;
      return memo;
    },
    {},
  );
  appendMessage(
    "assistant",
    `Watchlist: ${state.assets.length} sites. ${counts.live_demo || 0} live demo, ${counts.reference_event || 0} reference events, ${counts.reference_control || 0} controls.`,
  );
}

function applyAgentResponse(response) {
  if (
    (response.tool === "latest_alerts" || response.tool === "biggest_disruptions")
    && Array.isArray(response.alerts)
  ) {
    state.liveAlerts = response.alerts;
  }

  if (response.compare || response.tool === "site_compare" || response.tool === "explain_alert") {
    state.selectedSiteContext = response;
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

async function querySiteCompare(assetId) {
  const response = await fetch(urls.agentQuery, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      tool: "site_compare",
      site_id: assetId,
    }),
  });

  if (!response.ok) {
    throw new Error(`/agent/query returned ${response.status}`);
  }

  return response.json();
}

async function loadSelectedSiteContext(assetId) {
  if (!assetId) {
    return;
  }

  state.selectedSiteLoading = true;
  renderMap();
  renderDrawer();

  try {
    const response = await querySiteCompare(assetId);
    if (state.selectedAssetId === assetId) {
      state.selectedSiteContext = response;
    }
  } catch (error) {
    if (state.selectedAssetId === assetId) {
      state.selectedSiteContext = null;
    }
  } finally {
    if (state.selectedAssetId === assetId) {
      state.selectedSiteLoading = false;
      renderMap();
      renderDrawer();
    }
  }
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
  dom.alertChip.textContent = `${state.liveAlerts.length} ${state.liveAlerts.length === 1 ? "alert" : "alerts"}`;
  dom.alertChip.className = state.liveAlerts.length ? "chip degraded" : "chip neutral";
  renderPlannerChip();
}

function renderMap() {
  const selected = selectedAsset();
  const alert = selected ? liveAlertForAsset(selected.asset_id) : liveAlert();
  const bounds = computeBounds(state.assets);

  ensureLiveMap();

  if (!selected) {
    dom.mapMarkers.innerHTML = "";
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
        const isAlert = state.liveAlerts.some((item) => item.asset_id === asset.asset_id);
        const evidenceState = siteEvidenceState(asset);
        const classes = [
          "marker",
          isSelected ? "selected" : "",
          isAlert ? "alert" : "",
          !isAlert ? evidenceState : "",
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

}

function renderDrawer() {
  const selected = selectedAsset();
  const context = selectedSiteContext();
  const compare = selectedCompare();
  const alert = selectedSiteAlerts()[0] || null;
  const evidenceState = siteEvidenceState(selected);

  if (!selected) {
    dom.siteName.textContent = "Select a site";
    dom.siteImpact.textContent = "idle";
    dom.siteImpact.className = "status-pill idle";
    dom.siteSummary.textContent = "Map click or command. Compare lands here.";
    dom.siteRegion.textContent = "-";
    dom.siteType.textContent = "-";
    dom.siteCoords.textContent = "-";
    return;
  }

  dom.siteName.textContent = selected.asset_name;
  dom.siteImpact.textContent = alert
    ? alert.severity
    : evidenceState === "reference_control"
      ? "control"
      : evidenceState === "reference_event"
        ? "archive"
        : evidenceState === "live_demo"
          ? "demo"
          : "watch";
  dom.siteImpact.className = siteImpactClass(
    alert
      ? alert.severity
      : evidenceState === "reference_event"
        ? "medium"
        : evidenceState === "live_demo"
          ? "accepted"
          : "low",
  );
  dom.siteSummary.textContent = state.selectedSiteLoading
    ? "Loading compare."
    : alert
      ? alert.why
      : context?.summary || "Reference compare ready.";
  dom.siteRegion.textContent = compactLabel(selected.region);
  dom.siteType.textContent = `${humanizeSlug(selected.asset_type)} / ${evidenceLabel(evidenceState)}`;
  dom.siteCoords.textContent = `${selected.latitude.toFixed(2)}, ${selected.longitude.toFixed(2)}`;

  if (compare?.asset_id === selected.asset_id) {
    dom.currentTitle.textContent = formatTimestamp(compare.current_frame.frame.captured_at);
    dom.currentNote.textContent =
      evidenceState === "reference_event"
        ? "Visible disruption."
        : evidenceState === "reference_control"
          ? "No clear disruption."
          : compare.current_frame.accepted_for_alerting === true
            ? "Alert threshold crossed."
            : "Held below threshold.";
    dom.currentStatus.textContent = humanizeSlug(selectedStatusLabel(selected));
    dom.currentCaptured.textContent = "";
    dom.baselineTitle.textContent = formatTimestamp(compare.baseline_frame.frame.captured_at);
    dom.baselineNote.textContent = "Last clear baseline.";
    dom.baselineCaptured.textContent = evidenceState === "live_demo" ? "live lane" : "archive lane";
    dom.baselineSource.textContent = "";
  } else {
    dom.currentTitle.textContent = "Compare pending";
    dom.currentNote.textContent = state.selectedSiteLoading
      ? "Fetching site evidence."
      : "No evidence loaded.";
    dom.currentStatus.textContent = "watch";
    dom.currentCaptured.textContent = "n/a";
    dom.baselineTitle.textContent = "Baseline pending";
    dom.baselineNote.textContent = "Waiting for compare.";
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

  const latest = liveAlert();
  if (latest) {
    state.selectedAssetId = latest.asset_id;
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
    state.liveAlerts = alertsResult.value;
  }
  if (replayResult.status === "fulfilled") {
    state.replay = replayResult.value;
  }
  if (metricsResult.status === "fulfilled") {
    state.metrics = metricsResult.value;
  }

  pickInitialSelection();
  if (state.selectedAssetId) {
    await loadSelectedSiteContext(state.selectedAssetId);
  }
  renderTopbar();
  renderMap();
  renderDrawer();
  seedTranscript();
  setMobileSheet(liveAlert() ? "site" : null);

  if (healthResult.status !== "fulfilled") {
    renderHealthFallback();
  }
}

boot();
