"""Offline tests: every card must render valid XML from the fixture."""
import unittest
import xml.etree.ElementTree as ET

from . import (card_portscan, card_registry, card_scope, card_training,
               github_data)

FIXTURE = "testdata/profile.json"


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
