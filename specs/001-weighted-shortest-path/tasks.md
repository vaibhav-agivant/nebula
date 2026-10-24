# Tasks: Weighted Shortest Path in nGQL

**Input**: Design documents from `/specs/001-weighted-shortest-path/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/weighted-shortest-path.md

**Tests**: Parser and validator gtests plus the provided acceptance run (`~/exp/tools/test.sh`, 17 checks) are included because the spec's success criteria require them.

**Build**: `~/exp/tools/build.sh` from the repo root (minutes). **Acceptance**: `~/exp/tools/test.sh` (about 2 minutes).

## Format: `[ID] [P?] [Story] Description`

All paths are relative to the repo root.

---

## Phase 1: Setup

- [X] T001 Run `~/exp/tools/build.sh` once on the untouched tree to confirm the baseline builds, and note the build output location in `build/`
- [X] T002 [P] Run existing parser and path tests as a baseline: `src/parser/test/ParserTest.cpp` (FindPath cases) and `src/graph/validator/test/FindPathValidatorTest.cpp`

---

## Phase 2: Foundational (blocks all user stories)

**Purpose**: syntax, sentence data, context and plan node wiring so a weighted statement parses, validates and reaches an executor.

- [X] T003 Add `WEIGHT` and `WEIGHTED` tokens to `src/parser/scanner.lex` (case-insensitive like neighbours such as `"NOLOOP"`)
- [X] T004 Declare `KW_WEIGHT KW_WEIGHTED` in `src/parser/parser.yy` token list and add both to `unreserved_keyword` (and the `name_label` path) so existing identifiers named `weight`/`weighted` still parse
- [X] T005 Extend `FindPathSentence` in `src/parser/TraverseSentences.h` with `weighted`, `weightProp`, `direction` (default OUT_EDGE) and getters/setters; update `FindPathSentence::toString()` in `src/parser/TraverseSentences.cpp` to print `WEIGHTED`, `WEIGHT BY`, and direction
- [X] T006 Add the new `find_path_sentence` alternative in `src/parser/parser.yy`: `KW_FIND KW_WEIGHTED KW_SHORTEST KW_PATH from_clause to_clause KW_OVER over_edges KW_WEIGHT KW_BY name_label weight_direction weight_upto_clause yield_clause`; add `weight_direction` (empty, `KW_REVERSELY`, `KW_BIDIRECT`) and `weight_upto_clause` (empty yields null step meaning unbounded; `KW_UPTO legal_integer KW_STEPS`); declare `%type` entries. Confirm bison reports no new conflicts
- [X] T007 [P] Extend `PathContext` in `src/graph/context/ast/QueryAstContext.h` with `weightProp` (string) and a per-edge-type flag for double weights (existing `isWeight` is reused)
- [X] T008 [P] Add plan node kind `kWeightedShortestPath` in `src/graph/planner/plan/PlanNode.h` and its name string in `src/graph/planner/plan/PlanNode.cpp`
- [X] T009 Add `WeightedShortestPath` plan node class (space, from vid, to vid, max steps or unbounded, direction, edge types, weight prop, edge props, `clone`, `explain`) to `src/graph/planner/plan/Algo.h` and `src/graph/planner/plan/Algo.cpp`
- [X] T010 Create `src/graph/executor/algo/WeightedShortestPathExecutor.h` and `.cpp` skeleton (a `StorageAccessExecutor` subclass returning an empty two-column DataSet), register in `src/graph/executor/CMakeLists.txt` and the factory `case PlanNode::Kind::kWeightedShortestPath` in `src/graph/executor/Executor.cpp`
- [X] T011 Add a weighted branch in `PathPlanner::transform` in `src/graph/planner/ngql/PathPlanner.cpp` (and a private `weightedPlan()` in `PathPlanner.h`) that builds one `WeightedShortestPath` node with edge props (`_dst`, `_type`, `_rank`, weight prop per listed edge type, signed type for reverse) using the existing `buildEdgeProps` conventions, with colNames from the yield aliases. Do not touch the existing shortest/all-path branches
- [X] T012 Add a weighted branch in `FindPathValidator::validateImpl` in `src/graph/validator/FindPathValidator.cpp`: set `isWeight`, `weightProp`, direction, steps (unbounded sentinel when no UPTO), require single constant src and dst vid (clear error otherwise), validate over-edges via `ValidateUtil::validateOver`, and add a weighted `validateYield` accepting exactly `path AS <alias>, cost AS <alias>` and emitting outputs `PATH` and numeric column types

**Checkpoint**: the statement parses, validates and returns an empty result.

---

## Phase 3: User Story 1 - Cheapest path (Priority: P1) MVP

**Goal**: return the minimum-total-weight path and its cost (FR-002, FR-003, FR-004, FR-013).

**Independent Test**: graph with `a->d` cost 10 and `a->b->c->d` cost 3: the statement returns the 3-hop path and `c` = 3.

- [X] T013 [P] [US1] Add parser tests for the base weighted statement (parses, `toString` round trip) in `src/parser/test/ParserTest.cpp`
- [X] T014 [US1] Implement Dijkstra in `src/graph/executor/algo/WeightedShortestPathExecutor.cpp`: priority queue by cost, expand frontier vertices in batches through `StorageClient::getNeighbors` (same call shape as `AllPathsExecutor::getNeighbors`), read `_dst`, `_type`, `_rank` and the weight prop per edge type, settle each vertex once, stop when dst is settled
- [X] T015 [US1] Track predecessor links (previous vertex, edge name/type, rank, edge props) and rebuild the `Path` (src vertex, `Step`s, dst last) in the same shape and orientation as `FIND SHORTEST PATH` results in `src/graph/executor/algo/WeightedShortestPathExecutor.cpp`; check how `BFSShortestPath` builds `Step` values in `src/graph/executor/algo/ShortestPathBase.cpp` and mirror it
- [X] T016 [US1] Accumulate cost as int when all weights are int, otherwise double; emit a single row `[path, cost]` with colNames from the plan node in `src/graph/executor/algo/WeightedShortestPathExecutor.cpp`
- [X] T017 [US1] Rebuild with `~/exp/tools/build.sh` and run the US1 scenario from `quickstart.md` (cheaper longer path wins, tie returns one path with correct cost)

**Checkpoint**: MVP works end to end for forward single-type queries.

---

## Phase 4: User Story 2 - Direction, edge types, hop limit (Priority: P2)

**Goal**: FR-007, FR-008, FR-009.

**Independent Test**: cheap 4-edge path vs pricier 2-edge path; `UPTO 2 STEPS` returns the 2-edge path.

- [X] T018 [P] [US2] Add parser tests for `REVERSELY`, `BIDIRECT`, `UPTO n STEPS`, and multiple edge types in `src/parser/test/ParserTest.cpp`
- [X] T019 [US2] Implement bounded search in `src/graph/executor/algo/WeightedShortestPathExecutor.cpp`: when a step limit is set, use layered relaxation (best cost per vertex with at most k edges, up to n layers) and pick the cheapest dst label across layers; keep Dijkstra for the unbounded case (see research R3)
- [X] T020 [US2] Support direction in the executor (`OUT_EDGE`, `IN_EDGE`, `BOTH`) using the signed edge types from T011, and make sure the returned path still reads src to dst with correct edge orientation, in `src/graph/executor/algo/WeightedShortestPathExecutor.cpp`
- [X] T021 [US2] Support several edge types: read the weight from whichever listed type each returned edge belongs to, in `src/graph/executor/algo/WeightedShortestPathExecutor.cpp`
- [X] T022 [US2] Rebuild and run the US2 scenarios from `quickstart.md` (limit, reverse, bidirect, multi-type)

---

## Phase 5: User Story 3 - Errors and empty results (Priority: P2)

**Goal**: FR-005, FR-006, FR-010.

**Independent Test**: missing prop, string prop and negative weight each error clearly; unreachable dst and nonexistent vertex return empty.

- [X] T023 [US3] In `src/graph/validator/FindPathValidator.cpp` check each listed edge type's schema via `qctx_->schemaMng()->getEdgeSchema`: the weight field must exist and be an int type or FLOAT/DOUBLE; otherwise return `Status::SemanticError` naming the property, edge type and (if wrong) its actual type
- [X] T024 [P] [US3] Add validator tests in `src/graph/validator/test/FindPathValidatorTest.cpp` for missing property, string property, bad yield clause, and multiple src/dst
- [X] T025 [US3] In the executor, return an execution error when a negative weight is read (message names the edge and value) and when a weight is null or non-numeric, in `src/graph/executor/algo/WeightedShortestPathExecutor.cpp`
- [X] T026 [US3] Ensure unreachable dst (including within the `UPTO` limit), nonexistent src or dst, and an empty neighbour response all return an empty DataSet with no error, in `src/graph/executor/algo/WeightedShortestPathExecutor.cpp`; handle src equal to dst the same way as the existing `FIND SHORTEST PATH`
- [X] T027 [US3] Rebuild and run the error and empty-result scenarios from `quickstart.md`

---

## Phase 6: User Story 4 - Pipe (Priority: P3)

**Goal**: FR-011.

**Independent Test**: `... YIELD path AS p, cost AS c | YIELD $-.c AS cost` returns one `cost` row.

- [X] T028 [US4] Verify the validator output columns (`p`, `c`, with correct value types) in `FindPathValidator::validateYield` in `src/graph/validator/FindPathValidator.cpp` so `$-.c` resolves in a following `YIELD`; fix any column name or type mismatch
- [X] T029 [US4] Rebuild and run the piped example, plus a piped example on an empty result, from `quickstart.md`

---

## Phase 7: User Story 5 - Existing statements unchanged (Priority: P1)

**Goal**: FR-012.

**Independent Test**: all pre-existing path tests produce identical results.

- [X] T030 [P] [US5] Add parser tests in `src/parser/test/ParserTest.cpp` that `FIND SHORTEST PATH`, `FIND ALL PATH`, `FIND NOLOOP PATH` still parse unchanged and that `weight`, `weighted` are still usable as tag, edge and property names
- [X] T031 [US5] Re-run the T002 baseline tests (`ParserTest`, `FindPathValidatorTest`, `src/graph/executor/test/FindPathTest.cpp`) and confirm the results match the baseline; confirm no edits were made to the existing branches of `PathPlanner.cpp` or to `BFSShortestPathExecutor`/`AllPathsExecutor`/`MultiShortestPathExecutor`
  - Note: ParserTest (54 pass) and FindPathValidatorTest (7 pass) were run; the executor test FindPathTest.cpp was not built or run.

---

## Phase 8: Polish

- [X] T032 Run the full acceptance run `~/exp/tools/test.sh` and confirm all 17 checks pass
- [X] T033 [P] Add the statement to nGQL docs only if the repo's `docs/` already holds nGQL reference pages (skip otherwise) (skipped: docs/ only holds RFCs)
- [X] T034 Review the diff for stray changes outside the files listed in `plan.md`, and for formatting per `Coding_Style_Guide.md`

---

## Dependencies

- Phase 1 first. Phase 2 blocks all stories (T003 to T006 grammar; T007 to T012 depend on T005; T011 and T012 depend on T007, T009).
- US1 (T013 to T017) depends on Phase 2. US2, US3, US4 each build on US1's executor and can then proceed in any order. US5 can run any time after Phase 2 and must finish before Polish.
- T014 to T016, T019 to T021, T025, T026 all edit the same executor file, so they are sequential.

## Parallel Examples

- Phase 2: T007 and T008 together; T003/T004 (scanner and parser tokens) with T005 only if edits to `parser.yy` are sequenced.
- Test writing: T013, T018, T024, T030 are different test regions and can be drafted in parallel with executor work.

## Implementation Strategy

1. MVP: Phases 1, 2 and 3 (forward, single edge type, unbounded) and verify.
2. Add US2, then US3, then US4, rebuilding and checking after each.
3. Run US5 regression checks continuously, and the full acceptance run last.
