#!/bin/bash
# Weighted-shortest-path test (17 checks). Run from inside a repo:  ~/exp/tools/test.sh   (~2 min)
R=$(git rev-parse --show-toplevel) || exit 1
docker run --rm -v $HOME/exp/tools:/work -v "$R":/work/nebula -w /work/nebula/build nebula-claude bash -c 'bash /work/start-cluster.sh "" && PYTHONPATH=/work/pylib python3 /work/weighted_tests.py'