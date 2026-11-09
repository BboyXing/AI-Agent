from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from llm_gateway.main import create_app  # noqa: E402


def main() -> None:
    app = create_app(config_path=ROOT / "apps" / "api" / "config" / "gateway.example.yaml")
    output = ROOT / "packages" / "contracts" / "openapi.json"
    output.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
