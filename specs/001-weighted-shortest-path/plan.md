# Implementation Plan: Weighted Shortest Path in nGQL

**Branch**: `speckit` (spec dir `001-weighted-shortest-path`) | **Date**: 2026-10-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-weighted-shortest-path/spec.md`

## Summary

Add `FIND WEIGHTED SHORTEST PATH ... WEIGHT BY <prop> ... YIELD path AS p, cost AS c`. Approach: a new grammar rule that reuses `FindPathSentence` with a weighted flag, validation in the existing `FindPathValidator`, and one new plan node plus executor (`WeightedShortestPath`) that runs a cost-ordered search in the graph service, fetching neighbours through the existing storage `getNeighbors` call. Existing shortest/all/noloop planners and executors are not modified, which satisfies FR-012. See [research.md](research.md).

## Technical Context

**Language/Version**: C++17 (NebulaGraph graphd), Bison/Flex grammar

**Primary Dependencies**: folly, existing storage client (`StorageClient::getNeighbors`), existing `Path`/`Step` value types

**Storage**: N/A (reads edges via existing storage RPC; no schema or data change)

**Testing**: gtest parser/validator tests in-tree; acceptance via `~/exp/tools/test.sh` (17 checks)

**Target Platform**: Linux, built in the project's Docker image via `~/exp/tools/build.sh`

**Project Type**: single C++ service (query engine)

**Performance Goals**: no regression to existing path queries; small-graph queries return as fast as existing path queries (SC-006)

**Constraints**: unbounded search must terminate on cyclic graphs; honour existing memory-check guards; no change to existing statement behaviour

**Scale/Scope**: single src and single dst; weighted search touches only vertices cheaper than the best known dst cost

## Constitution Check

`.specify/memory/constitution.md` is the unfilled template, so there are no ratified principles to gate on. Self-imposed gates applied instead: (1) no edits to behaviour of existing path code, (2) new keywords must be non-reserved, (3) every spec requirement gets a test. All pass; re-checked after Phase 1 with no change.

## Project Structure

### Documentation (this feature)

```text
specs/001-weighted-shortest-path/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── weighted-shortest-path.md
└── tasks.md             # created later by /speckit-tasks
```

### Source Code (repository root)

```text
src/parser/scanner.lex                          # WEIGHT, WEIGHTED tokens
src/parser/parser.yy                            # tokens, unreserved_keyword, new find_path_sentence rule
src/parser/TraverseSentences.{h,cpp}            # weighted flag, weight prop, direction, optional step on FindPathSentence; toString
src/parser/test/ParserTest.cpp                  # parse tests incl. regression of existing forms

src/graph/context/ast/QueryAstContext.h         # PathContext: weightProp, weight edge info (isWeight already exists)
src/graph/validator/FindPathValidator.{h,cpp}   # weighted branch: edge-prop existence/type, yield check, single vid
src/graph/validator/test/FindPathValidatorTest.cpp

src/graph/planner/ngql/PathPlanner.{h,cpp}      # weighted branch -> WeightedShortestPath node
src/graph/planner/plan/{PlanNode.h,PlanNode.cpp,Algo.h,Algo.cpp}   # new node kind
src/graph/executor/Executor.cpp                 # factory case
src/graph/executor/algo/WeightedShortestPathExecutor.{h,cpp}       # search
src/graph/executor/CMakeLists.txt
src/graph/executor/test/ (optional unit test)
```

**Structure Decision**: extend the existing single-project layout in place, mirroring how `AllPaths` is wired (plan node + `StorageAccessExecutor`). No new libraries or directories except one executor file pair.

## Design Highlights

- **Grammar**: `KW_FIND KW_WEIGHTED KW_SHORTEST KW_PATH from_clause to_clause KW_OVER over_edges KW_WEIGHT KW_BY name_label [KW_REVERSELY|KW_BIDIRECT] [UPTO n STEPS] yield_clause`. The existing `over_clause` puts direction right after the edge list, but this syntax places `WEIGHT BY` between them, so the rule spells `OVER` out itself. `WEIGHT` and `WEIGHTED` are added to `unreserved_keyword` so existing identifiers keep parsing. `cost` is an ordinary label, so it needs no token.
- **Unbounded default**: the existing `find_path_upto_clause` defaults to 5 steps; the weighted rule uses its own optional clause with no default (spec: unbounded).
- **Validation (before search)**: each listed edge type must have the property with INT or FLOAT/DOUBLE type, else `SemanticError`; yield must be exactly `path AS p, cost AS c` forms; from/to must be constant single vids.
- **Search**: without `UPTO`, Dijkstra by cost. With `UPTO n`, a layered relaxation by edge count (best cost to each vertex with at most k edges) so the cheapest path within the limit is correct even when a cheaper-but-longer path would otherwise shadow it. Negative weight met while expanding aborts with an error. Zero-cost cycles are harmless because paths are rebuilt from predecessor links and a vertex is settled once per layer.
- **Output**: one row `[Path, cost]`, path built like existing shortest path results (src vertex, then steps with edge name/type/rank, dst last); empty dataset if unreachable or vertices absent.
- **Direction**: reuses the existing storage edge-direction handling (`OUT_EDGE`, `IN_EDGE`, `BOTH`) and the signed edge type convention used by `PathPlanner::buildEdgeProps`.

## Risks

- Path construction for reverse and bidirectional edges must match existing orientation conventions (verify against `BFSShortestPath` results).
- Adding keywords can create grammar conflicts; mitigated by unreserved list and a clean `bison` run.
- Build takes minutes per iteration; keep changes in few files.

## Complexity Tracking

No constitution violations to justify.
