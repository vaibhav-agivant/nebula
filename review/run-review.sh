#!/bin/bash
# usage: run-review.sh <repo folder name under ~/exp> [--baseline]
N=$1; shift
mkdir -p $HOME/exp/review
docker run --rm -v $HOME/exp/tools:/work -v $HOME/exp/review:/review -v $HOME/exp/$N:/work/nebula -w /work/nebula/build nebula-claude bash -c "bash /work/start-cluster.sh '' && PYTHONPATH=/work/pylib python3 /review/judge_extra.py $N $*"