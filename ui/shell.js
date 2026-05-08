const urls = {
  health: new URL("/health", window.location.origin),
  modelStatus: new URL("/model/status", window.location.origin),
  assets: new URL("/assets", window.location.origin),
  leads: new URL("/leads", window.location.origin),
  leadRefresh: new URL("/leads/refresh", window.location.origin),
  snapshot: new URL("/replay/snapshot", window.location.origin),
  currentEvidence: new URL("/evidence/current", window.location.origin),
  alerts: new URL("/alerts", window.location.origin),
  replay: new URL("/replay/status", window.location.origin),
  current: new URL("/frames/current", window.location.origin),
  baseline: new URL("/frames/baseline", window.location.origin),
  metrics: new URL("/metrics", window.location.origin),
  agentQuery: new URL("/agent/query", window.location.origin),
};

const state = {
  health: null,
  modelStatus: null,
  assets: [],
  leads: [],
  liveAlerts: [],
  replay: null,
  metrics: null,
  selectedAssetId: null,
  selectedLeadId: null,
  selectedSiteContext: null,
  selectedEvidence: null,
  selectedAnalyst: null,
  selectedSiteLoading: false,
  transcriptSeeded: false,
  map: null,
  mapMarkers: [],
  mapReady: false,
  mapLayerEventsBound: false,
  mobileSheet: null,
  plannerFallbackActive: false,
  leadRefreshLoading: false,
  userLocation: null,
  cameraMode: "globe",
  lastCameraIntentKey: null,
  missionTimers: [],
};

const dom = {
  healthChip: document.querySelector("#health-chip"),
  modeChip: document.querySelector("#mode-chip"),
  modelChip: document.querySelector("#model-chip"),
  alertChip: document.querySelector("#alert-chip"),
  plannerChip: document.querySelector("#planner-chip"),
  mapStage: document.querySelector("#map-stage"),
  mapCanvas: document.querySelector("#map-canvas"),
  mapMarkers: document.querySelector("#map-markers"),
  stageTitle: document.querySelector("#stage-title"),
  stageSubtitle: document.querySelector("#stage-subtitle"),
  stageClock: document.querySelector("#stage-clock"),
  missionSteps: document.querySelectorAll(".mission-step"),
  leadPopover: document.querySelector("#lead-popover"),
  leadPopoverKicker: document.querySelector("#lead-popover-kicker"),
  leadPopoverTitle: document.querySelector("#lead-popover-title"),
  leadPopoverRegion: document.querySelector("#lead-popover-region"),
  leadPopoverDate: document.querySelector("#lead-popover-date"),
  leadPopoverSummary: document.querySelector("#lead-popover-summary"),
  leadPopoverStatus: document.querySelector("#lead-popover-status"),
  leadPopoverLink: document.querySelector("#lead-popover-link"),
  leadPopoverInspect: document.querySelector("#lead-popover-inspect"),
  leadRefresh: document.querySelector("#lead-refresh"),
  channelPanel: document.querySelector(".channel-panel"),
  drawerPanel: document.querySelector(".drawer-panel"),
  siteName: document.querySelector("#site-name"),
  siteImpact: document.querySelector("#site-impact"),
  siteSummary: document.querySelector("#site-summary"),
  siteRegion: document.querySelector("#site-region"),
  siteType: document.querySelector("#site-type"),
  siteCoords: document.querySelector("#site-coords"),
  modelGateDecision: document.querySelector("#model-gate-decision"),
  modelGateSummary: document.querySelector("#model-gate-summary"),
  modelGateStats: document.querySelector("#model-gate-stats"),
  liquidAnalystCard: document.querySelector("#liquid-analyst-card"),
  liquidAnalystTitle: document.querySelector("#liquid-analyst-title"),
  liquidAnalystSummary: document.querySelector("#liquid-analyst-summary"),
  liquidAnalystModel: document.querySelector("#liquid-analyst-model"),
  liquidAnalystAction: document.querySelector("#liquid-analyst-action"),
  liquidAnalystConfidence: document.querySelector("#liquid-analyst-confidence"),
  currentTitle: document.querySelector("#current-title"),
  currentNote: document.querySelector("#current-note"),
  currentStatus: document.querySelector("#current-status"),
  currentCaptured: document.querySelector("#current-captured"),
  currentFrame: document.querySelector("#current-frame"),
  currentImage: document.querySelector("#current-image"),
  currentImageCaption: document.querySelector("#current-image-caption"),
  baselineTitle: document.querySelector("#baseline-title"),
  baselineNote: document.querySelector("#baseline-note"),
  baselineCaptured: document.querySelector("#baseline-captured"),
  baselineSource: document.querySelector("#baseline-source"),
  baselineFrame: document.querySelector("#baseline-frame"),
  baselineImage: document.querySelector("#baseline-image"),
  baselineImageCaption: document.querySelector("#baseline-image-caption"),
  signalAction: document.querySelector("#signal-action"),
  signalSeverity: document.querySelector("#signal-severity"),
  signalConfidence: document.querySelector("#signal-confidence"),
  metricsAlerts: document.querySelector("#metrics-alerts"),
  metricsSuppressed: document.querySelector("#metrics-suppressed"),
  metricsDownlink: document.querySelector("#metrics-downlink"),
  chatLog: document.querySelector("#chat-log"),
  chatForm: document.querySelector("#chat-form"),
  chatInput: document.querySelector("#chat-input"),
  channelNote: document.querySelector("#channel-note"),
  sheetToggles: document.querySelectorAll(".sheet-toggle"),
};

const missionStepOrder = ["parse", "fetch", "focus", "evidence", "summarize"];

function compactLabel(value, fallback = "none") {
  return value === null || value === undefined || value === "" ? fallback : value;
}

function humanizeSlug(value) {
  return compactLabel(value).replaceAll("_", " ").replaceAll("-", " ");
}

