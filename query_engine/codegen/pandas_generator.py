"""
Pandas Code Generator: Translates QueryPlan into executable, secure Python/Pandas code.
"""
from typing import List, Dict, Any, Optional
from query_engine.nlp.intent_model import QueryPlan, IntentType, FilterCondition


class PandasGenerator:
    """Generates idiomatic, self-contained Pandas expressions for analytical queries."""

    @staticmethod
    def _build_filter_expression(filters: List[FilterCondition], time_filter: Optional[Dict[str, str]]) -> str:
        conditions = []
        for f in filters:
            if isinstance(f.value, str):
                conditions.append(f"(df['{f.column}'] == '{f.value}')")
            else:
                conditions.append(f"(df['{f.column}'] == {f.value})")

        if time_filter:
            if "month" in time_filter:
                conditions.append(f"(df['month'] == '{time_filter['month']}')")
            elif "year" in time_filter:
                conditions.append(f"(df['year'] == '{time_filter['year']}')")

        if not conditions:
            return ""
        return " & ".join(conditions)

    def generate(self, plan: QueryPlan) -> str:
        """Converts a QueryPlan into an executable Pandas code block."""
        filter_expr = self._build_filter_expression(plan.filters, plan.time_filter)
        df_source = f"df[{filter_expr}]" if filter_expr else "df"
        metric = plan.metrics[0] if plan.metrics else "revenue"

        # 1. Single Aggregation
        if plan.intent_type == IntentType.AGGREGATION:
            agg_func = plan.agg_funcs[0] if plan.agg_funcs else "sum"
            if agg_func == "mean":
                return f"{df_source}['{metric}'].mean()"
            elif agg_func == "count":
                return f"{df_source}['order_id'].nunique()"
            return f"{df_source}['{metric}'].sum()"

        # 2. Group Top N
        if plan.intent_type == IntentType.GROUP_TOP_N:
            dims = plan.dimensions
            dim_str = f"'{dims[0]}'" if len(dims) == 1 else str(dims)
            limit = plan.limit or 5
            ascending_flag = not plan.order_desc
            return (
                f"{df_source}.groupby({dim_str})['{metric}']"
                f".sum().reset_index()"
                f".sort_values(by='{metric}', ascending={ascending_flag})"
                f".head({limit})"
            )

        # 3. Group Aggregation
        if plan.intent_type == IntentType.GROUP_AGGREGATION:
            dim_str = f"'{plan.dimensions[0]}'" if len(plan.dimensions) == 1 else str(plan.dimensions)
            if metric == "avg_order_value":
                return (
                    f"({df_source}.groupby({dim_str})['revenue'].sum() / "
                    f"{df_source}.groupby({dim_str})['order_id'].nunique())"
                    f".reset_index(name='avg_order_value')"
                )
            agg = plan.agg_funcs[0] if plan.agg_funcs else "sum"
            return f"{df_source}.groupby({dim_str})['{metric}'].{agg}().reset_index()"

        # 4. Target Comparison
        if plan.intent_type == IntentType.TARGET_COMPARISON:
            month_val = plan.time_filter.get("month", "2024-02") if plan.time_filter else "2024-02"
            op = plan.comparison_operator or "<"
            return (
                f"sales_m = df[df['month'] == '{month_val}'].groupby('region')['revenue'].sum().reset_index()\n"
                f"targets_m = targets[targets['month'] == '{month_val}']\n"
                f"merged = pd.merge(targets_m, sales_m, on='region', how='left').fillna({{'revenue': 0}})\n"
                f"merged[merged['revenue'] {op} merged['target_revenue']][['region', 'revenue', 'target_revenue']]"
            )

        # 5. Contribution Percentage
        if plan.intent_type == IntentType.CONTRIBUTION_PERCENTAGE:
            dim = plan.dimensions[0] if plan.dimensions else "product_category"
            return (
                f"cat_sales = {df_source}.groupby('{dim}')['{metric}'].sum().reset_index()\n"
                f"cat_sales['contribution_pct'] = (cat_sales['{metric}'] / {df_source}['{metric}'].sum()) * 100\n"
                f"cat_sales.sort_values(by='contribution_pct', ascending=False)"
            )

        # 6. Window Partition Rank
        if plan.intent_type == IntentType.WINDOW_PARTITION_RANK:
            part_col = plan.partition_by or "region"
            rank_col = [d for d in plan.dimensions if d != part_col][0] if len(plan.dimensions) > 1 else "product_name"
            lim = plan.limit or 1
            return (
                f"prod_agg = df.groupby(['{part_col}', '{rank_col}'])['{metric}'].sum().reset_index()\n"
                f"prod_agg['rank'] = prod_agg.groupby('{part_col}')['{metric}'].rank(method='first', ascending=False)\n"
                f"prod_agg[prod_agg['rank'] <= {lim}][['{part_col}', '{rank_col}', '{metric}']]"
            )

        # 7. Time Series YoY Growth
        if plan.intent_type == IntentType.TIME_SERIES_GROWTH:
            return (
                f"yearly_rev = df.groupby('year')['{metric}'].sum()\n"
                f"yearly_rev.pct_change()"
            )

        # 8. Nested Group Rank Aggregation
        if plan.intent_type == IntentType.NESTED_GROUP_RANK_AGG:
            spec = plan.nested_spec or {}
            inner_dim = spec.get("inner_dimension", "customer_id")
            outer_dim = spec.get("outer_dimension", "region")
            rank_lim = spec.get("inner_rank_limit", 3)
            return (
                f"cust_agg = df.groupby(['{outer_dim}', '{inner_dim}'])['{metric}'].sum().reset_index()\n"
                f"cust_agg['rank'] = cust_agg.groupby('{outer_dim}')['{metric}'].rank(method='first', ascending=False)\n"
                f"top_n = cust_agg[cust_agg['rank'] <= {rank_lim}]\n"
                f"top_n.groupby('{outer_dim}')['{metric}'].sum().reset_index()"
            )

        return f"{df_source}.head(10)"
