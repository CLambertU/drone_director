"""Execute the exact competition scenario without a browser; export measured results."""

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.config.settings import Settings
from backend.services.environment_service import EnvironmentService
from core.repository import create_registry
from simulation.engine import Engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aircraft", type=int)
    parser.add_argument("--scenario", choices=("full", "congestion", "weather", "closure", "failure", "conflict"), default="full")
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    aircraft_count = args.aircraft if args.aircraft is not None else (100 if args.scenario == "full" else 24)
    output = args.output or Path("data/demo_report.json" if args.scenario == "full"
                                 else f"data/scenarios/{args.scenario}.json")
    registry = create_registry()
    try:
        engine = Engine(registry, EnvironmentService(), Settings(_env_file=None))
        begin = perf_counter()
        engine.prepare_demo(aircraft_count=aircraft_count, seed=args.seed, scenario=args.scenario)
        setup_seconds = perf_counter() - begin
        begin = perf_counter()
        engine.step(args.steps)
        elapsed = perf_counter() - begin
        report = engine.report()
        report["benchmark"] = {"setup_seconds": setup_seconds, "execution_seconds": elapsed,
                               "requested_steps": args.steps,
                               "executed_steps": round(report["simulation"]["time_s"] / engine.tick_seconds),
                               "aircraft": aircraft_count, "seed": args.seed, "scenario": args.scenario}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"output": str(output.resolve()), **report["benchmark"],
                          "metrics": report["metrics"]}, ensure_ascii=False, indent=2))
    finally:
        registry.close()


if __name__ == "__main__":
    main()
