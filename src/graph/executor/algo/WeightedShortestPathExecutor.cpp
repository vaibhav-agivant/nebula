// Copyright (c) 2022 vesoft inc. All rights reserved.
//
// This source code is licensed under Apache 2.0 License.
#include "graph/executor/algo/WeightedShortestPathExecutor.h"

#include "graph/planner/plan/Algo.h"
#include "graph/service/GraphFlags.h"

namespace nebula {
namespace graph {

folly::Future<Status> WeightedShortestPathExecutor::execute() {
  SCOPED_TIMER(&execTime_);
  pathNode_ = asNode<WeightedShortestPath>(node());
  auto root = std::make_shared<Node>();
  root->vid = pathNode_->src();
  best_.emplace(root->vid, root->cost);
  frontier_.emplace_back(root);
  if (root->vid == pathNode_->dst()) {
    found_ = root;
  }
  return expand();
}

folly::Future<Status> WeightedShortestPathExecutor::expand() {
  // dst needs no expansion, and neither does a vertex that cannot beat the path found so far
  std::vector<Value> vids;
  for (const auto& n : frontier_) {
    if (n->vid == pathNode_->dst() || (found_ != nullptr && !(n->cost < found_->cost))) {
      continue;
    }
    vids.emplace_back(n->vid);
  }
  if (vids.empty() || (pathNode_->maxSteps() != 0 && hops_ >= pathNode_->maxSteps())) {
    return finishResult();
  }
  ++hops_;

  StorageClient* storageClient = qctx_->getStorageClient();
  storage::StorageClient::CommonRequestParam param(pathNode_->space(),
                                                   qctx_->rctx()->session()->id(),
                                                   qctx_->plan()->id(),
                                                   qctx_->plan()->isProfileEnabled());
  return storageClient
      ->getNeighbors(param,
                     {nebula::kVid},
                     std::move(vids),
                     {},
                     storage::cpp2::EdgeDirection::OUT_EDGE,
                     nullptr,
                     nullptr,
                     pathNode_->edgeProps(),
                     nullptr,
                     false,
                     false,
                     {},
                     -1,
                     nullptr,
                     nullptr)
      .via(runner())
      .thenValue([this](auto&& resps) {
        memory::MemoryCheckGuard guard;
        auto completeness = handleCompleteness(resps, FLAGS_accept_partial_success);
        if (!completeness.ok()) {
          return folly::makeFuture<Status>(std::move(completeness).status());
        }
        List list;
        for (auto& resp : std::move(resps).responses()) {
          auto dataset = resp.get_vertices();
          if (dataset != nullptr) {
            list.values.emplace_back(std::move(*dataset));
          }
        }
        next_.clear();
        if (!list.values.empty()) {
          auto iter = std::make_unique<GetNeighborsIter>(std::make_shared<Value>(std::move(list)));
          auto status = relax(iter.get());
          if (!status.ok()) {
            return folly::makeFuture<Status>(std::move(status));
          }
        }
        // the new labels become the next frontier
        frontier_.clear();
        for (auto& entry : next_) {
          best_[entry.first] = entry.second->cost;
          if (entry.first == pathNode_->dst()) {
            found_ = entry.second;
          }
          frontier_.emplace_back(std::move(entry.second));
        }
        return expand();
      });
}

Status WeightedShortestPathExecutor::relax(GetNeighborsIter* iter) {
  // labels of the previous round, so that a round only extends paths by one edge
  std::unordered_map<Value, NodePtr> prev;
  for (const auto& n : frontier_) {
    prev.emplace(n->vid, n);
  }
  for (; iter->valid(); iter->next()) {
    auto edgeVal = iter->getEdge();
    if (!edgeVal.isEdge()) {
      continue;
    }
    const auto& edge = edgeVal.getEdge();
    auto from = prev.find(edge.src);
    if (from == prev.end()) {
      continue;
    }
    Cost weight;
    NG_RETURN_IF_ERROR(readWeight(edge, weight));
    auto cost = from->second->cost + weight;

    auto known = best_.find(edge.dst);
    if (known != best_.end() && !(cost < known->second)) {
      continue;
    }
    if (found_ != nullptr && !(cost < found_->cost)) {
      continue;
    }
    auto cand = next_.find(edge.dst);
    if (cand != next_.end() && !(cost < cand->second->cost)) {
      continue;
    }
    auto node = std::make_shared<Node>();
    node->vid = edge.dst;
    node->parent = from->second;
    node->type = edge.type;
    node->name = edge.name;
    node->rank = edge.ranking;
    node->cost = cost;
    next_[edge.dst] = std::move(node);
  }
  return Status::OK();
}

Status WeightedShortestPathExecutor::readWeight(const Edge& edge, Cost& weight) const {
  const auto& prop = pathNode_->weightProp();
  auto found = edge.props.find(prop);
  if (found == edge.props.end() || (!found->second.isInt() && !found->second.isFloat())) {
    return Status::Error("Weight property `%s' of edge `%s' is null or not a number.",
                         prop.c_str(),
                         edge.name.c_str());
  }
  const auto& v = found->second;
  if (v.isInt()) {
    weight.i = v.getInt();
  } else {
    weight.isDouble = true;
    weight.d = v.getFloat();
  }
  if (weight.asDouble() < 0) {
    return Status::Error("Negative weight %s found on edge `%s' (property `%s'), "
                         "FIND WEIGHTED SHORTEST PATH needs non-negative weights.",
                         v.toString().c_str(),
                         edge.name.c_str(),
                         prop.c_str());
  }
  return Status::OK();
}

Value WeightedShortestPathExecutor::buildPath(const Node* last) const {
  std::vector<const Node*> chain;
  for (auto* n = last; n != nullptr; n = n->parent.get()) {
    chain.emplace_back(n);
  }
  Path path;
  path.src = Vertex(chain.back()->vid, {});
  for (auto it = chain.rbegin() + 1; it != chain.rend(); ++it) {
    path.steps.emplace_back(Step(Vertex((*it)->vid, {}), (*it)->type, (*it)->name, (*it)->rank, {}));
  }
  return Value(std::move(path));
}

folly::Future<Status> WeightedShortestPathExecutor::finishResult() {
  DataSet result(pathNode_->colNames());
  if (found_ != nullptr) {
    result.rows.emplace_back(Row({buildPath(found_.get()), found_->cost.toValue()}));
  }
  return finish(ResultBuilder().value(Value(std::move(result))).build());
}

}  // namespace graph
}  // namespace nebula
