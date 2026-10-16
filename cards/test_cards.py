"""Offline tests: every card must render valid XML from the fixture."""
import unittest
import xml.etree.ElementTree as ET

import os
import tempfile

from . import (card_activity, card_city, card_collab, card_drift,
                card_heatmap, card_languages, card_portscan, card_registry,
                card_rhythm, card_scope, card_training, card_ubuntu,
                card_years, github_data, history, stats, table)

FIXTURE = "testdata/profile.json"
_DATA = None    # loaded lazily so a missing fixture never breaks import


def data():
    global _DATA
    if _DATA is None:
        _DATA = github_data.load_fixture(FIXTURE)
    return _DATA


class CardsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = github_data.load_fixture(FIXTURE)

    def _render(self, module, *needles):
        svg = module.render(self.data)
        ET.fromstring(svg)                      # must be well-formed XML
        self.assertIn("<svg", svg)
        for n in needles:
            self.assertIn(n, svg)
        return svg

    def test_fixture_shape(self):
        self.assertGreater(self.data["total"], 0)
        self.assertGreater(len(self.data["repos"]), 0)
        self.assertGreater(len(self.data["days"]), 350)

    def test_fixture_has_commit_counts(self):
        for r in self.data["repos"]:
            self.assertIn("commits", r)
            self.assertGreaterEqual(r["commits"], 0)
            self.assertIn("private", r)

    def test_city_day_sky(self):
        from . import card_city
        svg = card_city.render(self.data)
        ET.fromstring(svg)
        self.assertIn("skyline --owner github.com/mgkvibez", svg)
        self.assertIn("population:", svg)
        self.assertIn("repeatCount=\"indefinite\"", svg)   # beacon blinks
        pub = [r for r in self.data["repos"] if not r["private"]]
        ranked = sorted(pub, key=card_city._score, reverse=True)
        self.assertIn("1. " + ranked[0]["name"][:8], svg)  # public ranks only
        # private repos: dark towers, names only, no stats
        priv = [r for r in self.data["repos"] if r["private"]]
        self.assertGreater(len(priv), 0)
        self.assertIn(priv[0]["name"], svg)
        self.assertNotIn(priv[0]["name"] + " — ", svg)
        self.assertIn("dark towers (private, names only)", svg)
        # fixture snapshot 11:50Z = 12:50 WAT -> day: sun, no moon, autumn
        self.assertIn("#ffd75e", svg)                 # sun
        self.assertNotIn("#e8edf5", svg)              # no moon
        self.assertIn("autumn · day", svg)

    def test_city_night_wat(self):
        from . import card_city
        data = dict(self.data, fetched_at="2026-09-16T21:30:00Z")  # 22:30 WAT
        svg = card_city.render(data)
        ET.fromstring(svg)
        self.assertIn("#e8edf5", svg)                 # moon
        self.assertIn("#d7843c", svg)                 # autumn leaves fall
        self.assertIn("autumn · night", svg)

    def test_city_winter_snow(self):
        from . import card_city
        data = dict(self.data, fetched_at="2027-01-10T13:00:00Z")  # winter
        svg = card_city.render(data)
        ET.fromstring(svg)
        self.assertIn("winter", svg)
        self.assertIn("#eef4fb", svg)                 # snow on rooftops
        self.assertNotIn("#d7843c", svg)             # no autumn leaves

    def test_training(self):
        svg = self._render(card_training, "train_contributor.py",
                           "converging", "epoch")
        self.assertIn(str(self.data["total"]), svg)

    def test_portscan(self):
        svg = self._render(card_portscan, "/tcp", "Nmap done")
        # one port line per repo
        self.assertEqual(svg.count("/tcp"), len(self.data["repos"]))
        # a state only appears if some repo is actually in it; require the
        # two the live profile always has, and never an unknown one
        for state in ("open", "filtered"):
            self.assertIn(state, svg)

    def test_registry(self):
        svg = self._render(card_registry, "MODEL", "serving", "params")
        self.assertIn("v0.", svg)              # mgkvibez repos are 0-star

    def test_scope(self):
        svg = self._render(card_scope, "CH1: CONTRIBUTIONS", "TRIG: RUN",
                           "samples")
        self.assertIn("polyline", svg)

    def test_states_consistent(self):
        for r in self.data["repos"]:
            st = card_registry._status(r)
            if r["archived"]:
                self.assertEqual(st[0], "deprecated")