function truncateText(value, maxLength = 240) {
  const text = compactLabel(value, "").replace(/\s+/g, " ").trim();
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 1).trim()}...`;
}

function actionLabel(value) {
  const labels = {
    downlink_now: "send evidence now",
    defer: "review next",
    discard: "no visual confirmation",
    watch: "watch",
    unconfirmed: "unconfirmed",
  };
  return labels[value] || humanizeSlug(value);
}

function analystBackendLabel(report) {
  if (!report) {
    return "Image analyst waiting";
  }
  if (report.backend === "liquid_vlm_http") {
    return "Liquid VLM live";
  }
  return "Reference analyst";
}

function evidenceLabel(value) {
  const labels = {
    live_demo: "reference evidence",
    reference_event: "confirmed disruption",
    reference_control: "control",
    watch_only: "monitored",
    loading: "loading",
  };
  return labels[value] || humanizeSlug(value);
}

function satelliteScopeLabel(bundle) {
  const labels = {
    exact_aoi: "exact satellite AOI",
    nearby_aoi: "nearby satellite AOI",
    regional_aoi: "regional satellite context",
    satellite_context_only: "satellite context only",
  };
  return labels[bundle?.scope] || "satellite context";
}

function satelliteUsability(bundle) {
  if (!bundle) {
    return "unavailable";
  }
  if (bundle.usability) {
    return bundle.usability;
  }
  return bundle.usable_for_evidence ? "direct_clear" : "context_only";
}

function satelliteUsabilityLabel(bundle) {
  const labels = {
    direct_clear: "clear view",
    cloud_limited: "limited view",
    context_only: "context view",
    unavailable: "unavailable",
  };
  return labels[satelliteUsability(bundle)] || "unknown evidence quality";
}

function satelliteEvidenceNote(bundle) {
  if (!bundle) {
    return "";
  }
  const usability = satelliteUsability(bundle);
  if (usability === "direct_clear") {
    return " Evidence note: the before/after images are clear enough for visual review.";
  }
  if (usability === "cloud_limited") {
    return " Evidence note: clouds or low visibility limit this view. Atlas is not claiming visual confirmation from these frames.";
  }
  if (usability === "context_only") {
    return " Evidence note: context imagery only; use the source report and map position, not model scoring.";
  }
  return " Evidence note: satellite imagery did not resolve for this point.";
}

function isContextOnlyCompare(compare) {
  return Boolean(
    compare?.satellite_evidence
      && satelliteUsability(compare.satellite_evidence) === "context_only",
  );
}

function isModelGatedCompare(compare) {
  if (!compare?.satellite_evidence) {
    return false;
  }
  return ["context_only", "unavailable"].includes(satelliteUsability(compare.satellite_evidence));
}

function analystEndpointReady() {
  return Boolean(state.health?.config?.analyst_http_enabled);
}

function satelliteSweepText() {
  return "Satellite sweep running: tight 5 km AOIs first, nearby 5 km grid next, and context only if evidence imagery cannot resolve.";
}

function sam3EvidenceNote(report) {
  if (!report) {
    return "";
  }
  if (report.decision !== "segmentation_ready" || !report.masks?.length) {
    return "";
  }
  const maxChangeScore = Math.max(
    ...report.masks.map((mask) => mask.temporal_change_score ?? mask.score ?? 0),
  );
  const scoreNote = maxChangeScore ? `, max change ${Math.round(maxChangeScore * 100)}%` : "";
  return ` Segment read: ${report.masks.length} region${report.masks.length === 1 ? "" : "s"}${scoreNote}; ${report.visual_evidence_tags.join(", ")}.`;
}

function frameImageSrc(imageRef) {
  if (!imageRef) {
    return "";
  }
  if (/^(https?:|data:)/i.test(imageRef)) {
    return imageRef;
  }
  const url = new URL("/frame-image", window.location.origin);
  url.searchParams.set("ref", imageRef);
  return url.toString();
}

function setEvidenceFrame(frameNode, imageNode, captionNode, imageRef, caption) {
  if (!frameNode || !imageNode || !captionNode) {
    return;
  }
  const source = frameImageSrc(imageRef);
  if (!source) {
    frameNode.hidden = true;
    frameNode.classList.remove("is-loading", "is-error");
    delete frameNode.dataset.stateLabel;
    imageNode.removeAttribute("src");
    return;
  }
  frameNode.hidden = false;
  frameNode.classList.add("is-loading");
  frameNode.classList.remove("is-error");
  frameNode.dataset.stateLabel = "Loading satellite tile";
  imageNode.hidden = false;
  imageNode.onload = () => {
    frameNode.classList.remove("is-loading", "is-error");
    delete frameNode.dataset.stateLabel;
    imageNode.hidden = false;
  };
  imageNode.onerror = () => {
    frameNode.classList.remove("is-loading");
    frameNode.classList.add("is-error");
    frameNode.dataset.stateLabel = "Satellite image failed to render";
    imageNode.hidden = true;
  };
  imageNode.src = source;
  captionNode.textContent = caption;
}

function clearEvidenceFrames() {
  setEvidenceFrame(dom.currentFrame, dom.currentImage, dom.currentImageCaption, null, "");
  setEvidenceFrame(dom.baselineFrame, dom.baselineImage, dom.baselineImageCaption, null, "");
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

function formatDateLabel(value) {
  if (!value) {
    return "date unknown";
  }

  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) {
    return value;
  }

  return timestamp.toISOString().slice(0, 10);
}

function updateStageClock() {
  if (!dom.stageClock) {
    return;
  }
  dom.stageClock.textContent = new Date().toISOString().slice(11, 16) + " UTC";
}

function setStageReport(title, subtitle) {
  if (dom.stageTitle) {
    dom.stageTitle.textContent = title;
  }
  if (dom.stageSubtitle) {
    dom.stageSubtitle.textContent = subtitle;
  }
}

function clearMissionTimers() {
  state.missionTimers.forEach((timer) => window.clearTimeout(timer));
  state.missionTimers = [];
}

function setMissionStep(activeStep, doneSteps = []) {
  const done = new Set(doneSteps);
  dom.missionSteps.forEach((step) => {
    const key = step.dataset.step;
    step.classList.toggle("active", key === activeStep);
    step.classList.toggle("done", done.has(key));
    step.classList.toggle("idle", key !== activeStep && !done.has(key));
  });
}

function runMissionSequence(activeSteps, finalDoneSteps = activeSteps) {
  clearMissionTimers();
  activeSteps.forEach((step, index) => {
    const timer = window.setTimeout(() => {
      setMissionStep(step, activeSteps.slice(0, index));
    }, index * 180);
    state.missionTimers.push(timer);
  });
  const finalTimer = window.setTimeout(() => {
    setMissionStep(null, finalDoneSteps);
  }, Math.max(activeSteps.length * 180, 300));
  state.missionTimers.push(finalTimer);
}

function missionStepsForResponse(response) {
  const steps = ["parse", "fetch"];
  if (response?.camera || response?.focus_asset_id || response?.focus_lead_id) {
    steps.push("focus");
  }
  if (response?.compare || response?.alerts?.length || response?.analyst_report) {
    steps.push("evidence");
  }
  steps.push("summarize");
  return steps.filter((step, index) => steps.indexOf(step) === index);
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
  if (!state.selectedAssetId) {
    return null;
  }
  return state.assets.find((asset) => asset.asset_id === state.selectedAssetId) || null;
}

function selectedLead() {
  return state.leads.find((lead) => lead.lead_id === state.selectedLeadId) || null;
}

function linkedAssetForLead(lead) {
  if (!lead?.linked_asset_id) {
    return null;
  }
  return state.assets.find((asset) => asset.asset_id === lead.linked_asset_id) || null;
}

function ensureLeadReviewAsset(lead) {
  if (!lead) {
    return null;
  }

  const assetId = lead.linked_asset_id;
  if (!assetId) {
    return null;
  }

  const existing = state.assets.find((asset) => asset.asset_id === assetId);
  if (existing) {
    return existing;
  }

  const asset = {
    asset_id: assetId,
    asset_name: lead.title,
    asset_type: lead.category_guess || "civilian_building_cluster",
    region: lead.region,
    latitude: lead.latitude,
    longitude: lead.longitude,
    hero: false,
    evidence_available: true,
    evidence_state: "watch_only",
  };
  state.assets.push(asset);
  return asset;
}

function reviewAssetForLead(lead) {
  return linkedAssetForLead(lead) || ensureLeadReviewAsset(lead);
}

function liveAlert() {
  return state.liveAlerts[0] || null;
}

function liveAlertForAsset(assetId) {
  return state.liveAlerts.find((alert) => alert.asset_id === assetId) || null;
}

function liveLeadCount() {
  return state.leads.length;
}

function inspectableLeadCount() {
  return state.leads.filter((lead) => Boolean(lead.linked_asset_id)).length;
}

function topLeadMetricText() {
  const count = liveLeadCount();
  if (count) {
    return `${count} live ${count === 1 ? "lead" : "leads"}`;
  }
  const alertCount = state.liveAlerts.length;
  if (alertCount) {
    return `${alertCount} model ${alertCount === 1 ? "alert" : "alerts"}`;
  }
  return "live leads loading";
}

function leadMetricText() {
  const count = liveLeadCount();
  return count ? `${count} live ${count === 1 ? "lead" : "leads"}` : "waiting for live leads";
}

function inspectableMetricText() {
  const count = inspectableLeadCount();
  return count ? `${count} inspectable ${count === 1 ? "site" : "sites"}` : "source-only map";
}

function evidenceMetricText(compare, selected) {
  if (compare?.asset_id === selected?.asset_id && compare.satellite_evidence) {
    const label = satelliteUsabilityLabel(compare.satellite_evidence);
    const size = compare.satellite_evidence.size_km
      ? ` / ${Number(compare.satellite_evidence.size_km).toFixed(1).replace(/\.0$/, "")} km AOI`
      : "";
    return `${label}${size}`;
  }
  if (selected) {
    return "evidence loading";
  }
  return "select a marker";
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

function selectedEvidenceReport() {
  if (!state.selectedEvidence || state.selectedEvidence.asset_id !== state.selectedAssetId) {
    return null;
  }
  return state.selectedEvidence;
}

function selectedAnalystReport() {
  if (state.selectedAnalyst && state.selectedAnalyst.asset_id === state.selectedAssetId) {
    return state.selectedAnalyst;
  }
  const report = selectedSiteContext()?.analyst_report;
  if (!report || report.asset_id !== state.selectedAssetId) {
    return null;
  }
  return report;
}

function compareUsableForVisualAnalysis(compare) {
  if (!compare) {
    return false;
  }
  if (!compare.satellite_evidence) {
    return true;
  }
  const usability = satelliteUsability(compare?.satellite_evidence);
  return usability === "direct_clear" || usability === "cloud_limited";
}

function isContextOnlyFrameCompare(compare) {
  return Boolean(
    compare
      && (
        isContextOnlyCompare(compare)
        || compare.current_frame?.filter_reason === "satellite_context_only"
        || compare.baseline_frame?.filter_reason === "satellite_context_only"
      ),
  );
}

function selectedSiteAlerts() {
  const context = selectedSiteContext();
  return Array.isArray(context?.alerts) ? context.alerts : [];
}

function mergeLeads(nextLeads) {
  if (!Array.isArray(nextLeads) || !nextLeads.length) {
    return;
  }

  const merged = new Map(state.leads.map((lead) => [lead.lead_id, lead]));
  nextLeads.forEach((lead) => {
    if (lead?.lead_id) {
      merged.set(lead.lead_id, lead);
    }
  });
  state.leads = Array.from(merged.values());
}

function leadStatusLabel(lead) {
  if (!lead) {
    return "no marker";
  }
  if (reviewAssetForLead(lead)) {
    return "satellite review ready";
  }
  if (lead.status === "lead_only") {
    return "source-only report";
  }
  return humanizeSlug(lead.status);
}

function formatLeadSummary(lead, maxLength = 300) {
  const raw = compactLabel(lead?.summary, "Live source marker selected.");
  const cleaned = raw
    .replace(/^GDELT Cloud conflict event:\s*/i, "")
    .replace(/\s*Confidence\s+\d+(?:\.\d+)?\.\s*Significance\s+\d+(?:\.\d+)?\.\s*/i, " ")
    .replace(/\s*\d+\s+linked source articles?\.\s*/i, " ")
    .replace(/\s+/g, " ")
    .trim();
  return truncateText(cleaned, maxLength);
}

function regionCodeForLead(lead) {
  const text = `${lead?.region || ""} ${lead?.title || ""}`.toLowerCase();
  if (text.includes("ukraine") || text.includes("kyiv") || text.includes("kherson")) {
    return "UA";
  }
  if (text.includes("gaza") || text.includes("khan younis")) {
    return "GZA";
  }
  if (text.includes("palestine") || text.includes("jabalia")) {
    return "PSE";
  }
  if (text.includes("sudan") || text.includes("darfur") || text.includes("khartoum")) {
    return "SD";
  }
  if (text.includes("lebanon")) {
    return "LB";
  }
  if (text.includes("libya") || text.includes("derna")) {
    return "LY";
  }
  if (text.includes("iran")) {
    return "IR";
  }
  if (text.includes("nigeria") || text.includes("borno")) {
    return "NG";
  }
  if (text.includes("yemen")) {
    return "YE";
  }
  if (text.includes("syria") || text.includes("aleppo") || text.includes("idlib")) {
    return "SY";
  }
  if (text.includes("iraq") || text.includes("mosul") || text.includes("baghdad")) {
    return "IQ";
  }
  if (text.includes("somalia") || text.includes("shabelle")) {
    return "SO";
  }
  if (text.includes("ethiopia")) {
    return "ET";
  }
  if (text.includes("russia")) {
    return "RU";
  }
  if (text.includes("pakistan")) {
    return "PK";
  }
  if (text.includes("kyrgyzstan")) {
    return "KG";
  }
  return "AOI";
}

function countryIso2ForLead(lead) {
  const text = `${lead?.region || ""} ${lead?.title || ""}`.toLowerCase();
  const rules = [
    [
      "UA",
      [
        "ukraine",
        "kyiv",
        "kharkiv",
        "kherson",
        "dnipro",
        "odesa",
        "odessa",
        "donetsk",
        "mariupol",
        "zaporizhzhia",
      ],
    ],
    ["PS", ["gaza", "palestine", "khan younis", "jabalia", "rafah"]],
    ["SD", ["sudan", "darfur", "khartoum", "al-fashir", "elfasher"]],
    ["LB", ["lebanon", "beirut", "south lebanon", "nabatieh"]],
    ["LY", ["libya", "derna", "tripoli"]],
    ["IR", ["iran", "tehran", "isfahan"]],
    ["NG", ["nigeria", "borno"]],
    ["YE", ["yemen", "sanaa", "aden"]],
    ["SY", ["syria", "aleppo", "idlib", "damascus"]],
    ["IQ", ["iraq", "mosul", "baghdad"]],
    ["SO", ["somalia", "shabelle", "mogadishu"]],
    ["ET", ["ethiopia", "amhara", "tigray"]],
    ["RU", ["russia", "belgorod", "kursk"]],
    ["PK", ["pakistan", "balochistan", "khyber"]],
    ["KG", ["kyrgyzstan", "bishkek"]],
    ["MM", ["myanmar", "burma", "rakhine", "mandalay"]],
    ["MX", ["mexico", "sinaloa", "michoacan", "guerrero"]],
    ["CD", ["congo", "goma", "north kivu", "south kivu"]],
    ["HT", ["haiti", "port-au-prince"]],
    ["AF", ["afghanistan", "kabul"]],
  ];
  const match = rules.find(([, aliases]) => aliases.some((alias) => text.includes(alias)));
  return match?.[0] || null;
}

function flagEmojiForIso2(iso2) {
  if (!iso2 || !/^[A-Z]{2}$/.test(iso2)) {
    return "";
  }
  return [...iso2]
    .map((letter) => String.fromCodePoint(127397 + letter.charCodeAt(0)))
    .join("");
}

function countryFlagForLead(lead) {
  return flagEmojiForIso2(countryIso2ForLead(lead));
}

function leadRegionLabel(lead) {
  const flag = countryFlagForLead(lead);
  return `${flag ? `${flag} ` : ""}${compactLabel(lead?.region, "unknown region")}`;
}

function conciseLeadLabel(lead) {
  const label = lead?.region || lead?.title || "source lead";
  return label.split(",")[0].trim();
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

function leadModeSuffix() {
  return state.leads.length ? ` / ${state.leads.length} live leads` : "";
}

function leadFeedNeedsRefresh() {
  if (!state.leads.length) {
    return true;
  }

  const timestamps = state.leads
    .map((lead) => (lead.last_refreshed_at ? new Date(lead.last_refreshed_at).getTime() : NaN))
    .filter((value) => Number.isFinite(value));
  if (!timestamps.length) {
    return true;
  }

  const newestRefresh = Math.max(...timestamps);
  const twelveHoursMs = 12 * 60 * 60 * 1000;
  return Date.now() - newestRefresh > twelveHoursMs;
}

function simsatStatuses() {
  if (!state.health) {
    return [];
  }
  return [state.health.simsat_current.status, state.health.simsat_baseline.status];
}

function simsatLiveReady() {
  const statuses = simsatStatuses();
  return statuses.length === 2 && statuses.every((status) => status === "ready");
}

function simsatFallbackNote(compare) {
  if (
    !state.health?.config?.simsat_required
    || compare?.current_frame?.filter_reason === "simsat_live_frame"
  ) {
    return "";
  }
  if (state.health.simsat_current.status === "ready") {
    if (compare?.current_frame?.filter_reason === "simsat_historical_current_frame") {
      return " Current overpass unavailable; SimSat historical Sentinel image loaded for this AOI.";
    }
    return " SimSat is online, but the current satellite pass has no image for this AOI; cached frame shown.";
  }
  return " SimSat is required but not reachable; cached frame shown.";
}

function topStatus() {
  if (!state.health) {
    return {
      healthText: "degraded",
      healthClass: "chip degraded",
      modeText: "live feed loading",
      modeClass: "chip neutral",
    };
  }

  const liveCount = [
    state.health.config.simsat_current_http_enabled,
    state.health.config.simsat_baseline_http_enabled,
  ].filter(Boolean).length;
  const statuses = simsatStatuses();
  const simsatRequired = state.health.config.simsat_required;
  const simsatMissing = statuses.includes("not_configured");
  const degraded =
    statuses.includes("degraded")
    || state.health.mapbox.status === "degraded"
    || (simsatRequired && simsatMissing);

  if (degraded) {
    return {
      healthText: simsatRequired ? "simsat offline" : "degraded",
      healthClass: "chip degraded",
      modeText: simsatRequired ? `start SimSat :9005${leadModeSuffix()}` : `source feed${leadModeSuffix()}`,
      modeClass: "chip neutral",
    };
  }

  if (liveCount > 0 && simsatLiveReady()) {
    return {
      healthText: "live",
      healthClass: "chip live",
      modeText: `SimSat imagery live${leadModeSuffix()}`,
      modeClass: "chip neutral",
    };
  }

  return {
    healthText: "ready",
    healthClass: "chip neutral",
    modeText: `source feed${leadModeSuffix()}`,
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

function appendMessage(role, text, options = {}) {
  const article = document.createElement("article");
  article.className = `message ${role}${options.thinking ? " thinking" : ""}`;
  const roleNode = document.createElement("p");
  roleNode.className = "message-role";
  roleNode.textContent = role === "assistant" ? "atlas" : "operator";
  const bodyNode = document.createElement("p");
  bodyNode.className = "message-body";
  bodyNode.textContent = text;
  if (options.thinking) {
    const dots = document.createElement("span");
    dots.className = "thinking-dots";
    dots.setAttribute("aria-hidden", "true");
    dots.innerHTML = "<span></span><span></span><span></span>";
    bodyNode.append(" ", dots);
  }
  article.append(roleNode, bodyNode);
  dom.chatLog.append(article);
  while (dom.chatLog.children.length > 7) {
    dom.chatLog.firstElementChild?.remove();
  }
  dom.chatLog.scrollTop = dom.chatLog.scrollHeight;
  return article;
}

function removeMessage(node) {
  if (!node) {
    return;
  }
  node.remove();
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
    return "Planner degraded. Atlas routed this through typed live-context tools.";
  }

  if (planner.mode === "live" && state.plannerFallbackActive) {
    state.plannerFallbackActive = false;
    return "Command service restored.";
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

function renderLeadRefreshButton() {
  if (!dom.leadRefresh) {
    return;
  }
  dom.leadRefresh.disabled = state.leadRefreshLoading;
  dom.leadRefresh.textContent = state.leadRefreshLoading ? "Refreshing" : "Refresh live leads";
}

function renderModelGate() {
  if (!dom.modelChip || !dom.modelGateDecision || !dom.modelGateSummary || !dom.modelGateStats) {
    return;
  }

  dom.modelChip.hidden = true;
  const status = state.modelStatus;
  if (!status) {
    dom.modelChip.textContent = "diagnostics loading";
    dom.modelChip.className = "chip neutral";
    dom.modelGateDecision.textContent = "Diagnostics loading";
    dom.modelGateSummary.textContent = "Technical model diagnostics stay out of the operator view.";
    dom.modelGateStats.textContent = "-";
    return;
  }

  const adapterName = status.candidate_adapter.split("/").pop() || "adapter";
  const adapter = status.adapter_eval;
  const base = status.base_eval;
  const evalCases = status.reported_eval_cases || status.frozen_gold_cases;
  const evalScope = (status.reported_eval_scope || "frozen_gold").replaceAll("_", " ");
  const runtime = (
    status.runtime_authority || status.recommended_runtime || "deterministic_replay"
  ).replaceAll("_", " ");
  const signalRole = (status.adapter_signal_role || "optional_non_authoritative").replaceAll(
    "_",
    " ",
  );
  const latestFailure = Array.isArray(status.acceptance_failures)
    ? status.acceptance_failures[0]
    : "";
  dom.modelChip.textContent = "diagnostics";
  dom.modelChip.className = "chip degraded";
  dom.modelGateDecision.textContent = "Operator alerts use validated rules";
  dom.modelGateSummary.textContent = latestFailure
    ? `${status.summary} Latest diagnostic: ${latestFailure}.`
    : status.summary;
  dom.modelGateStats.textContent = [
    `${adapterName}`,
    `signal ${signalRole}`,
    `runtime ${runtime}`,
    `alerts ${status.can_affect_alerts ? "model reviewed" : "rule checked"}`,
    evalScope,
    `base ${base.action_match}/${evalCases}`,
    `adapter ${adapter.action_match}/${evalCases}`,
    `schema ${adapter.schema_valid}/${evalCases}`,
    `downlink ${adapter.downlink_recall}/${adapter.downlink_total}`,
    `fp ${adapter.false_positives}`,
  ].join(" / ");
}

function seedTranscript() {
  if (state.transcriptSeeded) {
    return;
  }

  dom.chatLog.innerHTML = "";
  const lead = selectedLead();
  if (lead) {
    appendMessage(
      "assistant",
      `Live feed ready. Selected source lead: ${lead.title}. Ask what happened in a region, or ask to compare current and baseline evidence.`,
    );
    state.transcriptSeeded = true;
    return;
  }
  const alert = liveAlert();
  const opening = alert
    ? `Atlas ready. ${alert.asset_name} has confirmed reference evidence. Click a live marker or ask about a region.`
    : "Atlas ready. Click a live marker or ask what happened in a region.";
  appendMessage("assistant", opening);

  state.transcriptSeeded = true;
}

function selectAsset(assetId) {
  if (!assetId || state.selectedAssetId === assetId) {
    return;
  }
  state.selectedAssetId = assetId;
  state.selectedLeadId = null;
  const asset = state.assets.find((entry) => entry.asset_id === assetId);
  state.selectedAnalyst = null;
  if (asset) {
    setStageReport(
      `Reviewing ${asset.asset_name}`,
      "Loading current image, baseline image, evidence tags, and alert decision.",
    );
  }
  runMissionSequence(["focus", "evidence"], ["focus"]);
  if (isMobileSheetMode()) {
    setMobileSheet("site");
  }
  renderMap();
  renderDrawer();
  void loadSelectedSiteContext(assetId);
}

function selectLead(leadId) {
  if (!leadId || state.selectedLeadId === leadId) {
    return;
  }
  state.selectedLeadId = leadId;
  const lead = state.leads.find((entry) => entry.lead_id === leadId);
  const reviewAsset = reviewAssetForLead(lead);
  state.selectedAssetId = reviewAsset?.asset_id || null;
  state.selectedSiteContext = null;
  state.selectedEvidence = null;
  state.selectedAnalyst = null;
  state.selectedSiteLoading = false;
  if (lead) {
    setStageReport(
      lead.title,
      reviewAsset
        ? `${leadRegionLabel(lead)} / source lead / loading satellite review`
        : `${leadRegionLabel(lead)} / ${leadStatusLabel(lead)}`,
    );
  }
  runMissionSequence(reviewAsset ? ["focus", "evidence"] : ["focus", "summarize"], ["focus"]);
  if (isMobileSheetMode()) {
    setMobileSheet(null);
  }
  renderMap();
  renderDrawer();
  if (reviewAsset) {
    void loadSelectedSiteContext(reviewAsset.asset_id, lead?.lead_id || null);
  }
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

function setMapProjection(mode) {
  if (!state.map || typeof state.map.setProjection !== "function") {
    return;
  }

  try {
    state.map.setProjection({ type: mode === "globe" ? "globe" : "mercator" });
  } catch (error) {
    // Projection support varies by runtime and style.
  }
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

  state.cameraMode = "globe";
  setMapProjection("globe");
  const targetZoom = 2.35;
  const options = {
    center: [asset.longitude, asset.latitude],
    zoom: targetZoom,
    duration: immediate ? 0 : 900,
    essential: true,
  };

  state.map.easeTo(options);
}

function focusMapOnLead(lead, { immediate = false } = {}) {
  if (!state.map || !lead) {
    return;
  }

  state.cameraMode = "globe";
  setMapProjection("globe");
  state.map.easeTo({
    center: [lead.longitude, lead.latitude],
    zoom: 2.05,
    duration: immediate ? 0 : 900,
    essential: true,
  });
}

function angularDistanceDegrees(a, b) {
  const toRad = (value) => (value * Math.PI) / 180;
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const deltaLon = toRad(b.lng - a.lng);
  const cosine =
    Math.sin(lat1) * Math.sin(lat2) + Math.cos(lat1) * Math.cos(lat2) * Math.cos(deltaLon);
  return (Math.acos(Math.min(Math.max(cosine, -1), 1)) * 180) / Math.PI;
}

function fitMapToPoints(points) {
  if (!state.map || !points.length || !window.maplibregl) {
    return;
  }

  state.cameraMode = "globe";
  setMapProjection("globe");
  if (points.length > 120) {
    state.map.easeTo({
      center: [35, 25],
      zoom: 1.65,
      duration: 0,
      essential: true,
    });
    return;
  }
  const bounds = new window.maplibregl.LngLatBounds();
  points.forEach((point) => bounds.extend([point.longitude, point.latitude]));
  state.map.fitBounds(bounds, {
    padding: 120,
    maxZoom: points.length === 1 ? 4.2 : 2.8,
    duration: 0,
  });
}

function markerItems() {
  if (state.leads.length) {
    return state.leads.map((lead) => ({
      kind: "lead",
      id: lead.lead_id,
      label: lead.title,
      latitude: lead.latitude,
      longitude: lead.longitude,
      status: lead.status,
      linkedAssetId: lead.linked_asset_id || null,
      selected:
        state.selectedLeadId === lead.lead_id
        || (lead.linked_asset_id && state.selectedAssetId === lead.linked_asset_id),
      alert:
        !!lead.linked_asset_id
        && state.liveAlerts.some((item) => item.asset_id === lead.linked_asset_id),
      hero: false,
      summary: lead.summary,
    }));
  }

  return state.assets.map((asset) => ({
    kind: "asset",
    id: asset.asset_id,
    label: asset.asset_name,
    latitude: asset.latitude,
    longitude: asset.longitude,
    status: siteEvidenceState(asset),
    linkedAssetId: asset.asset_id,
    selected: state.selectedAssetId === asset.asset_id,
    alert: state.liveAlerts.some((item) => item.asset_id === asset.asset_id),
    hero: asset.hero,
    summary: null,
  }));
}

function isMarkerVisibleOnGlobe(item) {
  if (!state.map || !dom.mapCanvas) {
    return true;
  }

  const point = state.map.project([item.longitude, item.latitude]);
  const width = dom.mapCanvas.clientWidth || 1;
  const height = dom.mapCanvas.clientHeight || 1;
  const margin = 28;
  if (
    point.x < -margin
    || point.y < -margin
    || point.x > width + margin
    || point.y > height + margin
  ) {
    return false;
  }

  if (state.cameraMode !== "globe" || currentMapZoom() > 3.1) {
    return true;
  }

  const center = state.map.getCenter();
  const angularDistance = angularDistanceDegrees(
    { lng: center.lng, lat: center.lat },
    { lng: item.longitude, lat: item.latitude },
  );
  if (angularDistance > 92) {
    return false;
  }

  const radius = Math.min(width, height) * 0.43;
  const centerX = width / 2;
  const centerY = height / 2;
  const distance = Math.hypot(point.x - centerX, point.y - centerY);
  return distance <= radius;
}

function visibleMarkerItems() {
  const items = markerItems();
  if (!state.mapReady || !state.map) {
    return items;
  }
  return items.filter(isMarkerVisibleOnGlobe);
}

function leadZoneFeatureCollection() {
  const visibleLeads = state.leads.length
    ? state.leads
    : state.assets.map((asset) => ({
        lead_id: asset.asset_id,
        title: asset.asset_name,
        region: asset.region,
        latitude: asset.latitude,
        longitude: asset.longitude,
        status: siteEvidenceState(asset),
        linked_asset_id: asset.asset_id,
        summary: "",
      }));
  return {
    type: "FeatureCollection",
    features: visibleLeads.map((lead, index) => {
      const linkedAssetId = lead.linked_asset_id || null;
      const selected = Boolean(
        state.selectedLeadId === lead.lead_id
        || (linkedAssetId && state.selectedAssetId === linkedAssetId)
      );
      const alert = (
        !!linkedAssetId
        && state.liveAlerts.some((item) => item.asset_id === linkedAssetId)
      );
      return {
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: [lead.longitude, lead.latitude],
        },
        properties: {
          id: lead.lead_id,
          linkedAssetId,
          code: regionCodeForLead(lead),
          label: conciseLeadLabel(lead),
          flag: countryFlagForLead(lead),
          status: lead.status,
          selected,
          alert,
          labelVisible: selected || alert || index < 4,
        },
      };
    }),
  };
}

function syncLeadZoneLayer() {
  if (!state.map || !state.mapReady) {
    return;
  }

  const sourceId = "blackline-lead-zones";
  const data = leadZoneFeatureCollection();
  const existingSource = state.map.getSource(sourceId);
  if (existingSource && typeof existingSource.setData === "function") {
    existingSource.setData(data);
    bindLeadLayerEvents();
    return;
  }

  state.map.addSource(sourceId, {
    type: "geojson",
    data,
  });
  state.map.addLayer({
    id: "blackline-lead-zone-glow",
    type: "circle",
    source: sourceId,
    paint: {
      "circle-radius": [
        "interpolate",
        ["linear"],
        ["zoom"],
        1,
        ["case", ["get", "selected"], 24, ["get", "alert"], 18, 8],
        4,
        ["case", ["get", "selected"], 68, ["get", "alert"], 48, 22],
      ],
      "circle-color": [
        "case",
        ["get", "alert"],
        "#d46f55",
        ["==", ["get", "status"], "vlm_reviewed"],
        "#83d4cb",
        "#e0a84e",
      ],
      "circle-opacity": ["case", ["get", "selected"], 0.28, ["get", "alert"], 0.2, 0.08],
      "circle-blur": 0.55,
      "circle-stroke-color": [
        "case",
        ["get", "selected"],
        "#b7f2c1",
        "#d46f55",
      ],
      "circle-stroke-opacity": ["case", ["get", "selected"], 0.56, 0.16],
      "circle-stroke-width": ["case", ["get", "selected"], 1.4, 0.8],
    },
  });
  state.map.addLayer({
    id: "blackline-lead-points",
    type: "circle",
    source: sourceId,
    paint: {
      "circle-radius": [
        "interpolate",
        ["linear"],
        ["zoom"],
        1,
        ["case", ["get", "selected"], 6, 3.6],
        4,
        ["case", ["get", "selected"], 10, 6],
      ],
      "circle-color": [
        "case",
        ["get", "alert"],
        "#d46f55",
        ["==", ["get", "status"], "vlm_reviewed"],
        "#83d4cb",
        ["==", ["get", "status"], "reference_event"],
        "#d46f55",
        "#05090a",
      ],
      "circle-opacity": ["case", ["get", "selected"], 1, 0.94],
      "circle-stroke-color": [
        "case",
        ["get", "selected"],
        "#b7f2c1",
        ["get", "alert"],
        "#f0b35a",
        "#d8a15a",
      ],
      "circle-stroke-width": ["case", ["get", "selected"], 2.2, 1.5],
      "circle-stroke-opacity": 0.9,
    },
  });
  state.map.addLayer({
    id: "blackline-lead-hit",
    type: "circle",
    source: sourceId,
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 14, 4, 24],
      "circle-color": "#ffffff",
      "circle-opacity": 0.01,
    },
  });
  state.map.addLayer({
    id: "blackline-lead-zone-labels",
    type: "symbol",
    source: sourceId,
    minzoom: 1.65,
    filter: ["==", ["get", "labelVisible"], true],
    layout: {
      "text-field": ["concat", ["get", "code"], " / ", ["get", "label"]],
      "text-size": ["interpolate", ["linear"], ["zoom"], 1, 8, 4, 11],
      "text-offset": [0, 1.2],
      "text-anchor": "top",
      "text-allow-overlap": false,
      "text-ignore-placement": false,
    },
    paint: {
      "text-color": "#edf2ec",
      "text-halo-color": "#010303",
      "text-halo-width": 1.2,
      "text-opacity": ["case", ["get", "selected"], 1, 0.82],
    },
  });
  bindLeadLayerEvents();
}

function syncLiveMapMarkers() {
  if (!state.map || !state.mapReady || !window.maplibregl) {
    return;
  }

  syncLeadZoneLayer();
  clearLiveMapMarkers();
}

function bindLeadLayerEvents() {
  if (!state.map || state.mapLayerEventsBound) {
    return;
  }
  state.mapLayerEventsBound = true;

  const interactiveLayers = ["blackline-lead-hit"];
  interactiveLayers.forEach((layerId) => {
    state.map.on("mouseenter", layerId, () => {
      state.map.getCanvas().style.cursor = "pointer";
    });
    state.map.on("mouseleave", layerId, () => {
      state.map.getCanvas().style.cursor = "";
    });
    state.map.on("click", layerId, (event) => {
      const feature = event.features?.[0];
      const markerId = feature?.properties?.id;
      if (!markerId) {
        return;
      }
      const lead = state.leads.find((item) => item.lead_id === markerId);
      if (lead) {
        selectLead(lead.lead_id);
        focusMapOnLead(lead);
        appendMessage(
          "assistant",
          `${leadRegionLabel(lead)}: ${lead.title}. ${formatLeadSummary(lead, 180)} ${lead.linked_asset_id ? "Linked satellite evidence is loading." : "Satellite evidence is not linked yet."}`.trim(),
        );
        return;
      }
      const asset = state.assets.find((item) => item.asset_id === markerId);
      if (asset) {
        selectAsset(asset.asset_id);
        focusMapOnAsset(asset);
        appendMessage("assistant", `Map focused on ${asset.asset_name}.`);
      }
    });
  });
}

function ensureLiveMap() {
  if (state.map || !dom.mapCanvas || !window.maplibregl) {
    return;
  }

  state.map = new window.maplibregl.Map({
    container: dom.mapCanvas,
    style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
    center: [0, 15],
    zoom: 1.4,
    renderWorldCopies: false,
    attributionControl: true,
  });

  state.map.addControl(new window.maplibregl.NavigationControl({ visualizePitch: true }), "top-right");

  state.map.on("load", () => {
    state.mapReady = true;
    dom.mapStage.classList.add("is-live-map");
    const lead = selectedLead();
    if (lead) {
      focusMapOnLead(lead, { immediate: true });
    } else {
      fitMapToPoints(markerItems());
    }
    syncLiveMapMarkers();
    renderLeadPopover();
  });
  state.map.on("move", () => {
    syncLiveMapMarkers();
    renderLeadPopover();
  });
}

function focusLatestAlert() {
  const alert = liveAlert();
  if (!alert) {
    const lead = selectedLead() || state.leads[0];
    if (lead) {
      selectLead(lead.lead_id);
      focusMapOnLead(lead);
      appendMessage(
        "assistant",
        `No confirmed satellite alert is selected. Focused live source lead instead: ${lead.title}.`,
      );
      return;
    }
    appendMessage(
      "assistant",
      "No confirmed satellite alert or live source lead is loaded. Refresh live leads first.",
    );
    return;
  }

  selectAsset(alert.asset_id);
  appendMessage(
    "assistant",
    `Focused ${alert.asset_name}. ${humanizeSlug(alert.event_type)} with ${Math.round(alert.confidence * 100)}% confidence.`,
  );
}

function explainCurrentDecision() {
  const lead = selectedLead();
  const reviewAsset = reviewAssetForLead(lead);
  if (lead && reviewAsset) {
    state.selectedAssetId = reviewAsset.asset_id;
    focusMapOnAsset(reviewAsset);
    appendMessage("assistant", `Opening satellite review for ${reviewAsset.asset_name}.`);
    void loadSelectedSiteContext(reviewAsset.asset_id, lead.lead_id, { announce: true });
    return;
  }

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
    "No active alert on the selected site. I can explain decisions, compare current versus baseline imagery, and focus monitored regions.",
  );
}

function compareSelectedSite() {
  const lead = selectedLead();
  const reviewAsset = reviewAssetForLead(lead);
  if (lead && reviewAsset) {
    state.selectedAssetId = reviewAsset.asset_id;
    focusMapOnAsset(reviewAsset);
    appendMessage(
      "assistant",
      `Loading satellite review for ${reviewAsset.asset_name}.`,
    );
    void loadSelectedSiteContext(reviewAsset.asset_id, lead.lead_id, { announce: true });
    return;
  }
  if (lead && !reviewAsset) {
    appendMessage(
      "assistant",
      `${lead.title} is selected, but Atlas could not create a satellite review target for that point.`,
    );
    return;
  }

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
    `Evidence feed is ${state.replay.running ? "active" : "standing by"}. Selected site ${compactLabel(state.replay.asset_id)}. Active scenario ${compactLabel(state.replay.scenario_id)}.`,
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
    `Watchlist: ${state.assets.length} civilian sites. Globe markers: ${state.leads.length}. ${counts.reference_event || 0} confirmed reference disruptions, ${counts.reference_control || 0} controls.`,
  );
}

function leadRegistrySummary() {
  if (!state.leads.length) {
    appendMessage("assistant", "No live lead registry is loaded yet. Refresh live leads to fetch current geolocated source reports.");
    return;
  }

  const counts = state.leads.reduce(
    (memo, lead) => {
      memo[lead.status] = (memo[lead.status] || 0) + 1;
      return memo;
    },
    {},
  );
  const linked = state.leads.filter((lead) => lead.linked_asset_id).length;
  const selected = selectedLead();
  if (selected) {
    appendMessage(
      "assistant",
      `${selected.title}: ${formatLeadSummary(selected, 220)} Status ${humanizeSlug(selected.status)}. ${selected.linked_asset_id ? "Evidence inspect is available." : "Lead-only point; compare not loaded yet."}`,
    );
    return;
  }

  appendMessage(
    "assistant",
    `Lead registry: ${state.leads.length} current/reference markers, ${linked} linked to evidence sites. Reference events ${counts.reference_event || 0}, lead-only ${counts.lead_only || 0}, controls ${counts.reference_control || 0}.`,
  );
}

function pointMatchesCamera(item, camera) {
  if (!camera) {
    return false;
  }
  if (item.kind === "lead") {
    return camera.highlight_lead_ids.includes(item.id)
      || (item.linkedAssetId && camera.highlight_asset_ids.includes(item.linkedAssetId));
  }
  return camera.highlight_asset_ids.includes(item.id);
}

function applyCameraIntent(camera) {
  if (!camera || !state.map) {
    return;
  }

  const key = JSON.stringify(camera);
  if (state.lastCameraIntentKey === key) {
    return;
  }
  state.lastCameraIntentKey = key;

  if (camera.mode === "focus_asset" && camera.asset_id) {
    const asset = state.assets.find((entry) => entry.asset_id === camera.asset_id);
    if (asset) {
      focusMapOnAsset(asset);
    }
    return;
  }
  if (camera.mode === "focus_lead" && camera.lead_id) {
    const lead = state.leads.find((entry) => entry.lead_id === camera.lead_id);
    if (lead) {
      state.selectedLeadId = lead.lead_id;
      const reviewAsset = reviewAssetForLead(lead);
      state.selectedAssetId = reviewAsset?.asset_id || null;
      focusMapOnLead(lead);
    }
    return;
  }

  const highlighted = markerItems().filter((item) => pointMatchesCamera(item, camera));
  fitMapToPoints(highlighted.length ? highlighted : markerItems());
}

function applyAgentResponse(response) {
  if (
    response.tool === "refresh_live_leads"
    && response.status === "ok"
    && Array.isArray(response.leads)
  ) {
    state.leads = response.leads;
  } else if (Array.isArray(response.leads) && response.leads.length) {
    mergeLeads(response.leads);
  }

  if (
    (
      response.tool === "latest_alerts"
      || response.tool === "biggest_disruptions"
      || response.tool === "site_compare"
      || response.tool === "explain_alert"
    )
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

  if (response.focus_lead_id) {
    state.selectedLeadId = response.focus_lead_id;
    const lead = state.leads.find((entry) => entry.lead_id === response.focus_lead_id);
    const reviewAsset = reviewAssetForLead(lead);
    if (!response.focus_asset_id) {
      state.selectedAssetId = reviewAsset?.asset_id || null;
    }
  } else if (response.focus_asset_id) {
    state.selectedLeadId = null;
  }

  if (response.camera) {
    applyCameraIntent(response.camera);
  }

  renderTopbar();
  renderMap();
  renderDrawer();
}

async function queryAgent(rawText) {
  const userLocation = await resolveUserLocationForQuery(rawText);
  const payload = {
    query: rawText,
    selected_asset_id: state.selectedAssetId,
    selected_lead_id: state.selectedLeadId,
  };
  if (userLocation) {
    payload.user_latitude = userLocation.latitude;
    payload.user_longitude = userLocation.longitude;
  }

  const response = await fetch(urls.agentQuery, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`/agent/query returned ${response.status}`);
  }

  return response.json();
}

async function resolveUserLocationForQuery(rawText) {
  if (state.userLocation) {
    return state.userLocation;
  }
  if (!window.navigator?.geolocation || !queryNeedsUserLocation(rawText)) {
    return null;
  }

  try {
    state.userLocation = await new Promise((resolve, reject) => {
      window.navigator.geolocation.getCurrentPosition(
        (position) => {
          resolve({
            latitude: Number(position.coords.latitude.toFixed(6)),
            longitude: Number(position.coords.longitude.toFixed(6)),
          });
        },
        reject,
        {
          enableHighAccuracy: false,
          maximumAge: 10 * 60 * 1000,
          timeout: 2500,
        },
      );
    });
    return state.userLocation;
  } catch (error) {
    return null;
  }
}

function queryNeedsUserLocation(rawText) {
  return /\b(near me|nearest|closest|my location|my position)\b/i.test(rawText);
}

async function querySiteCompare(assetId, leadId = null) {
  const response = await fetch(urls.agentQuery, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      tool: "site_compare",
      site_id: assetId,
      selected_lead_id: leadId,
    }),
  });

  if (!response.ok) {
    throw new Error(`/agent/query returned ${response.status}`);
  }

  return response.json();
}

async function queryAssetEvidence(assetId) {
  const response = await fetch(new URL(`/evidence/assets/${assetId}`, window.location.origin));
  if (!response.ok) {
    throw new Error(`/evidence/assets/${assetId} returned ${response.status}`);
  }
  return response.json();
}

async function queryAssetAnalyst(assetId) {
  const response = await fetch(new URL(`/analyst/assets/${assetId}`, window.location.origin));
  if (!response.ok) {
    throw new Error(`/analyst/assets/${assetId} returned ${response.status}`);
  }
  return response.json();
}

async function loadSelectedVisualAnalysis(assetId, options = {}) {
  const announce = Boolean(options.announce);
  const compare = selectedCompare();
  if (!assetId || compare?.asset_id !== assetId || !compareUsableForVisualAnalysis(compare)) {
    return;
  }

  setStageReport("Sentinel pair loaded", "Liquid VLM site brief running.");
  renderDrawer();

  try {
    const report = await queryAssetAnalyst(assetId);
    if (state.selectedAssetId === assetId && report?.asset_id === assetId && report.status === "ready") {
      state.selectedAnalyst = report;
      setStageReport("Visual analysis complete", report.visible_change_summary);
      if (announce) {
        appendMessage("assistant", `Visual analysis complete: ${report.visible_change_summary}`);
      }
      renderDrawer();
    } else if (state.selectedAssetId === assetId) {
      setChannelNote("Liquid VLM visual brief withheld because model-readable images or a valid model report are unavailable.");
      renderDrawer();
    }
  } catch (error) {
    if (state.selectedAssetId === assetId) {
      setChannelNote("Liquid VLM site brief endpoint unavailable for this site.");
    }
  }
}

async function loadSelectedSiteContext(assetId, leadId = state.selectedLeadId, options = {}) {
  if (!assetId) {
    return;
  }

  const announce = Boolean(options.announce);
  state.selectedSiteLoading = true;
  renderMap();
  renderDrawer();

  try {
    const response = await querySiteCompare(assetId, leadId);
    if (state.selectedAssetId === assetId) {
      applyAgentResponse(response);
      state.selectedEvidence = null;
      state.selectedAnalyst = null;
      runMissionSequence(["evidence", "summarize"], ["focus", "evidence", "summarize"]);
      if (announce) {
        appendMessage("assistant", response.summary);
      }
      if (response.compare?.asset_id === assetId && compareUsableForVisualAnalysis(response.compare)) {
        setChannelNote("Sentinel pair loaded. Liquid VLM is running in the background.");
        void loadSelectedVisualAnalysis(assetId, { announce });
      } else if (response.status === "no_result") {
        setChannelNote("Source lead only. No dated Sentinel pair resolved for visual analysis.");
      }
    }
  } catch (error) {
    if (state.selectedAssetId === assetId) {
      state.selectedSiteContext = null;
      state.selectedEvidence = null;
      state.selectedAnalyst = null;
      setMissionStep(null, ["focus"]);
    }
  } finally {
    if (state.selectedAssetId === assetId) {
      state.selectedSiteLoading = false;
      renderMap();
      renderDrawer();
    }
  }
}

async function handleCommand(rawText) {
  const text = rawText.trim();
  if (!text) {
    return;
  }

  appendMessage("user", text);
  const thinkingMessage = appendMessage(
    "assistant",
    "Thinking. Routing the request, checking live source leads, resolving satellite context, and preparing a visual site brief.",
    { thinking: true },
  );
  runMissionSequence(["parse", "fetch"], ["parse"]);
  setStageReport(
    "Atlas parsing request",
    "Routing command into live-source search, camera focus, Sentinel evidence, and Liquid VLM briefing.",
  );
  setChannelNote("Parsing request. Satellite and model analysis can take a moment on first run.");

  try {
    const response = await queryAgent(text);
    const channelNote = applyPlannerTelemetry(response.planner);
    applyAgentResponse(response);
    runMissionSequence(missionStepsForResponse(response));
    removeMessage(thinkingMessage);
    appendMessage("assistant", response.summary);
    setChannelNote(channelNote);
    renderPlannerChip();
  } catch (error) {
    removeMessage(thinkingMessage);
    state.plannerFallbackActive = false;
    renderPlannerChip();
    runMissionSequence(["parse", "summarize"], ["parse", "summarize"]);
    appendMessage(
      "assistant",
      "Atlas planner is unreachable. Live markers remain available; retry in a moment.",
    );
    setChannelNote("Planner unreachable. Live map remains available.");
  }
}

function renderTopbar() {
  const summary = topStatus();
  dom.healthChip.textContent = summary.healthText;
  dom.healthChip.className = summary.healthClass;
  dom.modeChip.textContent = summary.modeText;
  dom.modeChip.className = summary.modeClass;
  dom.alertChip.textContent = topLeadMetricText();
  dom.alertChip.className = liveLeadCount() ? "chip degraded" : "chip neutral";
  renderLeadRefreshButton();
  renderModelGate();
  renderPlannerChip();
  renderStageReport();
}

function renderStageReport() {
  const lead = selectedLead();
  const asset = selectedAsset();
  const alert = liveAlertForAsset(asset?.asset_id);
  if (lead) {
    setStageReport(
      lead.title,
      `${leadRegionLabel(lead)} / ${humanizeSlug(lead.status)} / ${
        lead.linked_asset_id ? "evidence link available" : "source marker"
      }`,
    );
    return;
  }
  if (asset) {
    setStageReport(
      asset.asset_name,
      `${compactLabel(asset.region)} / ${humanizeSlug(asset.asset_type)} / ${
        alert ? humanizeSlug(alert.action) : evidenceLabel(siteEvidenceState(asset))
      }`,
    );
    return;
  }
  setStageReport(
    "Global conflict theater",
    state.leads.length
      ? `${state.leads.length} live/reference markers loaded. Ask Atlas to focus a region.`
      : "Live geolocated reports initializing. Ask Atlas to focus a region.",
  );
}

function renderLeadPopover() {
  if (!dom.leadPopover) {
    return;
  }

  const lead = selectedLead();
  if (!lead) {
    dom.leadPopover.hidden = true;
    return;
  }

  const reviewAsset = reviewAssetForLead(lead);
  dom.leadPopover.hidden = false;
  dom.leadPopoverKicker.textContent = reviewAsset ? "satellite review lead" : "source-only report";
  dom.leadPopoverTitle.textContent = lead.title;
  dom.leadPopoverRegion.textContent = leadRegionLabel(lead);
  dom.leadPopoverDate.textContent = formatDateLabel(lead.source_date);
  dom.leadPopoverSummary.textContent = formatLeadSummary(lead, 150);
  dom.leadPopoverStatus.textContent = leadStatusLabel(lead);

  if (lead.source_url) {
    dom.leadPopoverLink.hidden = false;
    dom.leadPopoverLink.href = lead.source_url;
    dom.leadPopoverLink.textContent = "Source article";
  } else {
    dom.leadPopoverLink.hidden = true;
    dom.leadPopoverLink.removeAttribute("href");
  }

  dom.leadPopoverInspect.hidden = false;
  dom.leadPopoverInspect.disabled = !reviewAsset;
  dom.leadPopoverInspect.textContent = reviewAsset ? "Inspect site" : "Source report only";

  let left = "50%";
  let top = "50%";
  let popoverBelow = false;
  if (state.mapReady && state.map) {
    const point = state.map.project([lead.longitude, lead.latitude]);
    const width = dom.mapCanvas.clientWidth || 1;
    const height = dom.mapCanvas.clientHeight || 1;
    const rightPanelSafe = Math.max(width - 440, 220);
    const ribbonSafeTop = Math.min(380, Math.max(300, height * 0.28));
    left = `${Math.min(Math.max(point.x, 180), rightPanelSafe)}px`;
    top = `${Math.min(Math.max(point.y + 44, ribbonSafeTop), height - 150)}px`;
    popoverBelow = true;
  } else {
    const bounds = computeBounds(markerItems());
    const position = project(lead, bounds);
    left = position.left;
    top = position.top;
  }

  dom.leadPopover.classList.toggle("below", popoverBelow);
  dom.leadPopover.style.left = left;
  dom.leadPopover.style.top = top;
}

function renderLiquidAnalystCard(report, selected, compare) {
  if (
    !dom.liquidAnalystCard
    || !dom.liquidAnalystTitle
    || !dom.liquidAnalystSummary
    || !dom.liquidAnalystModel
    || !dom.liquidAnalystAction
    || !dom.liquidAnalystConfidence
  ) {
    return;
  }

  if (!selected || !compare || compare.asset_id !== selected.asset_id) {
    dom.liquidAnalystCard.hidden = true;
    return;
  }

  dom.liquidAnalystCard.hidden = false;
  if (isModelGatedCompare(compare)) {
    dom.liquidAnalystTitle.textContent = "Context-only imagery";
    dom.liquidAnalystSummary.textContent = compare.satellite_evidence?.quality_summary
      || "Atlas loaded context imagery for orientation, but this is not a dated before/after pair.";
    dom.liquidAnalystModel.textContent = "context imagery";
    dom.liquidAnalystAction.textContent = "source-led only";
    dom.liquidAnalystConfidence.textContent = "no before/after confidence";
    return;
  }

  if (report && report.status !== "ready") {
    dom.liquidAnalystTitle.textContent = "Liquid VLM unavailable";
    dom.liquidAnalystSummary.textContent = report.visible_change_summary;
    dom.liquidAnalystModel.textContent = report.model_version;
    dom.liquidAnalystAction.textContent = "not model-scored";
    dom.liquidAnalystConfidence.textContent = "endpoint unavailable";
    return;
  }

  if (!report) {
    dom.liquidAnalystTitle.textContent = analystEndpointReady()
      ? "Visual site brief queued"
      : "Liquid VLM not attached";
    dom.liquidAnalystSummary.textContent = analystEndpointReady()
      ? "Current and baseline frames are loaded. Waiting for the Liquid VLM visual description."
      : "Current and baseline frames are loaded, but the real paired-image Liquid VLM endpoint is not configured. Atlas shows the imagery and rule gates without pretending a model reviewed it.";
    dom.liquidAnalystModel.textContent = "LiquidAI/LFM2.5-VL";
    dom.liquidAnalystAction.textContent = analystEndpointReady()
      ? "brief pending"
      : "not model-scored";
    dom.liquidAnalystConfidence.textContent = analystEndpointReady()
      ? "confidence pending"
      : "endpoint offline";
    return;
  }

  dom.liquidAnalystTitle.textContent = analystBackendLabel(report);
  dom.liquidAnalystSummary.textContent = report.visible_change_summary;
  dom.liquidAnalystModel.textContent = report.model_version;
  dom.liquidAnalystAction.textContent = `triage ${actionLabel(report.recommended_action)}`;
  dom.liquidAnalystConfidence.textContent = `${Math.round(report.confidence * 100)}% confidence`;
}

function renderMap() {
  const points = markerItems();
  const bounds = computeBounds(points);

  ensureLiveMap();

  if (!points.length) {
    dom.mapMarkers.innerHTML = "";
    return;
  }

  if (state.mapReady) {
    dom.mapMarkers.innerHTML = "";
    syncLiveMapMarkers();
  } else if (state.map) {
    dom.mapMarkers.innerHTML = "";
  } else {
    dom.mapMarkers.innerHTML = points
      .map((item) => {
        const position = project(item, bounds);
        const classes = [
          "marker",
          item.selected ? "selected" : "",
          item.alert ? "alert" : "",
          !item.alert ? item.status : "",
          item.hero ? "hero" : "",
        ]
          .filter(Boolean)
          .join(" ");
        return `
          <button
            class="${classes || "marker quiet"}"
            type="button"
            data-marker-id="${item.id}"
            data-marker-kind="${item.kind}"
            style="left:${position.left};top:${position.top};"
            aria-label="Focus ${item.label}"
          >
            <span class="marker-core"></span>
            <span class="marker-label">${item.label}</span>
          </button>
        `;
      })
      .join("");

    dom.mapMarkers.querySelectorAll(".marker").forEach((button) => {
      button.addEventListener("click", () => {
        const markerId = button.dataset.markerId;
        const markerKind = button.dataset.markerKind;
        if (!markerId || !markerKind) {
          return;
        }
        if (markerKind === "lead") {
          const lead = state.leads.find((item) => item.lead_id === markerId);
          if (!lead) {
            return;
          }
          selectLead(lead.lead_id);
          appendMessage(
            "assistant",
            `${leadRegionLabel(lead)}: ${lead.title}. ${formatLeadSummary(lead, 180)} ${lead.linked_asset_id ? "Linked satellite evidence is loading." : "Satellite evidence is not linked yet."}`.trim(),
          );
          return;
        }
        selectAsset(markerId);
        const asset = state.assets.find((item) => item.asset_id === markerId);
        if (asset) {
          focusMapOnAsset(asset);
          appendMessage("assistant", `Map focused on ${asset.asset_name}.`);
        }
      });
    });
  }

  renderLeadPopover();
}

function renderDrawer() {
  const lead = selectedLead();
  const selected = selectedAsset();
  const context = selectedSiteContext();
  const compare = selectedCompare();
  const sam3Evidence = selectedEvidenceReport();
  const analystReport = selectedAnalystReport();
  const alert = selectedSiteAlerts()[0] || null;
  const evidenceState = siteEvidenceState(selected);
  const metrics = state.metrics;
  dom.drawerPanel?.classList.toggle("is-loading", state.selectedSiteLoading);

  if (lead && !selected) {
    const reviewAsset = reviewAssetForLead(lead);
    dom.drawerPanel?.classList.add("lead-only");
    renderLiquidAnalystCard(null, null, null);
    clearEvidenceFrames();
    dom.siteName.textContent = lead.title;
    dom.siteImpact.textContent = reviewAsset ? "review ready" : "source-only";
    dom.siteImpact.className = reviewAsset ? "status-pill medium" : "status-pill idle";
    dom.siteSummary.textContent = formatLeadSummary(lead, 260);
    dom.siteRegion.textContent = leadRegionLabel(lead);
    dom.siteType.textContent = "live conflict/disruption source";
    dom.siteCoords.textContent = `${lead.latitude.toFixed(2)}, ${lead.longitude.toFixed(2)}`;
    dom.currentTitle.textContent = reviewAsset ? "Satellite review ready" : "Source-only event";
    dom.currentNote.textContent = reviewAsset
      ? "Atlas can load satellite context for this geolocated source point. Inspect starts current and baseline review."
      : "This report does not describe a visible macro-scale damage target, so Atlas keeps it as source intelligence and disables satellite inspection.";
    dom.currentStatus.textContent = leadStatusLabel(lead);
    dom.currentCaptured.textContent = formatDateLabel(lead.source_date);
    dom.baselineTitle.textContent = reviewAsset ? "Baseline/context after inspect" : "No satellite inspection";
    dom.baselineNote.textContent = reviewAsset
      ? "The drawer will show dated SimSat/Sentinel evidence when available, otherwise satellite context."
      : "Use the article/source context. Before/after review is reserved for visible infrastructure disruption.";
    dom.baselineCaptured.textContent = "source marker";
    dom.baselineSource.textContent = compactLabel(lead.source_url, "source unavailable");
    dom.signalAction.textContent = actionLabel("unconfirmed");
    dom.signalSeverity.textContent = "source lead";
    dom.signalConfidence.textContent = "needs evidence";
    dom.metricsAlerts.textContent = leadMetricText();
    dom.metricsSuppressed.textContent = inspectableMetricText();
    dom.metricsDownlink.textContent = reviewAsset ? "inspect available" : "lead only";
    return;
  }

  dom.drawerPanel?.classList.remove("lead-only");

  if (!selected) {
    renderLiquidAnalystCard(null, null, null);
    clearEvidenceFrames();
    dom.siteName.textContent = "Live disruption map";
    dom.siteImpact.textContent = "idle";
    dom.siteImpact.className = "status-pill idle";
    dom.siteSummary.textContent =
      "Click a live source marker to read what happened. Linked markers can be inspected with current and baseline imagery.";
    dom.siteRegion.textContent = "-";
    dom.siteType.textContent = "lead registry";
    dom.siteCoords.textContent = "-";
    dom.signalAction.textContent = actionLabel("watch");
    dom.signalSeverity.textContent = "-";
    dom.signalConfidence.textContent = "-";
    dom.metricsAlerts.textContent = leadMetricText();
    dom.metricsSuppressed.textContent = inspectableMetricText();
    dom.metricsDownlink.textContent = "select a marker";
    return;
  }

  dom.siteName.textContent = selected.asset_name;
  renderLiquidAnalystCard(analystReport, selected, compare);
  dom.siteImpact.textContent = alert
    ? alert.severity
    : evidenceState === "reference_control"
      ? "control"
      : evidenceState === "reference_event"
        ? "confirmed"
        : evidenceState === "live_demo"
          ? "reference"
          : "monitored";
  dom.siteImpact.className = siteImpactClass(
    alert
      ? alert.severity
      : evidenceState === "reference_event"
        ? "medium"
        : evidenceState === "live_demo"
          ? "medium"
          : "low",
  );
  dom.siteSummary.textContent = state.selectedSiteLoading
    ? satelliteSweepText()
    : alert
      ? analystReport?.visible_change_summary || alert.why
      : analystReport?.visible_change_summary || context?.summary || "Reference compare ready.";
  dom.siteRegion.textContent = compactLabel(selected.region);
  dom.siteType.textContent = `${humanizeSlug(selected.asset_type)} / ${evidenceLabel(evidenceState)}`;
  dom.siteCoords.textContent = `${selected.latitude.toFixed(2)}, ${selected.longitude.toFixed(2)}`;

  if (compare?.asset_id === selected.asset_id) {
    if (isContextOnlyFrameCompare(compare)) {
      clearEvidenceFrames();
      const qualitySummary = compare.satellite_evidence?.quality_summary
        || "No dated Sentinel current/baseline pair resolved for this source point.";
      dom.currentTitle.textContent = "Source report only";
      dom.currentNote.textContent =
        `${qualitySummary} Visual analysis was not run because the available imagery is context-only.`;
      dom.currentStatus.textContent = "no visual analysis";
      dom.currentCaptured.textContent = "no dated pair";
      dom.baselineTitle.textContent = "No baseline evidence";
      dom.baselineNote.textContent =
        "Map imagery can orient the operator, but it is not evidence and is not shown in the analysis lane.";
      dom.baselineCaptured.textContent = "unavailable";
      dom.baselineSource.textContent = "Sentinel pair required";
    } else {
    const sam3Note = sam3EvidenceNote(sam3Evidence);
    const analystNote =
      analystReport && analystReport.status === "ready"
        ? ` Liquid analyst: ${humanizeSlug(analystReport.severity_hint)} / ${actionLabel(analystReport.recommended_action)}.`
        : "";
    const simsatNote = simsatFallbackNote(compare);
    const satelliteNote = satelliteEvidenceNote(compare.satellite_evidence);
    const satelliteUsabilityState = satelliteUsability(compare.satellite_evidence);
    dom.currentTitle.textContent = formatTimestamp(compare.current_frame.frame.captured_at);
    dom.currentNote.textContent =
      (satelliteUsabilityState === "cloud_limited"
        ? "Current optical image loaded, but visibility is limited. Use it as context, not confirmation."
        : compare.current_frame.filter_reason === "simsat_live_frame"
        ? "Live Sentinel image loaded. Visual scoring pending."
        : compare.current_frame.filter_reason === "simsat_historical_current_frame"
          ? "Timestamped Sentinel image loaded for this conflict point."
        : compare.current_frame.filter_reason === "satellite_context_only"
          ? "Satellite context image loaded for the selected coordinate. Not direct before/after evidence."
        : evidenceState === "reference_event"
        ? "Visible civilian disruption evidence."
        : evidenceState === "reference_control"
          ? "No clear visible disruption."
        : compare.current_frame.accepted_for_alerting === true
            ? "Visible change cleared evidence rules."
            : "No defensible visible change yet.") + sam3Note + analystNote + simsatNote + satelliteNote;
    setEvidenceFrame(
      dom.currentFrame,
      dom.currentImage,
      dom.currentImageCaption,
      compare.current_frame.frame.image_ref,
      `${selected.asset_name} / current view`,
    );
    dom.currentStatus.textContent = humanizeSlug(selectedStatusLabel(selected));
    dom.currentCaptured.textContent = "";
    dom.baselineTitle.textContent =
      compare.baseline_frame.filter_reason === "satellite_context_only"
        ? "Context image"
        : formatTimestamp(compare.baseline_frame.frame.captured_at);
    dom.baselineNote.textContent =
      satelliteUsabilityState === "cloud_limited"
        ? `Baseline image loaded, but cloud cover or low detail limits comparison.${satelliteNote}`
        : compare.baseline_frame.filter_reason === "satellite_context_only"
        ? `Static satellite context loaded because dated baseline did not resolve.${satelliteNote}`
        : `Last clear baseline.${satelliteNote}`;
    setEvidenceFrame(
      dom.baselineFrame,
      dom.baselineImage,
      dom.baselineImageCaption,
      compare.baseline_frame.frame.image_ref,
      `${selected.asset_name} / baseline view`,
    );
    dom.baselineCaptured.textContent = compare.satellite_evidence
      ? satelliteUsabilityLabel(compare.satellite_evidence)
      : evidenceState === "live_demo" ? "live reference source" : "archive source";
    dom.baselineSource.textContent = "";
    }
  } else {
    clearEvidenceFrames();
    const noResult = context?.status === "no_result";
    dom.currentTitle.textContent = noResult ? "Satellite evidence unavailable" : "Waiting for site";
    dom.currentNote.textContent = state.selectedSiteLoading
      ? satelliteSweepText()
      : noResult
        ? context.summary
        : "Select a marker to load evidence.";
    dom.currentStatus.textContent = noResult ? "not resolved" : "watch";
    dom.currentCaptured.textContent = state.selectedSiteLoading
      ? "searching exact + nearby grid"
      : noResult ? "live timeout" : "n/a";
    dom.baselineTitle.textContent = state.selectedSiteLoading
      ? "Searching baseline"
      : noResult ? "No baseline resolved" : "Waiting for site";
    dom.baselineNote.textContent = noResult
      ? "Atlas could not resolve a defensible before/after pair for this point within the live window."
      : state.selectedSiteLoading
        ? "Trying dated baseline, nearby AOIs, and context fallback. This can take longer for sparse coordinates."
        : "Baseline appears after a site is selected.";
    dom.baselineCaptured.textContent = state.selectedSiteLoading
      ? "5-9 km grid"
      : noResult ? "unavailable" : "n/a";
    dom.baselineSource.textContent = noResult ? "try another marker or refresh leads" : "n/a";
  }

  dom.signalAction.textContent = alert
    ? actionLabel(alert.action)
    : compare?.asset_id === selected.asset_id
      ? isModelGatedCompare(compare)
        ? "source-led only"
        : compare.current_frame.accepted_for_alerting === false
        ? actionLabel("discard")
        : compare.current_frame.accepted_for_alerting === true
          ? actionLabel("downlink_now")
          : actionLabel("watch")
      : actionLabel("watch");
  dom.signalSeverity.textContent = alert
    ? humanizeSlug(alert.severity)
    : compare?.asset_id === selected.asset_id && isModelGatedCompare(compare)
      ? satelliteUsabilityLabel(compare.satellite_evidence)
      : evidenceState === "reference_control"
      ? "control"
      : evidenceState === "reference_event"
        ? "confirmed"
        : "pending";
  dom.signalConfidence.textContent = alert
    ? `${Math.round(alert.confidence * 100)}% confidence`
    : compare?.asset_id === selected.asset_id
      ? isModelGatedCompare(compare)
        ? satelliteUsability(compare.satellite_evidence) === "cloud_limited"
          ? "cloud-limited"
          : "no dated pair"
        : compactLabel(humanizeSlug(compare.current_frame.filter_reason), "no confidence")
      : "no evidence";

  dom.metricsAlerts.textContent = leadMetricText();
  dom.metricsSuppressed.textContent = inspectableMetricText();
  dom.metricsDownlink.textContent = evidenceMetricText(compare, selected);
}

function renderHealthFallback() {
  dom.healthChip.textContent = "degraded";
  dom.healthChip.className = "chip degraded";
  dom.modeChip.textContent = "live feed degraded";
  dom.modeChip.className = "chip neutral";
  renderModelGate();
  renderPlannerChip();
  setChannelNote("Atlas health check degraded. Command status unknown.");
}

async function loadJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${url.pathname} returned ${response.status}`);
  }
  return response.json();
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`${url.pathname} returned ${response.status}`);
  }
  return response.json();
}

