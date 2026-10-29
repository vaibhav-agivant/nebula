# Weighted shortest path experiment: evaluation materials

This branch holds the evaluation materials for an experiment in which Claude Code implemented
`FIND WEIGHTED SHORTEST PATH` ([vesoft-inc/nebula#4309](https://github.com/vesoft-inc/nebula/issues/4309))
in NebulaGraph twice: once with plain Claude Code and once with Spec Kit. Both runs used the model
claude-sonnet-5-5 in Claude Code 2.1.310, with the same prompt and the same starting code.

| Ref | Contents |
| --- | --- |
| tag `baseline` | Upstream commit `426266b5c`, the starting point of both runs |
| branch `plain-claude-code` | Plain Claude Code's result: one commit on `baseline` |
| branch `spec-kit` | Spec Kit's tooling setup, then its result (code, unit tests and `specs/`): two commits on `baseline` |
| branch `evaluation` | This branch: the scripts and saved results used to evaluate both |

## Layout

The scripts expect this layout:

```
~/exp/tools            this branch's tools/
~/exp/review           this branch's review/
~/exp/base             checkout of tag baseline
~/exp/nebula-claude    checkout of branch plain-claude-code (with tag baseline)
~/exp/nebula-speckit   checkout of branch spec-kit (with tag baseline)
```

`tools/`

| File | Purpose |
| --- | --- |
| `prompt-as-delivered.txt` | The task prompt exactly as both sessions received it |
| `build.sh` | Builds `nebula-graphd` for the repository you run it from, inside Docker |
| `test.sh` | Starts a one-node cluster and runs the acceptance suite (about 2 minutes) |
| `weighted_tests.py` | The acceptance suite: 17 checks. The agents were told about it and could run it |
| `start-cluster.sh`, `txnlib.py` | Cluster start-up and client helpers used by the suites |
| `demo.py`, `multi.py` | The demo queries and the multi-source / pipe check quoted in the report |
| `Dockerfile` | The build image (reconstructed from `docker history`) |

`review/`

| File | Purpose |
| --- | --- |
| `judge_extra.py`, `judge_extra2.py` | The hidden suite: 150 randomised queries checked against a reference implementation, plus probes P1 to P18 and K1 to K5. Never shown to the agents |
| `run-review.sh`, `run-review2.sh` | Run the hidden suite against a build: `~/exp/review/run-review.sh nebula-claude` |
| `out-*.json`, `out2-*.json` | Saved hidden-suite results for `base`, `nebula-claude` (plain) and `nebula-speckit` |
| `demo-*.txt` | Saved demo output from both builds |
| `speckit-unit-tests.patch`, `plain-unit-test-run.txt` | Spec Kit's unit tests applied to the plain build, and the result |
| `evidence.py` | Recomputes the report's headline numbers (see below) |

## Setup

Not included here; fetch them yourself:

- `tools/nebula-console`: the nebula-console 3.8.0 binary from [vesoft-inc/nebula-console](https://github.com/vesoft-inc/nebula-console/releases).
- `tools/pylib`: `pip install --target ~/exp/tools/pylib nebula3-python==3.8.3`
- The Docker image: `docker build -t nebula-claude ~/exp/tools`
- A configured build directory in each checkout, made once inside the image: `mkdir build && cd build && cmake -DCMAKE_BUILD_TYPE=Debug -DENABLE_TESTING=OFF ..`

Then, from a checkout: `~/exp/tools/build.sh && ~/exp/tools/test.sh`.

## evidence.py

E7 to E10 (lines of code, hidden-suite results, existing queries, specification size) come from the
repositories and the saved outputs here. E1 to E6 and E11 (time, tokens, tool calls, test runs, compile
errors, prompt, look-ups) come from the Claude Code session records, which are not published, so those
lines only run on the experiment machine.