if __name__ == "__main__":
    unittest.main()


class SnakeGradientTest(unittest.TestCase):
    """The snake must start blue and reach green by the end of its run."""

    STYLE = (
        "<style>:root{--ce:#ebedf0}"
        "@keyframes c0{25.0%{fill:var(--c1)}25.1%,100%{fill:var(--ce)}}"
        "@keyframes c1{50.0%{fill:var(--c1)}50.1%,100%{fill:var(--ce)}}"
        "@keyframes c2{75.0%{fill:var(--c2)}75.1%,100%{fill:var(--ce)}}"
        "</style>"
    )

    def test_journey_is_blue_to_green(self):
        from . import snake_gradient as sg
        out = sg.paint(self.STYLE, "dark")
        self.assertIn("25.0%{fill:#00c6ff}", out)   # start: electric blue
        self.assertIn("75.0%{fill:#00ff41}", out)    # end: terminal green
        self.assertIn("{fill:var(--ce)}", out)       # turn-offs untouched

    def test_midpoint_interpolates(self):
        from . import snake_gradient as sg
        self.assertEqual(sg.journey_color(0.5, "dark"), "#00e2a0")


class UbuntuTerminalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = github_data.load_fixture(FIXTURE)

    def test_renders_yaru_window(self):
        from . import card_ubuntu
        svg = card_ubuntu.render(self.data)
        ET.fromstring(svg)
        self.assertIn("whoami", svg)
        self.assertIn(self.data["login"] + "@github: ~", svg)  # GNOME titlebar
        self.assertIn("#300A24", svg)                  # Ubuntu aubergine bg
        self.assertIn("coffee: low", svg)
        self.assertIn("<animate", svg)                  # blinking cursor

    def test_gnome_window_controls(self):
        from . import card_ubuntu
        svg = card_ubuntu.render(self.data)
        self.assertIn("#E95420", svg)   # orange close button, right side


class SnakeBodyJourneyTest(unittest.TestCase):
    def test_body_shifts_blue_to_green(self):
        from . import snake_gradient as sg
        svg = ('<style>:root{--cb:#1b1f230a;--cs:purple;--ce:#ebedf0}'
               '.s{fill:var(--cs);animation:none linear 16700ms infinite}'
               '</style>')
        out = sg.paint(svg, "light")
        self.assertIn("--cs:#26ae4a", out)          # purple normalised away
        self.assertIn("@property --cs", out)        # registered -> interpolates
        self.assertIn("@keyframes eat{0%{--cs:#0969da}", out)   # starts blue
        self.assertIn(":root{animation:eat 16700ms linear infinite}", out)
        self.assertNotIn("syntax:'<color>'", out)                # raw < is invalid
        self.assertIn("&lt;color&gt;", out)                      # escaped instead
        ET.fromstring("<svg xmlns=\"http://www.w3.org/2000/svg\">"
                      + out + "</svg>")                          # must parse


# --- extended data layer + new cards (2026-10-16) ------------------------

class HeatmapCardTest(unittest.TestCase):
    def test_renders_grid_and_legend(self):
        svg_text = card_heatmap.render(data())
        self.assertIn("contributions.heatmap", svg_text)
        self.assertIn("</svg>", svg_text)
        ET.fromstring(svg_text)          # well-formed XML
        # legend prints the numeric band ranges
        self.assertIn("quartiles", svg_text)

    def test_bands_are_quartiles_of_active_days(self):
        days = data()["days"]
        cuts = stats.bands(days)
        self.assertEqual(len(cuts), 3)
        self.assertLessEqual(cuts[0], cuts[1])
        self.assertLessEqual(cuts[1], cuts[2])