async function refreshLiveLeads({ announce = true } = {}) {
  if (state.leadRefreshLoading) {
    return;
  }

  state.leadRefreshLoading = true;
  renderLeadRefreshButton();
  runMissionSequence(["fetch"], ["parse"]);
  setStageReport(
    "Refreshing live leads",
    "Fetching current geolocated conflict events from GDELT Cloud or fallback feeds.",
  );
  setChannelNote("Refreshing live lead registry. Existing markers stay visible if no live events are returned.");

  try {
    const payload = await postJson(urls.leadRefresh, {
      source_mode: "auto",
      hours: 72,
      max_files: 288,
      limit: 500,
      min_articles: 1,
      country_allowlist: "default",
      acled_days: 14,
      acled_countries: "default",
      gdelt_cloud_days: 30,
      gdelt_cloud_countries: "all",
      gdelt_cloud_confidence_profile: "loose",
    });

    if (payload.leads?.length) {
      state.leads = payload.leads;
      if (state.selectedLeadId && !state.leads.some((lead) => lead.lead_id === state.selectedLeadId)) {
        state.selectedLeadId = null;
      }
    }

    const [assetsResult, metricsResult] = await Promise.allSettled([
      loadJson(urls.assets),
      loadJson(urls.metrics),
    ]);
    if (assetsResult.status === "fulfilled") {
      state.assets = assetsResult.value;
    }
    if (metricsResult.status === "fulfilled") {
      state.metrics = metricsResult.value;
    }

    renderTopbar();
    renderMap();
    renderDrawer();
    fitMapToPoints(markerItems());
    runMissionSequence(["fetch", "focus", "summarize"], ["fetch", "focus", "summarize"]);
    const sourceText = payload.reachable_source_count
      ? `${payload.source_mode.toUpperCase()} source reached`
      : `no reachable ${payload.source_mode.toUpperCase()} source`;
    const resultText = payload.lead_count
      ? `${payload.lead_count} current markers loaded`
      : "no new live markers returned; existing markers preserved";
    setChannelNote(`${resultText} from ${sourceText}.`);
    if (announce) {
      appendMessage("assistant", `Live lead refresh complete: ${resultText}.`);
    }
    void autoSelectLeadForAnalysis({ announce: false, force: true });
  } catch (error) {
    runMissionSequence(["fetch", "summarize"], ["summarize"]);
    setChannelNote("Live lead refresh failed. Existing markers remain available.");
    if (announce) {
      appendMessage("assistant", "Live lead refresh failed. Existing markers remain available.");
    }
  } finally {
    state.leadRefreshLoading = false;
    renderLeadRefreshButton();
  }
}

