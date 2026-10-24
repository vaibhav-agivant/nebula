// Copyright (c) 2026 vesoft inc. All rights reserved.
//
// This source code is licensed under Apache 2.0 License.
#ifndef GRAPH_EXECUTOR_ALGO_WEIGHTEDSHORTESTPATHEXECUTOR_H_
#define GRAPH_EXECUTOR_ALGO_WEIGHTEDSHORTESTPATHEXECUTOR_H_

#include "graph/executor/Executor.h"
#include "graph/planner/plan/Algo.h"

namespace nebula {
namespace graph {

class WeightedShortestPathExecutor final : public Executor {
 public:
  WeightedShortestPathExecutor(const PlanNode* node, QueryContext* qctx)
      : Executor("WeightedShortestPath", node, qctx) {
    pathNode_ = asNode<WeightedShortestPath>(node);
  }

  folly::Future<Status> execute() override;

 private:
  // W is int64_t or double, matching the weight property type
  template <typename W>
  Status search(const std::vector<Value>& starts, const std::vector<Value>& ends, DataSet& result);

  std::vector<Value> readVids(const std::string& var);

  const WeightedShortestPath* pathNode_{nullptr};
};

}  // namespace graph
}  // namespace nebula

#endif  // GRAPH_EXECUTOR_ALGO_WEIGHTEDSHORTESTPATHEXECUTOR_H_
