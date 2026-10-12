"""
Entity extraction, tokenization, and linguistic normalization for natural language queries.
"""
import re
from typing import Dict, List, Optional, Tuple, Any, Set
from query_engine.schema_catalog import SchemaCatalog
from query_engine.nlp.intent_model import FilterCondition


class EntityExtractor:
    """Extracts business metrics, dimensions, geographic filters, numbers, and temporal filters."""

    def __init__(self, schema_catalog: SchemaCatalog):
        self.catalog = schema_catalog

        # Known values from domain for exact matching
        self.known_countries = {"India", "Germany", "USA", "UK", "France", "United States"}
        self.known_cities = {
            "Mumbai", "Berlin", "Delhi", "New York", "London",
            "Bangalore", "Chicago", "Paris", "San Francisco"
        }
        self.known_regions = {"APAC", "EMEA", "NA"}
        self.known_categories = {"Furniture", "Technology", "Office Supplies"}

        self.month_map = {
            "jan": "2024-01", "january": "2024-01",
            "feb": "2024-02", "february": "2024-02",
            "mar": "2024-03", "march": "2024-03",
            "apr": "2024-04", "april": "2024-04",
            "may": "2024-05",
            "jun": "2024-06", "june": "2024-06",
            "jul": "2024-07", "july": "2024-07",
            "aug": "2024-08", "august": "2024-08",
            "sep": "2024-09", "september": "2024-09",
            "oct": "2024-10", "october": "2024-10",
            "nov": "2024-11", "november": "2024-11",
            "dec": "2024-12", "december": "2024-12"
        }

    def extract_time_filters(self, query: str) -> Optional[Dict[str, str]]:
        """Extracts month or year constraints from query text."""
        lower = query.lower()
        # Direct YYYY-MM
        m_regex = re.search(r"\b(20\d{2})-(0[1-9]|1[0-2])\b", lower)
        if m_regex:
            return {"month": m_regex.group(0)}

        # Month names
        for m_name, yyyy_mm in self.month_map.items():
            pattern = rf"\b{m_name}\b"
            if re.search(pattern, lower):
                return {"month": yyyy_mm}

        # Year
        y_regex = re.search(r"\b(202[0-9])\b", lower)
        if y_regex:
            return {"year": y_regex.group(0)}

        return None

    def extract_filters(self, query: str) -> List[FilterCondition]:
        """Extracts dimension filters from explicit values mentioned in text."""
        filters = []
        lower = query.lower()

        # Country
        for country in self.known_countries:
            if re.search(rf"\b{re.escape(country.lower())}\b", lower):
                canonical_country = "USA" if country.lower() == "united states" else country
                filters.append(FilterCondition(column="country", operator="==", value=canonical_country))
                break

        # City
        for city in self.known_cities:
            if re.search(rf"\b{re.escape(city.lower())}\b", lower):
                filters.append(FilterCondition(column="city", operator="==", value=city))
                break

        # Region
        for region in self.known_regions:
            # Avoid matching 'in' inside words or common substrings
            pattern = rf"\b{re.escape(region.lower())}\b"
            if re.search(pattern, lower):
                filters.append(FilterCondition(column="region", operator="==", value=region))
                break

        # Product Category
        for cat in self.known_categories:
            if re.search(rf"\b{re.escape(cat.lower())}\b", lower):
                filters.append(FilterCondition(column="product_category", operator="==", value=cat))
                break

        return filters

    def extract_limit(self, query: str) -> Optional[int]:
        """Extracts Top N or Limit numbers (e.g. 'top 2', 'first 5')."""
        match = re.search(r"\b(?:top|first|best|highest|lowest)\s+(\d+)\b", query, re.IGNORECASE)
        if match:
            return int(match.group(1))
        if re.search(r"\b(?:top|highest|best|leading)\b", query, re.IGNORECASE):
            return 1
        return None

    def extract_metrics(self, query: str) -> List[str]:
        """Identifies metrics referenced in the query."""
        metrics = []
        lower = query.lower()

        # Check multi-word metrics first
        if "average order value" in lower or "avg order value" in lower or "aov" in lower:
            metrics.append("avg_order_value")
        elif "sales" in lower or "revenue" in lower or "turnover" in lower:
            metrics.append("revenue")
        
        if "profit" in lower or "earnings" in lower or "margin" in lower:
            metrics.append("profit")

        if "order" in lower and "avg_order_value" not in metrics and "order_id" not in metrics:
            if re.search(r"\borders\b|\border count\b|\bnumber of orders\b", lower):
                metrics.append("orders")

        if "discount" in lower:
            metrics.append("discount")
        if "quantity" in lower or "units" in lower:
            metrics.append("quantity")

        # Default fallback metric if query asks about business performance
        if not metrics:
            if "target" in lower or "grow" in lower or "rank" in lower or "top" in lower or "contribution" in lower:
                metrics.append("revenue")

        return metrics

    def extract_dimensions(self, query: str) -> List[str]:
        """Extracts dimensions intended for grouping or partitioning."""
        dimensions = []
        lower = query.lower()

        if re.search(r"\bby city\b|\bcities\b|\bcity\b", lower):
            dimensions.append("city")
        if re.search(r"\bby region\b|\bregions\b|\bregion\b|\bin each region\b|\bper region\b", lower):
            dimensions.append("region")
        if re.search(r"\bby category\b|\bcategories\b|\bproduct_category\b|\bproduct category\b", lower):
            dimensions.append("product_category")
        if re.search(r"\bby product\b|\bproducts\b|\bproduct\b|\btop product\b", lower):
            dimensions.append("product_name")
        if re.search(r"\bby customer\b|\bcustomers\b|\bcustomer\b", lower):
            dimensions.append("customer_id")
        if re.search(r"\bby segment\b|\bsegments\b|\bcustomer segment\b", lower):
            dimensions.append("customer_segment")
        if re.search(r"\bby country\b|\bcountries\b|\bcountry\b", lower):
            dimensions.append("country")

        return dimensions