function pickInitialSelection() {
  if (state.selectedLeadId || state.selectedAssetId) {
    return;
  }

  const initialLinkedLead = state.leads.find((lead) => lead.linked_asset_id);
  if (initialLinkedLead || state.leads[0]) {
    const lead = initialLinkedLead || state.leads[0];
    state.selectedLeadId = lead.lead_id;
    const reviewAsset = reviewAssetForLead(lead);
    state.selectedAssetId = reviewAsset?.asset_id || null;
    return;
  }

  const latest = liveAlert();
  if (latest) {
    state.selectedAssetId = latest.asset_id;
    return;
  }
}

function bestLeadForAutoAnalysis() {
  const reviewable = state.leads
    .map((lead) => ({ lead, asset: reviewAssetForLead(lead) }))
    .filter((item) => item.asset);
  if (!reviewable.length) {
    return null;
  }
  return reviewable.sort((left, right) => leadAutoRank(right.lead) - leadAutoRank(left.lead))[0];
}

function leadAutoRank(lead) {
  const sourceTime = Date.parse(lead.source_date || lead.last_refreshed_at || "") || 0;
  const inspectableBonus = reviewAssetForLead(lead) ? 10_000_000_000_000 : 0;
  return inspectableBonus + sourceTime;
}

async function autoSelectLeadForAnalysis({ announce = false, force = false } = {}) {
  if (state.selectedSiteLoading) {
    return false;
  }
  const candidate = bestLeadForAutoAnalysis();
  if (!candidate) {
    return false;
  }
  if (
    !force
    && state.selectedAssetId === candidate.asset.asset_id
    && selectedCompare()?.asset_id === candidate.asset.asset_id
  ) {
    return false;
  }

  state.selectedLeadId = candidate.lead.lead_id;
  state.selectedAssetId = candidate.asset.asset_id;
  state.selectedSiteContext = null;
  state.selectedEvidence = null;
  state.selectedAnalyst = null;
  state.selectedSiteLoading = true;
  renderMap();
  renderDrawer();
  focusMapOnAsset(candidate.asset);
  setChannelNote(`Auto-inspecting newest satellite-review lead: ${candidate.lead.title}.`);
  await loadSelectedSiteContext(candidate.asset.asset_id, candidate.lead.lead_id, { announce });
  return true;
}

