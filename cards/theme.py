"""Palette and typography for the mgkvibez cards.

The profile's existing accent is terminal green (#00ff41) — the cards keep
that identity, on a GitHub-dark base, all in system monospace stacks because
web fonts do not load inside GitHub's camo-proxied SVGs.
"""

BG = "#0a0e14"        # outer background
PANEL = "#0d1117"     # card panel
BORDER = "#1f2730"    # card border
FG = "#c9d1d9"        # primary text
DIM = "#8b949e"       # secondary text
GREEN = "#00ff41"     # accent (matches the profile theme)
AMBER = "#e3b341"     # warnings / mid-tier states
CYAN = "#58a6ff"      # informational
RED = "#f85149"       # hot / stale
PHOSPHOR = "#39d353"  # scope beam
SCOPE_BG = "#04120a"  # scope screen

MONO = ("ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, "
        "'Liberation Mono', monospace")
