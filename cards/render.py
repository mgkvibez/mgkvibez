"""Render all four cards into assets/cards/.

    python -m cards.render --fixture testdata/profile.json   # offline
    python -m cards.render --login mgkvibez               # live (needs GITHUB_TOKEN)

Prints each file written so the workflow log reads as a record.
"""
import argparse
import os

from . import (card_activity, card_city, card_collab, card_drift,
                card_heatmap, card_languages, card_portscan, card_registry,
                card_rhythm, card_scope, card_training, card_ubuntu,
                card_years, github_data, history, table)

# Simple cards take just the profile dict; the archive-aware ones also
# receive the snapshot history so they can move, not just measure.
CARDS = {
    "training.svg": card_training.render,
    "portscan.svg": card_portscan.render,
    "registry.svg": card_registry.render,
    "scope.svg": card_scope.render,
    "ubuntu.svg": card_ubuntu.render,
    "city.svg": card_city.render,
    "heatmap.svg": card_heatmap.render,
    "languages.svg": card_languages.render,
    "rhythm.svg": card_rhythm.render,
    "years.svg": card_years.render,
    "activity.svg": card_activity.render,
    "collab.svg": card_collab.render,
    "drift.svg": card_drift.render,
}

# cards that read the snapshot archive (data, entries) -> svg
ARCHIVE_CARDS = {
    "activity.svg": card_activity.render,
    "collab.svg": card_collab.render,
    "drift.svg": card_drift.render,
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
        # live runs feed the archive, and the archive feeds drift and the
        # 30-day movement lines back here on the next run.
        history.record(data, "history.jsonl")
        entries = history.load("history.jsonl")
    else:
        data = github_data.load_fixture(args.fixture)
        entries = history.load("history.jsonl")

    os.makedirs(args.out, exist_ok=True)
    for fname, fn in CARDS.items():
        path = os.path.join(args.out, fname)
        if fname in ARCHIVE_CARDS:
            svg_text = fn(data, entries)
        else:
            svg_text = fn(data)
        with open(path, "w") as f:
            f.write(svg_text)
        print(f"rendered {path}")

    # refresh the README table view between its markers
    try:
        with open("README.md") as f:
            readme = f.read()
        updated = table.update(readme, table.build(data, entries))
        if updated != readme:
            with open("README.md", "w") as f:
                f.write(updated)
            print("updated README table view")
    except FileNotFoundError:
        print("no README.md found; skipped table view")


if __name__ == "__main__":
    main()
