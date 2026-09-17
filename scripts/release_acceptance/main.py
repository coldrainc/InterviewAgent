from __future__ import annotations

import argparse
import json
from pathlib import Path

from .flows import logout_and_verify_refresh_revoked, run_full_acceptance, verify_persistence


def main() -> None:
    parser = argparse.ArgumentParser(description="Run release acceptance against an isolated API")
    parser.add_argument("--base-url", default="http://127.0.0.1:8022")
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--phase", choices=("full", "persistence", "logout"), required=True)
    parser.add_argument(
        "--confirm-isolated",
        action="store_true",
        help="Confirm that the target uses disposable acceptance data",
    )
    args = parser.parse_args()
    if not args.confirm_isolated:
        parser.error("--confirm-isolated is required because this suite creates and mutates data")

    if args.phase == "full":
        state = run_full_acceptance(args.base_url)
        args.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nAcceptance state written to {args.state_file}")
        return

    state = json.loads(args.state_file.read_text(encoding="utf-8"))
    if args.phase == "persistence":
        verify_persistence(args.base_url, state)
    else:
        logout_and_verify_refresh_revoked(args.base_url, state)


if __name__ == "__main__":
    main()
