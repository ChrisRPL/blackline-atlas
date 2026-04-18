from __future__ import annotations

from dataclasses import dataclass

from app.schemas.asset import Asset


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
        selected_asset: Asset | None,
    ) -> AgentPlannerPrompt:
        asset_types = ", ".join(sorted({asset.asset_type for asset in assets}))
        watchlist = "\n".join(
            f"- {asset.asset_id}: {asset.asset_name} / {asset.region} / {asset.asset_type}"
            for asset in assets
        )
        selected = (
            f"{selected_asset.asset_id}: {selected_asset.asset_name} / "
            f"{selected_asset.region} / {selected_asset.asset_type}"
            if selected_asset
            else "none"
        )

        return AgentPlannerPrompt(
            system=(
                "You are Blackline Atlas control-plane planning.\n"
                "Choose exactly one tool for the user request.\n"
                "Allowed tools: latest_alerts, biggest_disruptions, site_compare, explain_alert.\n"
                "Return JSON only with keys: tool, area, category, site_id, alert_id.\n"
                "Use null when a field is not needed.\n"
                "Do not answer the user. Do not invent sites or alerts.\n"
                f"Allowed category values: {asset_types}. Otherwise use null.\n"
                "site_id must be exactly one watchlist asset_id or null.\n"
                "area must be exactly one watchlist region, one watchlist asset_name, or null.\n"
                "alert_id must stay null unless the user explicitly gives an alert id.\n"
                "Prefer site_compare for compare/baseline requests.\n"
                "For site_compare, set site_id when one watchlist asset is clearly "
                "referenced and set category to null.\n"
                "Prefer explain_alert for why/explain/confidence requests.\n"
                "Prefer biggest_disruptions for biggest/highest/most severe requests.\n"
                "Otherwise prefer latest_alerts."
            ),
            user=(
                f"watchlist:\n{watchlist}\n\n"
                f"selected_asset: {selected}\n"
                f"user_query: {query}\n"
            ),
        )
