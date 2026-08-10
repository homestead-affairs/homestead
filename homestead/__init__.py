"""homestead — the seat of Homestead · Affairs."""
# No `__version__` here on purpose. The git tag is the single source of truth
# (pyproject `dynamic = ["version"]` + hatch-vcs); a literal in this file was a
# second copy that drifted. Anything that needs the number reads it from the
# installed metadata: `importlib.metadata.version("homestead")`.
