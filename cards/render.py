"""Render all four cards into assets/cards/.

    python -m cards.render --fixture testdata/profile.json   # offline
    python -m cards.render --login mgkvibez               # live (needs GITHUB_TOKEN)

Prints each file written so the workflow log reads as a record.
"""
import argparse
import os

from . import (card_portscan, card_registry, card_scope, card_training,
                card_ubuntu, github_data)

CARDS = {
    "training.svg": card_training.render,
    "portscan.svg": card_portscan.render,
    "registry.svg": card_registry.render,
    "scope.svg": card_scope.render,
    "ubuntu.svg": card_ubuntu.render,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--login")
    ap.add_argument("--fixture", default="testdata/profile.json")
    ap.add_argument("--out", default="assets/cards")
    args = ap.parse_args()

    if args.login:
        token = os.environ["GITHUB_TOKEN"]
        data = github_data.fetch(args.login, token)
    else:
        data = github_data.load_fixture(args.fixture)

    os.makedirs(args.out, exist_ok=True)
    for fname, fn in CARDS.items():
        path = os.path.join(args.out, fname)
        with open(path, "w") as f:
            f.write(fn(data))
        print(f"rendered {path}")


if __name__ == "__main__":
    main()
