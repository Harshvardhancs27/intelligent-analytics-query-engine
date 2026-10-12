"""
Structured Semantic Intermediate Representation (QueryPlan) for natural language analytics.
Decouples intent parsing from code generation (Pandas / SQL).
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


class IntentType(str, Enum):
    AGGREGATION = "AGGREGATION"
    GROUP_TOP_N = "GROUP_TOP_N"
    GROUP_AGGREGATION = "GROUP_AGGREGATION"
    TARGET_COMPARISON = "TARGET_COMPARISON"
    CONTRIBUTION_PERCENTAGE = "CONTRIBUTION_PERCENTAGE"
    WINDOW_PARTITION_RANK = "WINDOW_PARTITION_RANK"
    TIME_SERIES_GROWTH = "TIME_SERIES_GROWTH"
    NESTED_GROUP_RANK_AGG = "NESTED_GROUP_RANK_AGG"
    RAW_SCAN = "RAW_SCAN"


@dataclass
class FilterCondition:
    column: str
    operator: str  # '==', '!=', '>', '<', 'in', 'startswith'
    value: Any

    def to_dict(self) -> Dict[str, Any]:
        return {"column": self.column, "operator": self.operator, "value": self.value}


@dataclass
class QueryPlan:
    """Semantic Abstract Syntax Tree representing the user's analytical question."""
    raw_query: str
    intent_type: IntentType
    metrics: List[str] = field(default_factory=list)
    dimensions: List[str] = field(default_factory=list)
    filters: List[FilterCondition] = field(default_factory=list)
    agg_funcs: List[str] = field(default_factory=list)  # 'sum', 'mean', 'count'
    order_by: Optional[str] = None
    order_desc: bool = True
    limit: Optional[int] = None
    partition_by: Optional[str] = None
    time_filter: Optional[Dict[str, str]] = None
    comparison_target: Optional[str] = None  # e.g., 'target_revenue'
    comparison_operator: Optional[str] = None  # '<' for missed, '>=' for achieved
    nested_spec: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
