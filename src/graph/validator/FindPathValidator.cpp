/* Copyright (c) 2020 vesoft inc. All rights reserved.
 *
 * This source code is licensed under Apache 2.0 License.
 */

#include "graph/validator/FindPathValidator.h"

#include "graph/planner/plan/Algo.h"
#include "graph/planner/plan/Logic.h"
#include "graph/util/ExpressionUtils.h"
#include "graph/util/ValidateUtil.h"

namespace nebula {
namespace graph {
Status FindPathValidator::validateImpl() {
  auto fpSentence = static_cast<FindPathSentence*>(sentence_);
  pathCtx_ = getContext<PathContext>();
  pathCtx_->isShortest = fpSentence->isShortest();
  pathCtx_->noLoop = fpSentence->noLoop();
  pathCtx_->withProp = fpSentence->withProp();
  pathCtx_->singleShortest = fpSentence->singleShortest();
  pathCtx_->inputVarName = inputVarName_;
  pathCtx_->limit = fpSentence->limit();

  NG_RETURN_IF_ERROR(validateStarts(fpSentence->from(), pathCtx_->from));
  NG_RETURN_IF_ERROR(validateStarts(fpSentence->to(), pathCtx_->to));
  NG_RETURN_IF_ERROR(ValidateUtil::validateOver(qctx_, fpSentence->over(), pathCtx_->over));
  NG_RETURN_IF_ERROR(validateWhere(fpSentence->where()));
  NG_RETURN_IF_ERROR(ValidateUtil::validateStep(fpSentence->step(), pathCtx_->steps));
  pathCtx_->isWeight = fpSentence->isWeighted();
  if (pathCtx_->isWeight) {
    NG_RETURN_IF_ERROR(validateWeight(fpSentence));
  }
  NG_RETURN_IF_ERROR(validateYield(fpSentence->yield()));

  return Status::OK();
}

// The weight property must exist on every listed edge type and be an int or a double.
Status FindPathValidator::validateWeight(FindPathSentence* sentence) {
  const auto& prop = sentence->weightProp();
  auto space = vctx_->whichSpace();
  auto names = sentence->over()->edges();
  bool allInt = true;
  for (size_t i = 0; i < names.size(); ++i) {
    auto schema = qctx_->schemaMng()->getEdgeSchema(space.id, pathCtx_->over.edgeTypes[i]);
    const auto* field = schema ? schema->field(prop) : nullptr;
    const auto& edge = *names[i]->edge();
    if (field == nullptr) {
      return Status::SemanticError(
          "Weight property `%s' not found in edge type `%s'.", prop.c_str(), edge.c_str());
    }
    switch (field->type()) {
      case nebula::cpp2::PropertyType::INT8:
      case nebula::cpp2::PropertyType::INT16:
      case nebula::cpp2::PropertyType::INT32:
      case nebula::cpp2::PropertyType::INT64:
        break;
      case nebula::cpp2::PropertyType::FLOAT:
      case nebula::cpp2::PropertyType::DOUBLE:
        allInt = false;
        break;
      default:
        return Status::SemanticError(
            "Weight property `%s' of edge type `%s' must be int or double.",
            prop.c_str(),
            edge.c_str());
    }
  }
  pathCtx_->weightProp = prop;
  pathCtx_->weightIsInt = allInt;
  return Status::OK();
}

// Check validity of filter expression, rewrites expression to fit its sementic,
// disable some invalid expression types, collect properties used in filter.
Status FindPathValidator::validateWhere(WhereClause* where) {
  if (where == nullptr) {
    return Status::OK();
  }
  // Not Support $-、$var、$$.tag.prop、$^.tag.prop、agg
  auto filterExpr = where->filter();
  if (ExpressionUtils::findAny(filterExpr,
                               {Expression::Kind::kSrcProperty,
                                Expression::Kind::kDstProperty,
                                Expression::Kind::kVarProperty,
                                Expression::Kind::kInputProperty})) {
    return Status::SemanticError("Not support `%s' in where sentence.",
                                 filterExpr->toString().c_str());
  }

  auto undefinedParams = graph::ExpressionUtils::ExtractInnerVars(filterExpr, qctx_);
  if (!undefinedParams.empty()) {
    auto msg = folly::join(", ", undefinedParams);
    return Status::SemanticError("Undefined parameters: %s", msg.c_str());
  }
  auto* newFilter = graph::ExpressionUtils::rewriteParameter(filterExpr, qctx_);

  where->setFilter(ExpressionUtils::rewriteLabelAttr2EdgeProp(newFilter));
  auto filter = where->filter();

  auto typeStatus = deduceExprType(filter);
  NG_RETURN_IF_ERROR(typeStatus);
  auto type = typeStatus.value();
  if (type != Value::Type::BOOL && type != Value::Type::NULLVALUE &&
      type != Value::Type::__EMPTY__) {
    std::stringstream ss;
    ss << "`" << filter->toString() << "', expected Boolean, "
       << "but was `" << type << "'";
    return Status::SemanticError(ss.str());
  }

  NG_RETURN_IF_ERROR(deduceProps(filter, pathCtx_->exprProps));
  pathCtx_->filter = filter;
  return Status::OK();
}

// Check validity of yield columns
Status FindPathValidator::validateYield(YieldClause* yield) {
  if (yield == nullptr) {
    return Status::SemanticError("Missing yield clause.");
  }
  if (pathCtx_->isWeight) {
    const auto& cols = yield->columns();
    if (cols.size() != 2 || strcasecmp(cols[0]->expr()->toString().c_str(), "path") != 0 ||
        strcasecmp(cols[1]->expr()->toString().c_str(), "cost") != 0) {
      return Status::SemanticError("Only support `YIELD path AS <name>, cost AS <name>'.");
    }
    outputs_.emplace_back(cols[0]->name(), Value::Type::PATH);
    outputs_.emplace_back(cols[1]->name(),
                          pathCtx_->weightIsInt ? Value::Type::INT : Value::Type::FLOAT);
    pathCtx_->colNames = getOutColNames();
    return Status::OK();
  }
  if (yield->columns().size() != 1) {
    return Status::SemanticError("Only support yield path");
  }
  auto col = yield->columns().front();
  if (col->expr()->kind() != Expression::Kind::kLabel || col->expr()->toString() != "PATH") {
    return Status::SemanticError("Illegal yield clauses `%s'. only support yield path",
                                 col->toString().c_str());
  }
  outputs_.emplace_back(col->name(), Value::Type::PATH);
  pathCtx_->colNames = getOutColNames();
  return Status::OK();
}

}  // namespace graph
}  // namespace nebula
