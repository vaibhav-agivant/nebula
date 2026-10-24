# Feature Specification: Weighted Shortest Path in nGQL

**Feature Branch**: `speckit` (spec directory: `001-weighted-shortest-path`)

**Created**: 2026-10-24

**Status**: Draft

**Input**: User description: "Add weighted shortest path to nGQL: `FIND WEIGHTED SHORTEST PATH FROM <src> TO <dst> OVER <edge_type> [, <edge_type> ...] WEIGHT BY <edge_prop> [REVERSELY | BIDIRECT] [UPTO <n> STEPS] YIELD path AS p, cost AS c`"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Find the cheapest path between two vertices (Priority: P1)

A graph user (e.g. routing, logistics, network analysis) wants the path between two vertices whose edge weights add up to the smallest total, even when it has more hops than another path. They run the new statement naming the edge types and the numeric edge property to use as weight, and get back one path and its total weight.

**Why this priority**: This is the core capability; the existing `FIND SHORTEST PATH` only minimises hop count and cannot answer "cheapest" questions.

**Independent Test**: On a small graph where a 3-hop path costs 3 and a 1-hop path costs 10, run the statement and confirm the 3-hop path is returned with cost 3.

**Acceptance Scenarios**:

1. **Given** a 1-hop path of weight 10 and a 3-hop path of total weight 3 between src and dst, **When** the user runs `FIND WEIGHTED SHORTEST PATH FROM src TO dst OVER e WEIGHT BY w YIELD path AS p, cost AS c`, **Then** one row is returned with `p` the 3-hop path and `c` equal to 3.
2. **Given** several paths with the same minimal cost, **When** the statement is run, **Then** exactly one of them is returned and `c` is the correct minimal cost.
3. **Given** a path returned by this statement and one returned by `FIND SHORTEST PATH` for the same endpoints, **When** compared, **Then** `p` has the same path type and vertex/edge ordering (src first, dst last).
4. **Given** a double-typed weight property, **When** the statement is run, **Then** `c` is the sum of the doubles; with an int-typed property, the sum of the ints.

---

### User Story 2 - Control direction, edge types and hop limit (Priority: P2)

The user restricts the search to certain edge types, traverses edges backwards (`REVERSELY`) or in both directions (`BIDIRECT`), and caps the path length with `UPTO <n> STEPS`.

**Why this priority**: Needed for real-world graphs but builds on the core search.

**Independent Test**: With a cheap 4-edge path and a pricier 2-edge path, `UPTO 2 STEPS` returns the 2-edge path while no limit returns the 4-edge path.

**Acceptance Scenarios**:

1. **Given** a cheapest path of 4 edges and another of 2 edges, **When** `UPTO 2 STEPS` is given, **Then** the cheapest path with at most 2 edges is returned; without `UPTO`, the overall cheapest is returned.
2. **Given** edges only pointing from dst to src, **When** `REVERSELY` is used, **Then** the path is found; without it, the result is empty.
3. **Given** edges pointing in mixed directions along the route, **When** `BIDIRECT` is used, **Then** the cheapest path using edges in either direction is returned.
4. **Given** several edge types listed with the weight property present on each, **When** the statement is run, **Then** paths may mix those edge types and the weight is read from whichever type each edge belongs to.

---

### User Story 3 - Clear errors and empty results (Priority: P2)

The user gets a clear message for misuse and an empty (not error) result when nothing can be found.

**Why this priority**: Predictable failure behaviour is required for safe use in scripts and pipelines.

**Independent Test**: Run with a missing property, a string property, and a negative-weight graph, and confirm each fails with a clear error; run with an unreachable dst and a nonexistent vertex and confirm empty results.

**Acceptance Scenarios**:

1. **Given** the weight property does not exist on one of the listed edge types, **When** the statement is run, **Then** it fails with a clear error before any search work begins.
2. **Given** the weight property is neither int nor double on a listed edge type, **When** run, **Then** it fails with a clear error before the search.
3. **Given** the search meets an edge with a negative weight, **When** run, **Then** it fails with a clear error.
4. **Given** dst is unreachable (or unreachable within `UPTO`), or src or dst does not exist, **When** run, **Then** an empty result is returned with no error.

---

### User Story 4 - Use the result in a pipe (Priority: P3)

The user pipes the result into further statements, e.g. `... YIELD path AS p, cost AS c | YIELD $-.c AS cost`.

**Why this priority**: Composability with existing nGQL; small incremental value.

**Independent Test**: Run the piped example and confirm it returns the cost value only.

**Acceptance Scenarios**:

1. **Given** a reachable dst, **When** the piped example is run, **Then** a single row with column `cost` equal to the minimal total weight is returned.
2. **Given** an empty find result, **When** piped, **Then** the downstream statement returns an empty result.

---

### User Story 5 - Existing path statements are unaffected (Priority: P1)

