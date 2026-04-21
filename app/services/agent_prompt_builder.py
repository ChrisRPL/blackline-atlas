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
        watchlist = "\n".join(
            f"- {asset.asset_id}: {asset.asset_name} / {asset.region} / {asset.asset_type}"
            for asset in assets
        )
        lead_index = "\n".join(
            f"- {lead.lead_id}: {lead.title} / {lead.region} / "
            f"{lead.category_guess or 'unknown'} / {lead.status}"
            for lead in leads
        )
        selected = (
            f"{selected_asset.asset_id}: {selected_asset.asset_name} / "
            f"{selected_asset.region} / {selected_asset.asset_type}"
            if selected_asset
            else "none"
        )
        selected_lead_line = (
            f"{selected_lead.lead_id}: {selected_lead.title} / {selected_lead.region} / "
            f"{selected_lead.category_guess or 'unknown'} / {selected_lead.status}"
            if selected_lead
            else "none"
        )

        return AgentPlannerPrompt(
            system=(
                "You are Blackline Atlas control-plane planning.\n"
                "Choose exactly one tool for the user request.\n"
                "Allowed tools: latest_alerts, biggest_disruptions, site_compare, explain_alert.\n"
                "Return JSON only with keys: tool, area, category, site_id, alert_id, camera.\n"
                "Use null when a field is not needed.\n"
                "Do not answer the user. Do not invent sites or alerts.\n"
                f"Allowed category values: {asset_types}. Otherwise use null.\n"
                "site_id must be exactly one watchlist asset_id or null.\n"
                "area must be exactly one watchlist region, one watchlist asset_name, or null.\n"
                "alert_id must stay null unless the user explicitly gives an alert id.\n"
                "camera may be null. If used, camera.mode must be watchlist, focus_asset, "
                "or focus_lead.\n"
                "camera.asset_id must be one watchlist asset_id or null.\n"
                "camera.lead_id must be one lead_registry lead_id or null.\n"
                "Prefer site_compare for compare/baseline requests.\n"
                "For site_compare, set site_id when one watchlist asset is clearly "
                "referenced and set category to null.\n"
                "Lead markers are browse signals, not guaranteed evidence-backed watchlist "
                "sites.\n"
                "If the selected lead has no linked watchlist asset, avoid site_compare and "
                "explain_alert; prefer latest_alerts or biggest_disruptions with camera focus "
                "on that lead.\n"
                "Prefer explain_alert for why/explain/confidence requests.\n"
                "Prefer biggest_disruptions for biggest/highest/most severe requests.\n"
                "Otherwise prefer latest_alerts."
            ),
            user=(
                f"watchlist:\n{watchlist}\n\n"
                f"selected_asset: {selected}\n"
                f"lead_registry:\n{lead_index}\n\n"
                f"selected_lead: {selected_lead_line}\n"
                f"user_query: {query}\n"
            ),
        )
