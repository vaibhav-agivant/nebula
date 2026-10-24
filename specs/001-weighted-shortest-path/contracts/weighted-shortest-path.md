# Contract: FIND WEIGHTED SHORTEST PATH (nGQL)

## Grammar

```
FIND WEIGHTED SHORTEST PATH FROM <src> TO <dst>
  OVER <edge_type> [, <edge_type> ...]
  WEIGHT BY <edge_prop>
  [REVERSELY | BIDIRECT]
  [UPTO <n> STEPS]
  YIELD path AS p, cost AS c
```

`WEIGHT` and `WEIGHTED` are non-reserved keywords.

## Result

| Column | Type | Notes |
|--------|------|-------|
| `p` (alias of `path`) | PATH | same type/ordering as `FIND SHORTEST PATH` |
| `c` (alias of `cost`) | INT or FLOAT | sum of `<edge_prop>` over the path |

Zero or one row.

## Errors (before search unless noted)

| Condition | Result |
|-----------|--------|
| `<edge_prop>` missing on a listed edge type | semantic error naming prop and edge type |
| `<edge_prop>` not int/double | semantic error naming prop, edge type and actual type |
| YIELD not `path AS .., cost AS ..` | semantic error |
| Negative weight met during search | execution error (at run time) |

## Non-errors

Unreachable dst (within `UPTO`) and nonexistent src/dst return an empty result.

## Compatibility

`FIND SHORTEST PATH`, `FIND ALL PATH`, `FIND NOLOOP PATH` grammar, plans and results are unchanged.
