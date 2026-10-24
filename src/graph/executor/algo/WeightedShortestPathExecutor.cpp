// Copyright (c) 2026 vesoft inc. All rights reserved.
//
// This source code is licensed under Apache 2.0 License.
#include "graph/executor/algo/WeightedShortestPathExecutor.h"

#include <algorithm>
#include <unordered_map>
#include <unordered_set>

#include "graph/context/iterator/GetNeighborsIter.h"
#include "graph/util/SchemaUtil.h"

namespace nebula {
namespace graph {

folly::Future<Status> WeightedShortestPathExecutor::execute() {
  SCOPED_TIMER(&execTime_);
  DataSet result;
  result.colNames = pathNode_->colNames();
  auto starts = readVids(pathNode_->fromVar());
  auto ends = readVids(pathNode_->toVar());
  auto status = pathNode_->weightIsInt() ? search<int64_t>(starts, ends, result)
                                         : search<double>(starts, ends, result);
  NG_RETURN_IF_ERROR(status);
  return finish(ResultBuilder().value(Value(std::move(result))).build());
}

std::vector<Value> WeightedShortestPathExecutor::readVids(const std::string& var) {
  const auto& metaVidType = *(qctx()->rctx()->session()->space().spaceDesc.vid_type_ref());
  auto vidType = SchemaUtil::propTypeToValueType(metaVidType.get_type());
  std::unordered_set<Value> seen;
  std::vector<Value> vids;
  // read the DataSet directly: a constant vid list has no sequential iterator
  const auto& value = ectx_->getValue(var);
  if (!value.isDataSet()) {
    return vids;
  }
  for (const auto& row : value.getDataSet().rows) {
    const auto& vid = row.values.front();
    if (vid.type() == vidType && seen.insert(vid).second) {
      vids.emplace_back(vid);
    }
  }
  return vids;
}

// Layered Bellman-Ford: round k relaxes the edges out of the vertices improved in round k-1,
// so round k yields the cheapest paths with at most k edges and UPTO n STEPS is exact.
// One batched storage request per round.
// ponytail: worst case |V| rounds; switch to Dijkstra if the unbounded case gets slow.
template <typename W>
Status WeightedShortestPathExecutor::search(const std::vector<Value>& starts,
                                            const std::vector<Value>& ends,
                                            DataSet& result) {
  struct Label {
    W cost;
    Value prev;  // vertex this label was reached from, in the previous round
    Step step;   // the edge used; its dst is the labelled vertex
  };
  using Round = std::unordered_map<Value, Label>;

  auto* storage = qctx_->getStorageClient();
  storage::StorageClient::CommonRequestParam param(pathNode_->space(),
                                                   qctx_->rctx()->session()->id(),
                                                   qctx_->plan()->id(),
                                                   qctx_->plan()->isProfileEnabled());
  for (const auto& start : starts) {
    std::vector<Round> rounds(1);
    rounds[0].emplace(start, Label{0, Value(), Step()});
    std::unordered_map<Value, W> best;
    best.emplace(start, 0);

    for (uint32_t step = 1; step <= pathNode_->maxSteps() && !rounds.back().empty(); ++step) {
      // once every end is reached, costs at or above the worst of them cannot help
      bool allReached = true;
      W bound = 0;
      for (const auto& end : ends) {
        auto found = best.find(end);
        if (found == best.end()) {
          allReached = false;
          break;
        }
        bound = std::max(bound, found->second);
      }
      std::vector<Value> frontier;
      for (const auto& entry : rounds.back()) {
        if (!allReached || entry.second.cost < bound) {
          frontier.emplace_back(entry.first);
        }
      }
      if (frontier.empty()) {
        break;
      }

      auto resp = storage
                      ->getNeighbors(param,
                                     {nebula::kVid},
                                     frontier,
                                     {},
                                     pathNode_->edgeDirection(),
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
                      .get();
      if (resp.completeness() != 100) {
        return Status::Error("Request to storage failed while searching the weighted path.");
      }
      List list;
      for (auto& r : std::move(resp).responses()) {
        if (auto* ds = r.get_vertices()) {
          list.values.emplace_back(std::move(*ds));
        }
      }
      auto listVal = std::make_shared<Value>(std::move(list));
      GetNeighborsIter iter(listVal);

      const auto& prev = rounds.back();
      Round next;
      for (; iter.valid(); iter.next()) {
        auto edgeVal = iter.getEdge();
        if (UNLIKELY(!edgeVal.isEdge())) {
          continue;
        }
        const auto& edge = edgeVal.getEdge();
        auto prop = edge.props.find(pathNode_->weightProp());
        if (prop == edge.props.end() || !(prop->second.isInt() || prop->second.isFloat())) {
          return Status::Error("Weight property `%s' of edge `%s' is not a number.",
                               pathNode_->weightProp().c_str(),
                               edge.name.c_str());
        }
        W weight = prop->second.isInt() ? static_cast<W>(prop->second.getInt())
                                        : static_cast<W>(prop->second.getFloat());
        if (weight < 0) {
          return Status::Error("Negative weight %s on edge `%s' is not supported.",
                               std::to_string(weight).c_str(),
                               edge.name.c_str());
        }
        W cost = prev.at(edge.src).cost + weight;
        auto known = best.find(edge.dst);
        if (known != best.end() && cost >= known->second) {
          continue;
        }
        best[edge.dst] = cost;
        next[edge.dst] = Label{
            cost, edge.src, Step(Vertex(edge.dst, {}), edge.type, edge.name, edge.ranking, {})};
      }
      rounds.emplace_back(std::move(next));
    }

    for (const auto& end : ends) {
      if (end == start || best.find(end) == best.end()) {
        continue;
      }
      // the last round that improved `end` holds its cheapest label
      size_t r = rounds.size();
      while (--r > 0 && rounds[r].find(end) == rounds[r].end()) {
      }
      std::vector<Step> steps;
      Value at = end;
      for (; r > 0; --r) {
        const auto& label = rounds[r].at(at);
        steps.emplace_back(label.step);
        at = label.prev;
      }
      Path path;
      path.src = Vertex(start, {});
      path.steps.assign(steps.rbegin(), steps.rend());
      result.rows.emplace_back(Row({Value(std::move(path)), Value(best.at(end))}));
    }
  }
  return Status::OK();
}

}  // namespace graph
}  // namespace nebula
