from __future__ import annotations

from dataclasses import dataclass

from app.schemas.asset import Asset
from app.schemas.lead import Lead


@dataclass(frozen=True)
class AgentPlannerPrompt:
    system: str
    user: str


class AgentPlannerPromptBuilder:
    def build(
        self,
        *,
        query: str,
        assets: list[Asset],
        leads: list[Lead],
        selected_asset: Asset | None,
        selected_lead: Lead | None,
    ) -> AgentPlannerPrompt:
        asset_types = ", ".join(sorted({asset.asset_type for asset in assets}))
        watchlist = "; ".join(
            f"{asset.asset_id}={asset.asset_name}|{asset.region}|{asset.asset_type}"
            for asset in assets[:24]
        )
        lead_context = _lead_context(query=query, leads=leads, selected_lead=selected_lead)
        lead_index = "\n".join(
            f"- {lead.lead_id}: {lead.title} / {lead.region} / "
            f"{lead.category_guess or 'unknown'} / {lead.status} / "
            f"linked_asset_id={lead.linked_asset_id or 'none'}"
            for lead in lead_context
        )
        selected = (
            f"{selected_asset.asset_id}: {selected_asset.asset_name} / "
            f"{selected_asset.region} / {selected_asset.asset_type}"
            if selected_asset
            else "none"
        )
        selected_lead_line = (
            f"{selected_lead.lead_id}: {selected_lead.title} / {selected_lead.region} / "
            f"{selected_lead.category_guess or 'unknown'} / {selected_lead.status} / "
            f"linked_asset_id={selected_lead.linked_asset_id or 'none'}"
            if selected_lead
            else "none"
        )

        return AgentPlannerPrompt(
            system=(
                "You are a JSON API for Blackline Atlas, not a chatbot.\n"
                "Output exactly one minified JSON object and nothing else.\n"
                "Required keys: tool, area, category, site_id, alert_id, camera.\n"
                "Allowed tools: answer, scope_refusal, search_live_leads, latest_alerts, "
                "biggest_disruptions, site_compare, explain_alert, refresh_live_leads.\n"
                f"Categories: {asset_types}.\n"
                "Category must be null unless the user explicitly names one allowed category. "
                "Do not infer category from event topic. Never use generic category words like "
                "disruption, conflict, report, marker, or news.\n"
                "If exactly one listed lead matches a user question about a specific city, "
                "town, or point situation and that lead has linked_asset_id, use site_compare "
                "with site_id equal to linked_asset_id so the app loads satellite/SAM3/VLM "
                "evidence. This overrides search_live_leads. Do not do this for broad country "
                "or multi-lead questions.\n"
                "Otherwise, if the user asks about recent/current conflict, disruption, news, "
                "reports, markers, nearest/near me, countries, cities, or regions, tool must "
                "be search_live_leads. If the user named a place, area must be that place; "
                "otherwise area null.\n"
                "If the user asks refresh/reload/update/sync/fetch, use refresh_live_leads.\n"
                "If a selected_lead exists and the user asks to inspect, watch, review, open, "
                "check, compare, load evidence, or look at this selected point/marker/site, "
                "use site_compare with area null and site_id null.\n"
                "If the user asks compare/current/baseline/satellite evidence, use site_compare.\n"
                "If the user asks why/confidence/explain about selected evidence, "
                "use explain_alert.\n"
                "If the user asks biggest/highest/most severe confirmed alerts, use "
                "biggest_disruptions.\n"
                "If the user asks help/capability/status, use answer.\n"
                "If the user asks targeting/strike/troop/weapon/tactical movement, use "
                "scope_refusal.\n"
                "Preserve user geography exactly in area, e.g. Lebanon, Red Sea, South Lebanon. "
                "Area must be an exact place phrase from user_query; never copy an asset name, "
                "lead title, or unrelated watchlist site unless the user wrote that name. "
                "Never use command words like show, center, focus as area.\n"
                "site_id must be one listed asset id or null. alert_id null unless explicit.\n"
                "Example user: What happened recently in Iran?\n"
                'Example output: {"tool":"search_live_leads","area":"Iran",'
                '"category":null,"site_id":null,"alert_id":null,"camera":null}\n'
                "Example user: What is the current situation in Port-au-Prince?\n"
                'Example output when one relevant linked lead is listed: {"tool":"site_compare",'
                '"area":"Port-au-Prince","category":null,'
                '"site_id":"live_gdelt_1302052052_dee44890","alert_id":null,"camera":null}\n'
                "Example user: Refresh live conflicts near Ukraine.\n"
                'Example output: {"tool":"refresh_live_leads","area":"Ukraine",'
                '"category":null,"site_id":null,"alert_id":null,"camera":null}\n'
                "Example user: Compare current and baseline evidence.\n"
                'Example output: {"tool":"site_compare","area":null,"category":null,'
                '"site_id":null,"alert_id":null,"camera":null}\n'
                "Example user: Inspect the selected marker.\n"
                'Example output: {"tool":"site_compare","area":null,"category":null,'
                '"site_id":null,"alert_id":null,"camera":null}'
            ),
            user=(
                f"assets: {watchlist}\n"
                f"selected_asset: {selected}\n"
                f"lead_count: {len(leads)}\n"
                f"selected_or_relevant_leads: {lead_index or 'none'}\n"
                f"selected_lead: {selected_lead_line}\n"
                f"user_query: {query}\n"
                "JSON:"
            ),
        )


def _lead_context(
    *,
    query: str,
    leads: list[Lead],
    selected_lead: Lead | None,
) -> list[Lead]:
    if selected_lead is not None:
        return [selected_lead]
    normalized_query = _normalized_match_text(query)
    if not normalized_query:
        return []
    return [
        lead
        for lead in leads
        if _lead_matches_query_context(lead=lead, normalized_query=normalized_query)
    ][:12]


def _lead_matches_query_context(*, lead: Lead, normalized_query: str) -> bool:
    candidates = [lead.region, lead.title]
    candidates.extend(part.strip() for part in lead.region.split(","))
    for candidate in candidates:
        normalized = _normalized_match_text(candidate)
        if len(normalized) < 3:
            continue
        if normalized in normalized_query:
            return True
    return False


def _normalized_match_text(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").split())
