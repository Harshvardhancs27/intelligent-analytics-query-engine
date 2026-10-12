"""
SQL Code Generator: Translates QueryPlan into ANSI / SQLite-compatible SQL queries with CTEs & Window Functions.
"""
from typing import List, Dict, Any, Optional
from query_engine.nlp.intent_model import QueryPlan, IntentType, FilterCondition


class SQLGenerator:
    """Generates standard SQL expressions with CTEs, window ranking, and left joins."""

    @staticmethod
    def _build_where_clause(filters: List[FilterCondition], time_filter: Optional[Dict[str, str]]) -> str:
        clauses = []
        for f in filters:
            if isinstance(f.value, str):
                clauses.append(f"{f.column} = '{f.value}'")
            else:
                clauses.append(f"{f.column} = {f.value}")

        if time_filter:
            if "month" in time_filter:
                clauses.append(f"strftime('%Y-%m', order_date) = '{time_filter['month']}'")
            elif "year" in time_filter:
                clauses.append(f"strftime('%Y', order_date) = '{time_filter['year']}'")

        if not clauses:
            return ""
        return "WHERE " + " AND ".join(clauses)

    def generate(self, plan: QueryPlan) -> str:
        """Converts a QueryPlan into an executable SQL string."""
        where_clause = self._build_where_clause(plan.filters, plan.time_filter)
        metric = plan.metrics[0] if plan.metrics else "revenue"

        # 1. Single Aggregation
        if plan.intent_type == IntentType.AGGREGATION:
            agg_func = plan.agg_funcs[0] if plan.agg_funcs else "sum"
            sql_func = "AVG" if agg_func == "mean" else ("COUNT(DISTINCT order_id)" if agg_func == "count" else f"SUM({metric})")
            return f"SELECT {sql_func} AS result FROM sales_data {where_clause}".strip()

        # 2. Group Top N
        if plan.intent_type == IntentType.GROUP_TOP_N:
            dims = ", ".join(plan.dimensions)
            limit = plan.limit or 5
            direction = "DESC" if plan.order_desc else "ASC"
            return (
                f"SELECT {dims}, SUM({metric}) AS {metric} "
                f"FROM sales_data {where_clause} "
                f"GROUP BY {dims} "
                f"ORDER BY {metric} {direction} "
                f"LIMIT {limit}"
            ).strip()

        # 3. Group Aggregation
        if plan.intent_type == IntentType.GROUP_AGGREGATION:
            dims = ", ".join(plan.dimensions)
            if metric == "avg_order_value":
                return (
                    f"SELECT {dims}, (SUM(revenue) * 1.0 / COUNT(DISTINCT order_id)) AS avg_order_value "
                    f"FROM sales_data {where_clause} "
                    f"GROUP BY {dims}"
                ).strip()
            agg = "AVG" if (plan.agg_funcs and plan.agg_funcs[0] == "mean") else f"SUM({metric})"
            return f"SELECT {dims}, {agg} AS {metric} FROM sales_data {where_clause} GROUP BY {dims}".strip()

        # 4. Target Comparison
        if plan.intent_type == IntentType.TARGET_COMPARISON:
            month_val = plan.time_filter.get("month", "2024-02") if plan.time_filter else "2024-02"
            op = plan.comparison_operator or "<"
            return (
                f"SELECT t.region, t.target_revenue, COALESCE(s.actual_revenue, 0) AS revenue\n"
                f"FROM targets t\n"
                f"LEFT JOIN (\n"
                f"    SELECT region, SUM(revenue) AS actual_revenue\n"
                f"    FROM sales_data\n"
                f"    WHERE strftime('%Y-%m', order_date) = '{month_val}'\n"
                f"    GROUP BY region\n"
                f") s ON t.region = s.region\n"
                f"WHERE t.month = '{month_val}' AND COALESCE(s.actual_revenue, 0) {op} t.target_revenue"
            )

        # 5. Contribution Percentage
        if plan.intent_type == IntentType.CONTRIBUTION_PERCENTAGE:
            dim = plan.dimensions[0] if plan.dimensions else "product_category"
            return (
                f"SELECT \n"
                f"    {dim},\n"
                f"    SUM({metric}) AS revenue,\n"
                f"    (SUM({metric}) * 100.0 / (SELECT SUM({metric}) FROM sales_data)) AS contribution_pct\n"
                f"FROM sales_data {where_clause}\n"
                f"GROUP BY {dim}\n"
                f"ORDER BY contribution_pct DESC"
            ).strip()

        # 6. Window Partition Rank
        if plan.intent_type == IntentType.WINDOW_PARTITION_RANK:
            part_col = plan.partition_by or "region"
            rank_col = [d for d in plan.dimensions if d != part_col][0] if len(plan.dimensions) > 1 else "product_name"
            lim = plan.limit or 1
            return (
                f"WITH ranked_products AS (\n"
                f"    SELECT \n"
                f"        {part_col},\n"
                f"        {rank_col},\n"
                f"        SUM({metric}) AS {metric},\n"
                f"        ROW_NUMBER() OVER (PARTITION BY {part_col} ORDER BY SUM({metric}) DESC) AS rank\n"
                f"    FROM sales_data\n"
                f"    GROUP BY {part_col}, {rank_col}\n"
                f")\n"
                f"SELECT {part_col}, {rank_col}, {metric}\n"
                f"FROM ranked_products\n"
                f"WHERE rank <= {lim}\n"
                f"ORDER BY {part_col}"
            )

        # 7. Time Series YoY Growth
        if plan.intent_type == IntentType.TIME_SERIES_GROWTH:
            return (
                f"WITH yearly AS (\n"
                f"    SELECT strftime('%Y', order_date) AS year, SUM({metric}) AS total_revenue\n"
                f"    FROM sales_data\n"
                f"    GROUP BY strftime('%Y', order_date)\n"
                f")\n"
                f"SELECT \n"
                f"    year,\n"
                f"    total_revenue,\n"
                f"    LAG(total_revenue) OVER (ORDER BY year) AS prev_year_revenue,\n"
                f"    ((total_revenue - LAG(total_revenue) OVER (ORDER BY year)) * 1.0 / NULLIF(LAG(total_revenue) OVER (ORDER BY year), 0)) * 100.0 AS yoy_growth_pct\n"
                f"FROM yearly"
            )

        # 8. Nested Group Rank Aggregation
        if plan.intent_type == IntentType.NESTED_GROUP_RANK_AGG:
            spec = plan.nested_spec or {}
            inner_dim = spec.get("inner_dimension", "customer_id")
            outer_dim = spec.get("outer_dimension", "region")
            rank_lim = spec.get("inner_rank_limit", 3)
            return (
                f"WITH customer_ranks AS (\n"
                f"    SELECT \n"
                f"        {outer_dim},\n"
                f"        {inner_dim},\n"
                f"        SUM({metric}) AS customer_revenue,\n"
                f"        ROW_NUMBER() OVER (PARTITION BY {outer_dim} ORDER BY SUM({metric}) DESC) AS rank\n"
                f"    FROM sales_data\n"
                f"    GROUP BY {outer_dim}, {inner_dim}\n"
                f"),\n"
                f"top_n AS (\n"
                f"    SELECT {outer_dim}, {inner_dim}, customer_revenue\n"
                f"    FROM customer_ranks\n"
                f"    WHERE rank <= {rank_lim}\n"
                f")\n"
                f"SELECT {outer_dim}, SUM(customer_revenue) AS revenue\n"
                f"FROM top_n\n"
                f"GROUP BY {outer_dim}"
            )

        return f"SELECT * FROM sales_data LIMIT 10"
