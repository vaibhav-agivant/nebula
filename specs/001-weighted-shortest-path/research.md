# Research: Weighted Shortest Path

## R1: Where does the feature plug in?

- **Decision**: Reuse `FindPathSentence` (flag `weighted`) and `FindPathValidator`; add a new plan node and executor.
- **Rationale**: `FindPathSentence` already carries from/to/over/step/yield; permission check (`PermissionCheck.cpp`) and validator dispatch (`Validator.cpp`) key on `Sentence::Kind::kFindPath`, so no new sentence kind means no changes there. `PathContext` already has an unused `isWeight` field.
- **Alternatives**: a new `FindWeightedPathSentence` kind (needs permission, validator, planner registration and more files); extending `BFSShortestPath` (risks FR-012).

## R2: Grammar and keywords

- **Decision**: New `find_path_sentence` alternative; add `WEIGHT`, `WEIGHTED` tokens, both unreserved. `BY`, `UPTO`, `STEPS`, `REVERSELY`, `BIDIRECT`, `SHORTEST`, `PATH` already exist. `cost` is a plain label.
- **Rationale**: `over_clause` fixes direction immediately after the edge list; the required order is `OVER edges WEIGHT BY prop [direction]`, so the rule inlines `KW_OVER over_edges`. `find_path_upto_clause` forces a default of 5 steps, so a separate optional clause is needed for "unbounded".
- **Alternatives**: reserved keywords (would break users with `weight`/`weighted` identifiers, violates spec US5).

## R3: Search algorithm

- **Decision**: Dijkstra for the unbounded case; for `UPTO n`, layered best-cost-by-edge-count relaxation (at most n layers).
- **Rationale**: Correct for non-negative weights; negative weights are rejected at runtime per spec. Plain Dijkstra with a hop cap is wrong, because the cheapest path to an intermediate vertex may use too many hops while a costlier one with fewer hops is the only one that fits the limit. Layering is simple and correct.
- **Alternatives**: bidirectional Dijkstra (more code, only useful at scale); extending BFS (cannot handle weights).

## R4: How to read neighbours and weights

- **Decision**: Call `StorageClient::getNeighbors` directly from the executor (as `AllPathsExecutor` does) per frontier batch, requesting `_dst`, `_type`, `_rank` and the weight property for each listed edge type, with signed types for reverse direction.
- **Rationale**: Same mechanism existing path executors use; no storage changes; handles direction and multiple edge types.
- **Alternatives**: a plan-level Loop of `GetNeighbors` nodes (more planner code, awkward predecessor state).

## R5: Validation of the weight property

- **Decision**: In the validator, look up each edge type's schema via `schemaMng()->getEdgeSchema` and require the field to exist with int-family or float/double type. Error text names the property and edge type.
- **Rationale**: Satisfies "fail before running the search" with no runtime cost.

## R6: Cost typing and null weights

- **Decision**: Accumulate as int when every weight seen is int, otherwise double; null/non-numeric value at runtime is an error.
- **Rationale**: Matches the spec assumption; int overflow is not specially handled (documented ceiling).

## R7: Test approach

- **Decision**: Parser and validator gtests in tree for syntax and validation errors; the supplied `~/exp/tools/test.sh` acceptance run for end-to-end behaviour; run existing `FindPath*`/parser tests for regression.
- **Rationale**: Mirrors how existing path features are tested.
