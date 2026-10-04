"""CLI: python -m src.pipeline --config config/pipeline.local.json [--stage ...]."""

import argparse
import json
from .data_processing.runtime import load_config, run_pipeline, run_stage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--stage", choices=("eda", "recover", "enrich", "report", "all"), default="all"
    )
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        result = run_pipeline(config) if args.stage == "all" else run_stage(args.stage, config)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, f"Pipeline stopped: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
