# Quickstart: Validate Weighted Shortest Path

## Prerequisites

Run from the repo directory (WSL): `cd ~/exp/nebula-speckit`.

## Build

```
~/exp/tools/build.sh
```

## Acceptance run

```
~/exp/tools/test.sh
```

Expected: all 17 checks pass (starts a local database, loads a small graph).

## Manual scenarios (in a console against the test graph)

Using a space with edge type `e(w int)` where `a->d` costs 10 directly and `a->b->c->d` costs 1+1+1:

1. `FIND WEIGHTED SHORTEST PATH FROM "a" TO "d" OVER e WEIGHT BY w YIELD path AS p, cost AS c` → one row, 3-hop path, `c` = 3.
2. Same with `UPTO 1 STEPS` → direct path, `c` = 10.
3. Same with `REVERSELY` from `"d"` to `"a"` → path found; without it → empty.
4. `... WEIGHT BY missing_prop ...` and a string-typed prop → clear error before search.
5. Unreachable dst or nonexistent vid → empty, no error.
6. `... YIELD path AS p, cost AS c | YIELD $-.c AS cost` → single `cost` column.
7. Existing `FIND SHORTEST PATH`, `FIND ALL PATH`, `FIND NOLOOP PATH` queries return the same results as before.

Details: [contract](contracts/weighted-shortest-path.md), [data model](data-model.md).
