#!/usr/bin/env python3
"""Generate a t-way covering array for combinatorial test-case design.

Given named factors with discrete levels (and optional forbidden combinations),
emit a COMPACT set of rows such that every combination of levels across any t
factors appears in at least one row (pairwise / t=2 by default). This is the
deterministic generator behind /test-agent's "rigorous" synthetic-dataset mode:
each row is a factor-vector; an agent then writes one concrete prompt per row,
and the row is stored as the example's metadata so coverage is auditable and
failures map back to factor cells.

Algorithm: deterministic greedy, one row at a time (AETG-style) — seed each row
with the most-needed uncovered t-tuple, then extend factor-by-factor choosing the
level that covers the most still-uncovered tuples. Guarantees full t-way coverage
(not provably minimal, but compact). No third-party deps.

Usage:
  python covering_array.py factors.json [--strength 2]
  echo '{"factors": {...}, "constraints": [...]}' | python covering_array.py -

Spec (JSON):
  {
    "factors": {
      "intent":      ["balance", "transfer", "dispute", "out_of_scope"],
      "persona":     ["novice", "expert", "hostile"],
      "difficulty":  ["easy", "hard"],
      "tool_needed": ["yes", "no"]
    },
    "constraints": [ {"intent": "out_of_scope", "tool_needed": "yes"} ]
  }

Output: JSON list of rows, each a {factor: level} dict (stderr prints the count).
"""
from itertools import combinations, product
import json
import sys


def _violates(assignment, constraints):
    """True if a (partial) assignment is a superset of any forbidden combo."""
    return any(all(assignment.get(k) == v for k, v in c.items()) for c in constraints)


def covering_array(factors, strength=2, constraints=None):
    constraints = constraints or []
    names = list(factors)
    t = max(1, min(strength, len(names)))

    # Every t-tuple that must be covered (skip ones already forbidden).
    required = set()
    for fset in combinations(names, t):
        for levels in product(*(factors[f] for f in fset)):
            assign = dict(zip(fset, levels))
            if not _violates(assign, constraints):
                required.add(tuple(sorted(assign.items())))

    def covers(row):
        return {tuple(sorted((f, row[f]) for f in fs)) for fs in combinations(names, t)}

    rows, uncovered, guard = [], set(required), 0
    while uncovered:
        guard += 1
        if guard > 100_000:
            raise RuntimeError("did not converge — check for over-tight constraints")
        row = dict(sorted(uncovered)[0])          # seed with a needed tuple
        for f in names:
            if f in row:
                continue
            assigned = [g for g in names if g in row]
            best, best_gain = None, -1
            for lvl in factors[f]:
                if _violates({**row, f: lvl}, constraints):
                    continue
                gain = sum(
                    tuple(sorted([(g, row[g]) for g in sub] + [(f, lvl)])) in uncovered
                    for sub in combinations(assigned, min(t - 1, len(assigned)))
                )
                if gain > best_gain:
                    best, best_gain = lvl, gain
            if best is None:                      # constraint dead-end: any legal level
                best = next((lvl for lvl in factors[f]
                             if not _violates({**row, f: lvl}, constraints)), factors[f][0])
            row[f] = best
        uncovered -= covers(row)
        rows.append(row)
    return rows


def _verify(rows, factors, strength, constraints):
    """Assert every required t-tuple is covered by at least one row."""
    names, t = list(factors), max(1, min(strength, len(factors)))
    need = set()
    for fset in combinations(names, t):
        for levels in product(*(factors[f] for f in fset)):
            a = dict(zip(fset, levels))
            if not _violates(a, constraints or []):
                need.add(tuple(sorted(a.items())))
    have = set()
    for r in rows:
        for fs in combinations(names, t):
            have.add(tuple(sorted((f, r[f]) for f in fs)))
    missing = need - have
    if missing:
        raise AssertionError(f"{len(missing)} t-tuples uncovered, e.g. {sorted(missing)[:3]}")


def main(argv):
    strength = 2
    if "--strength" in argv:
        i = argv.index("--strength"); strength = int(argv[i + 1]); argv = argv[:i] + argv[i + 2:]
    if not argv:
        print(__doc__); return 2
    raw = sys.stdin.read() if argv[0] == "-" else open(argv[0], encoding="utf-8").read()
    spec = json.loads(raw)
    factors, constraints = spec["factors"], spec.get("constraints", [])
    rows = covering_array(factors, strength, constraints)
    _verify(rows, factors, strength, constraints)
    full = 1
    for v in factors.values():
        full *= len(v)
    print(json.dumps(rows, indent=2))
    print(f"# {len(rows)} rows  (t={min(strength, len(factors))}, "
          f"vs {full} full-factorial)  coverage verified", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
