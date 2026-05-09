from __future__ import annotations

import os

os.environ["BLACKLINE_SKIP_DOTENV"] = "1"

# Local live runs may use .env for live ACLED/GDELT cache settings. Tests
# must stay deterministic and load the seeded registry unless a test opts in.
for _key in (
    "ACLED_ACCESS_TOKEN",
    "ACLED_USERNAME",
    "ACLED_PASSWORD",
    "GDELT_API_KEY",
    "GDELT_CLOUD_API_KEY",
    "AGENT_API_KEY",
    "AGENT_ENDPOINT",
    "AGENT_HTTP_ENABLED",
    "AGENT_PROVIDER",
    "LEAD_REGISTRY_PATH",
    "SIMSAT_BASELINE_ENDPOINT",
    "SIMSAT_BASELINE_HTTP_ENABLED",
    "SIMSAT_CURRENT_ENDPOINT",
    "SIMSAT_CURRENT_HTTP_ENABLED",
    "SIMSAT_REQUIRED",
):
    os.environ[_key] = ""
