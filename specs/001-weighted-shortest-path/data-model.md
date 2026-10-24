# Data Model: Weighted Shortest Path

No persistent schema or storage changes. These are the in-flight structures.

## FindPathSentence (extended)

| Field | Meaning |
|-------|---------|
| `weighted` | true for `FIND WEIGHTED SHORTEST PATH` |
| `weightProp` | edge property name from `WEIGHT BY` |
| `direction` | OUT (default), IN (`REVERSELY`), BOTH (`BIDIRECT`) |
| `step` | null when `UPTO` absent (unbounded) |

## PathContext (extended)

`isWeight` (existing, now set), `weightProp`, per-edge-type weight value type (int or double).

## Search state (executor only)

- **Label**: best known `cost` for a vertex (per edge-count layer when `UPTO` is given), plus predecessor link (previous vertex, edge type, rank, edge props).
- **Frontier**: cost-ordered queue (unbounded) or current layer (bounded).
- **Validation rules**: weight must be numeric and non-negative; cost is the sum along the path; a vertex is not repeated in the returned path.

## Result

DataSet with two columns named by the YIELD aliases (`p`, `c`): `p` is a `Path` value (src vertex, steps, dst), `c` is int or double. Zero rows when no path.
