// Copyright (c) 2022 vesoft inc. All rights reserved.
//
// This source code is licensed under Apache 2.0 License.

#ifndef GRAPH_EXECUTOR_ALGO_WEIGHTEDSHORTESTPATHEXECUTOR_H_
#define GRAPH_EXECUTOR_ALGO_WEIGHTEDSHORTESTPATHEXECUTOR_H_

#include "graph/executor/StorageAccessExecutor.h"

// Cheapest path between one src and one dst, weighted by an edge property.
//
// The search runs in rounds, one storage request per round. Round k expands the vertices whose
// best cost improved in round k-1 and relaxes their edges against the labels of round k-1
// (Bellman-Ford with a frontier). After round k the label of a vertex is its cheapest cost over
// paths of at most k edges, so `UPTO n STEPS` is exact: stop after n rounds. Without a limit the
// search stops when no label improves, which is guaranteed because weights are non-negative and an
// edge is only taken when it strictly lowers the cost.
//
// Every label points to an immutable chain of its predecessors, so the returned path always has
// exactly the reported cost and never repeats a vertex.
namespace nebula {
namespace graph {
class WeightedShortestPath;

class WeightedShortestPathExecutor final : public StorageAccessExecutor {
 public:
  WeightedShortestPathExecutor(const PlanNode* node, QueryContext* qctx)
      : StorageAccessExecutor("WeightedShortestPath", node, qctx) {}

  folly::Future<Status> execute() override;

 private:
  // int while every weight on the path is an int, double otherwise
  struct Cost {
    bool isDouble{false};
    int64_t i{0};
    double d{0};

    double asDouble() const {
      return isDouble ? d : static_cast<double>(i);
    }
    bool operator<(const Cost& rhs) const {
      if (!isDouble && !rhs.isDouble) {
        return i < rhs.i;
      }
      return asDouble() < rhs.asDouble();
    }
    Cost operator+(const Cost& rhs) const {
      Cost c;
      if (!isDouble && !rhs.isDouble) {
        c.i = i + rhs.i;
      } else {
        c.isDouble = true;
        c.d = asDouble() + rhs.asDouble();
      }
      return c;
    }
    Value toValue() const {
      return isDouble ? Value(d) : Value(i);
    }
  };

  // one step of an immutable predecessor chain
  struct Node {
    Value vid;
    std::shared_ptr<const Node> parent;
    // the edge that led from parent to vid, type is signed by search direction
    EdgeType type{0};
    std::string name;
    EdgeRanking rank{0};
    Cost cost;
  };
  using NodePtr = std::shared_ptr<const Node>;

  folly::Future<Status> expand();

  Status relax(GetNeighborsIter* iter);

  Status readWeight(const Edge& edge, Cost& weight) const;

  Value buildPath(const Node* last) const;

  folly::Future<Status> finishResult();

 private:
  const WeightedShortestPath* pathNode_{nullptr};
  size_t hops_{0};
  std::vector<NodePtr> frontier_;
  std::unordered_map<Value, Cost> best_;
  // cheapest known way to dst
  NodePtr found_;
  // candidates of the current round, keyed by vertex
  std::unordered_map<Value, NodePtr> next_;
};
}  // namespace graph
}  // namespace nebula
#endif
