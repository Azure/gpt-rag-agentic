#!/usr/bin/env python3
"""
export_env_variables.py

Description:
    This script reads a .env file and exports its environment variables into a JSON file
    named `advanced_edit.json`, where each variable is formatted as:
    {
        "name": "<ENV_VAR_NAME>",
        "value": "<ENV_VAR_VALUE>",
        "slotSetting": false
    }

    This JSON format is intended for use in **Azure App Service** and **Azure Function Apps**
    under the **Advanced Edit** section of Application Settings. It allows you to quickly 
    migrate or replicate your local environment settings into the cloud service configuration.

Usage:
    From the root of the project (where your `.env` file is located), run:

        python util/export_env_variables.py

    Make sure a `.env` file exists in the root directory before running this script.
    The generated `advanced_edit.json` file will be saved inside the `.local/` folder 
    in the project root.

Example `.env` content:
    # Env Variables
    PYTHON_ENABLE_INIT_INDEXING="1"
    AZURE_SUBSCRIPTION_ID="your-subscription-id"
    AZURE_OPENAI_API_VERSION="2024-10-21"

Output example (`.local/advanced_edit.json`):
    [
        {
            "name": "PYTHON_ENABLE_INIT_INDEXING",
            "value": "1",
            "slotSetting": false
        },
        {
            "name": "AZURE_SUBSCRIPTION_ID",
            "value": "your-subscription-id",
            "slotSetting": false
        }
    ]

Note:
    - All variables will have `"slotSetting": false` by default.
    - This script is especially useful for deployment pipelines or manual configuration
      in Azure portal's "Advanced Edit" feature.
"""

import json
from pathlib import Path

def parse_env_file(env_path):
    env_vars = []
    with open(env_path, "r") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                value = value.strip().strip('"').strip("'")  # Remove quotes
                env_vars.append({
                    "name": key.strip(),
                    "value": value,
                    "slotSetting": False
                })
    return env_vars

def generate_json(env_vars, output_dir=".local", filename="advanced_edit.json"):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    output_file = output_path / filename
    with open(output_file, "w") as f:
        json.dump(env_vars, f, indent=2)
    print(f"✅ {filename} file created successfully at {output_file.resolve()}")

if __name__ == "__main__":
    env_file = Path(".env")
    if not env_file.exists():
        print("⚠️  .env file not found in the current directory.")
    else:
        env_vars = parse_env_file(env_file)
        generate_json(env_vars)
