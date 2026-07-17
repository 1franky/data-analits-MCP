"""Fail-closed allowlist of read-only MongoDB pipeline stages and operators."""


class MongoOperatorPolicy:
    """Allowlist-based policy: only explicitly recognized names are permitted."""

    _ALLOWED_PIPELINE_STAGES = frozenset(
        {
            "$match",
            "$project",
            "$group",
            "$sort",
            "$limit",
            "$skip",
            "$unwind",
            "$lookup",
            "$addFields",
            "$set",
            "$count",
            "$facet",
            "$bucket",
            "$bucketAuto",
            "$sample",
            "$replaceRoot",
            "$replaceWith",
            "$sortByCount",
            "$unset",
            "$geoNear",
        }
    )

    _ALLOWED_OPERATORS = frozenset(
        {
            "$eq",
            "$ne",
            "$gt",
            "$gte",
            "$lt",
            "$lte",
            "$in",
            "$nin",
            "$and",
            "$or",
            "$nor",
            "$not",
            "$exists",
            "$type",
            "$regex",
            "$options",
            "$mod",
            "$all",
            "$elemMatch",
            "$size",
            "$expr",
            "$text",
            "$search",
            "$sum",
            "$avg",
            "$min",
            "$max",
            "$first",
            "$last",
            "$push",
            "$addToSet",
            "$cond",
            "$ifNull",
            "$switch",
            "$concat",
            "$substr",
            "$toUpper",
            "$toLower",
            "$dateToString",
            "$year",
            "$month",
            "$dayOfMonth",
            "$multiply",
            "$divide",
            "$add",
            "$subtract",
        }
    )

    _EXPLICITLY_BLOCKED = frozenset(
        {
            "$out",
            "$merge",
            "$function",
            "$accumulator",
            "$where",
            "$currentOp",
            "$collStats",
            "$indexStats",
            "$planCacheStats",
            "$eval",
        }
    )

    @classmethod
    def stage_is_allowed(cls, stage_name: str) -> bool:
        """Return whether a top-level pipeline stage name is on the allowlist."""
        return stage_name in cls._ALLOWED_PIPELINE_STAGES

    @classmethod
    def stage_is_explicitly_blocked(cls, stage_name: str) -> bool:
        """Return whether a stage name has a specific, named denial reason."""
        return stage_name in cls._EXPLICITLY_BLOCKED

    @classmethod
    def operator_is_allowed(cls, operator_name: str) -> bool:
        """Return whether a nested '$'-prefixed operator key is on the allowlist."""
        return operator_name in cls._ALLOWED_OPERATORS

    @classmethod
    def operator_is_explicitly_blocked(cls, operator_name: str) -> bool:
        """Return whether an operator name has a specific, named denial reason."""
        return operator_name in cls._EXPLICITLY_BLOCKED