function bindEvents() {
  dom.leadRefresh?.addEventListener("click", () => {
    void refreshLiveLeads();
  });

  dom.leadPopoverInspect?.addEventListener("click", () => {
    const lead = selectedLead();
    const asset = reviewAssetForLead(lead);
    if (!lead || !asset) {
      return;
    }
    state.selectedAssetId = asset.asset_id;
    state.selectedLeadId = lead.lead_id;
    state.selectedSiteContext = null;
    state.selectedEvidence = null;
    state.selectedAnalyst = null;
    state.selectedSiteLoading = true;
    renderMap();
    renderDrawer();
    focusMapOnAsset(asset);
    appendMessage("assistant", `Inspecting ${lead.title}. Loading current and baseline satellite evidence.`);
    void loadSelectedSiteContext(asset.asset_id, lead.lead_id, { announce: true });
  });

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
  updateStageClock();
  window.setInterval(updateStageClock, 30_000);
  setMissionStep(null, []);

  const [
    healthResult,
    modelStatusResult,
    assetsResult,
    leadsResult,
    snapshotResult,
    alertsResult,
    replayResult,
    currentResult,
    baselineResult,
    metricsResult,
  ] = await Promise.allSettled([
    loadJson(urls.health),
    loadJson(urls.modelStatus),
    loadJson(urls.assets),
    loadJson(urls.leads),
    loadJson(urls.snapshot),
    loadJson(urls.alerts),
    loadJson(urls.replay),
    loadJson(urls.current),
    loadJson(urls.baseline),
    loadJson(urls.metrics),
  ]);

  if (healthResult.status === "fulfilled") {
    state.health = healthResult.value;
  }
  if (modelStatusResult.status === "fulfilled") {
    state.modelStatus = modelStatusResult.value;
  }
  if (assetsResult.status === "fulfilled") {
    state.assets = assetsResult.value;
  }
  if (leadsResult.status === "fulfilled") {
    state.leads = leadsResult.value;
  }
  if (snapshotResult.status === "fulfilled") {
    state.replay = snapshotResult.value.replay || null;
    state.metrics = snapshotResult.value.metrics || null;
  }
  if (snapshotResult.status !== "fulfilled" && replayResult.status === "fulfilled") {
    state.replay = replayResult.value;
  }
  if (snapshotResult.status !== "fulfilled" && metricsResult.status === "fulfilled") {
    state.metrics = metricsResult.value;
  }

  pickInitialSelection();
  renderTopbar();
  renderMap();
  renderDrawer();
  seedTranscript();
  setMobileSheet(liveAlert() ? "site" : null);

  if (leadFeedNeedsRefresh()) {
    void refreshLiveLeads({ announce: false });
  } else {
    void autoSelectLeadForAnalysis({ announce: false });
  }

  if (healthResult.status !== "fulfilled") {
    renderHealthFallback();
  }
}

boot();