Users of `FIND SHORTEST PATH`, `FIND ALL PATH` and `FIND NOLOOP PATH` see no change in syntax, results or errors.

**Why this priority**: Regression safety for existing workloads.

**Independent Test**: Run the existing checks for those statements; results are identical to before the change.

**Acceptance Scenarios**:

1. **Given** any statement valid before the change using those three forms, **When** run after the change, **Then** it returns the same results or errors as before.
2. **Given** a schema element or property named `weighted`, `weight` or `cost`, **When** existing statements reference it, **Then** they still parse and run as before.

### Edge Cases

- src equals dst: assumed to follow the existing `FIND SHORTEST PATH` behaviour for that case (see Assumptions).
- Zero-weight edges are valid; cycles of zero weight must not cause non-termination or repeated vertices in the result.
- Multiple edges (ranks) between the same pair of vertices: the cheapest applies.
- Unbounded search on a graph with cycles must terminate.
- A non-positive `UPTO` limit follows existing `UPTO` conventions for path statements.
- Null weight value on an edge at run time: treated as an error rather than silently zero (assumption).
- Fractional (double) sums: the reported cost is the sum of the weights along the returned path.
- Multiple src or dst values: only the single-src, single-dst form is in scope (see Assumptions).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST accept `FIND WEIGHTED SHORTEST PATH FROM <src> TO <dst> OVER <edge_type> [, <edge_type> ...] WEIGHT BY <edge_prop> [REVERSELY | BIDIRECT] [UPTO <n> STEPS] YIELD path AS p, cost AS c`.
- **FR-002**: The system MUST return the single path from src to dst with the smallest total weight as `p`, with the same path type and node ordering as `FIND SHORTEST PATH`, and the total weight as `c`.
- **FR-003**: The total weight MUST equal the sum of `<edge_prop>` over the returned path's edges; a cheaper path with more hops MUST be preferred over a costlier path with fewer hops.
- **FR-004**: When multiple paths tie on minimal cost, the system MUST return any one of them, with the correct cost.
- **FR-005**: `<edge_prop>` MUST be read from every listed edge type; the system MUST fail with a clear error, before running the search, if it is absent on any listed edge type or its type is not int or double.
- **FR-006**: The system MUST fail with a clear error if a negative weight is encountered during the search.
- **FR-007**: `UPTO <n> STEPS` MUST limit the path to at most n edges and the cheapest path within that limit MUST be returned; without `UPTO` the search MUST be unbounded.
- **FR-008**: `REVERSELY` MUST follow edges backwards; `BIDIRECT` MUST follow edges in both directions; with neither, edges are followed forwards.
- **FR-009**: Multiple edge types MUST be supported in the `OVER` clause.
- **FR-010**: If dst is unreachable (within the limit), or src or dst does not exist, the system MUST return an empty result without error.
- **FR-011**: The result MUST be usable as input to a pipe (e.g. `| YIELD $-.c AS cost`).
- **FR-012**: `FIND SHORTEST PATH`, `FIND ALL PATH` and `FIND NOLOOP PATH` MUST behave exactly as before, including syntax acceptance, results and errors.
- **FR-013**: The returned path MUST NOT repeat vertices.

### Key Entities

- **Weighted path**: ordered alternating vertices and edges from src to dst, same shape as the existing shortest-path value.
- **Cost**: the numeric total of the weight property over the path's edges; int if the property is int, double if double.
- **Weight property**: a named int or double property that exists on each listed edge type.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On test graphs where the cheapest path has more hops than the fewest-hop path, 100% of queries return the minimum-cost path and the correct cost.
- **SC-002**: 100% of the invalid-weight cases (missing property, non-numeric property, negative weight) produce a clear error message and no path result.
- **SC-003**: 100% of unreachable-destination and nonexistent-vertex queries return an empty result with no error.
- **SC-004**: All existing automated checks for `FIND SHORTEST PATH`, `FIND ALL PATH` and `FIND NOLOOP PATH` pass unchanged.
- **SC-005**: The provided acceptance run (17 checks) passes in full, including the weighted-path scenarios.
- **SC-006**: On the small test graph, a weighted shortest path query returns in about the same time as an equivalent existing path query, so users perceive no extra delay.

## Assumptions

- Only a single source and a single destination are supported; multi-source/destination forms are out of scope.
- The YIELD clause is exactly `path AS p, cost AS c`; other YIELD forms are out of scope.
- `WEIGHT BY` takes one property name, which must be present on every listed edge type.
- Weight values are treated as non-negative; null weights at run time are an error.
- src equals dst follows the existing `FIND SHORTEST PATH` convention.
- `UPTO <n> STEPS` follows the existing convention for hop limits in path statements.
- Mixed int/double weights across edge types are allowed; the sum is a double if any weight is double.
- Existing graph spaces, schemas and data need no migration.
- Build and verification use the project's provided build and test scripts.
