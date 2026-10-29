#!/bin/bash
# Build nebula-graphd for the repo you are standing in (incremental). Usage: ~/exp/tools/build.sh
R=$(git rev-parse --show-toplevel) || exit 1
docker run --rm -v $HOME/exp/tools:/work -v "$R":/work/nebula -w /work/nebula/build nebula-claude bash -c 'make -j6 nebula-graphd 2>&1 | tail -40; exit ${PIPESTATUS[0]}'