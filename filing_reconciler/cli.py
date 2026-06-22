"""Cross-platform console entrypoint (``filing-reconciler ...``).

Mirrors the Makefile targets so Windows users (no ``make``) have parity.
"""

import argparse
import logging
import sys
from typing import Any

from .runtime import GraphRuntime
from .samples import list_sample_sets, load_sample


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _print_summary(thread_id: str, result: dict[str, Any]) -> None:
    sources = result.get("sources", [])
    claims = result.get("claims", [])
    contradictions = result.get("contradictions", [])
    memo = result.get("final_memo") or result.get("draft_memo")
    interrupts = result.get("__interrupt__")

    print(f"\nrun_id: {thread_id}")
    print(f"documents ingested : {len(sources)}")
    print(f"claims extracted   : {len(claims)}")
    print(f"contradictions     : {len(contradictions)}")
    print(f"cost (usd)         : {result.get('cost_usd', 0.0):.6f}")

    if interrupts:
        print("\n** Paused for human review (HITL gate). **")
        print("Use the FastAPI endpoints or the runtime to submit a decision and resume.")
        return

    if memo is not None:
        print(f"\nMEMO: {memo.title}")
        print(f"  {memo.executive_summary}")
        for section in memo.sections:
            print(f"  - {section.heading}")
        print(f"  citations: {len(memo.citations)}")


def _cmd_run(args: argparse.Namespace) -> int:
    _configure_logging()
    company, inputs = load_sample(args.sample)
    with GraphRuntime() as rt:
        thread_id, result = rt.start(inputs, company=company)
    _print_summary(thread_id, result)
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    # Wired to the evaluation harness in step 7.
    print("The evaluation harness is implemented in build step 7 (`make eval`).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="filing-reconciler")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run a full analysis over a sample document set")
    run_p.add_argument(
        "--sample",
        default="set_a",
        help=f"Sample set id. Available: {', '.join(list_sample_sets()) or '(none)'}",
    )
    run_p.set_defaults(func=_cmd_run)

    eval_p = sub.add_parser("eval", help="Run the offline evaluation harness")
    eval_p.set_defaults(func=_cmd_eval)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