class LanguagesCardTest(unittest.TestCase):
    def test_renders_share_bars(self):
        svg_text = card_languages.render(data())
        self.assertIn("langs.mix", svg_text)
        self.assertIn("%", svg_text)
        ET.fromstring(svg_text)

    def test_lang_shares_sum_to_one(self):
        shares = stats.lang_shares(data()["repo_langs"])
        total = sum(s for _, _, s in shares)
        self.assertAlmostEqual(total, 1.0, places=1)


class ActivityCardTest(unittest.TestCase):
    def test_renders_hero_and_tiles(self):
        svg_text = card_activity.render(data(), [])
        self.assertIn("contributions.activity", svg_text)
        self.assertIn("current streak", svg_text)
        ET.fromstring(svg_text)

    def test_streak_math(self):
        cur, longest = stats.streaks(data()["days"])
        self.assertGreater(longest, 0)
        self.assertLessEqual(cur, longest)


class CollabCardTest(unittest.TestCase):
    def test_renders_bars(self):
        svg_text = card_collab.render(data(), [])
        self.assertIn("contributions.collab", svg_text)
        self.assertIn("pull requests", svg_text)
        ET.fromstring(svg_text)


class RhythmCardTest(unittest.TestCase):
    def test_renders_grid_from_commit_sample(self):
        svg_text = card_rhythm.render(data())
        self.assertIn("commits.rhythm", svg_text)
        ET.fromstring(svg_text)

    def test_grid_sums_to_sample(self):
        grid = stats.rhythm_grid(data()["commit_sample"])
        self.assertEqual(sum(sum(r) for r in grid),
                         len(data()["commit_sample"]))


class YearsCardTest(unittest.TestCase):
    def test_renders_year_rows(self):
        svg_text = card_years.render(data())
        self.assertIn("contributions.years", svg_text)
        ET.fromstring(svg_text)

    def test_month_totals_are_twelve(self):
        for y in data()["years"]:
            self.assertEqual(len(stats.month_totals(y["days"])), 12)


class DriftCardTest(unittest.TestCase):
    def test_empty_archive_says_so(self):
        svg_text = card_drift.render(data(), [])
        self.assertIn("archive", svg_text)
        ET.fromstring(svg_text)

    def test_with_history_draws_dumbbells(self):
        entries = [{"date": "2026-09-15",
                    "langs": {"Python": 0.5, "TypeScript": 0.3}}]
        svg_text = card_drift.render(data(), entries)
        self.assertIn("pt", svg_text)
        ET.fromstring(svg_text)


class HistoryArchiveTest(unittest.TestCase):
    def test_record_then_load_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "history.jsonl")
            history.record(data(), path)
            history.record(data(), path)      # same day = one line
            entries = history.load(path)
            self.assertEqual(len(entries), 1)
            self.assertIn("langs", entries[0])
            ago = history.days_ago(entries, 28)
            self.assertIsNone(ago)            # snapshot is brand new

    def test_days_ago_finds_oldest_match(self):
        entries = [{"date": "2026-09-01", "langs": {}},
                   {"date": "2026-09-10", "langs": {}}]
        found = history.days_ago(entries, 28,
                                 now=__import__("datetime").date(2026, 10, 16))
        self.assertEqual(found["date"], "2026-09-10")


class TableTest(unittest.TestCase):
    def test_builds_all_sections(self):
        block = table.build(data(), [])
        for needle in ("Right now", "Metric", "Language", "Building"):
            self.assertIn(needle, block)

    def test_update_inserts_then_replaces(self):
        readme = "# hello\n\nread me\n"
        first = table.update(readme, "BLOCK-ONE")
        self.assertIn("cards:table:start", first)
        self.assertIn("BLOCK-ONE", first)
        self.assertIn("# hello", first)
        second = table.update(first, "BLOCK-TWO")
        self.assertIn("BLOCK-TWO", second)
        self.assertNotIn("BLOCK-ONE", second)
        self.assertIn("read me", second)
