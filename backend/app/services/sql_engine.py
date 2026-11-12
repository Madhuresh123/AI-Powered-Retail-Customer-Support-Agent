"""SQLEngine service for SQL query execution.

Parses and executes SQL SELECT queries against a DataFrame
using DuckDB.
"""

import re

import duckdb
import numpy as np
import pandas as pd

from app.exceptions import AnalyticsValidationError
from app.models.analytics_schemas import SQLResponse


class SQLEngine:
    """SQL query execution service.

    Validates and executes SQL SELECT queries against DataFrames,
    returning columns and rows limited to 10,000 results.
    """

    def validate_query(self, query: str) -> None:
        """Validate SQL query safety and constraints.

        Checks:
        - Non-empty, 1-4096 characters
        - Single SELECT statement only (no INSERT/UPDATE/DELETE/DROP)
        - No subqueries, JOINs, UNIONs, or window functions

        Raises:
            AnalyticsValidationError: If the query fails validation.
        """
        # Length check
        if not query or len(query) > 4096:
            raise AnalyticsValidationError(
                "Query must be between 1 and 4096 characters"
            )

        stripped = query.strip()

        if not stripped:
            raise AnalyticsValidationError(
                "Query must be between 1 and 4096 characters"
            )

        # Check for multiple statements (split by semicolons)
        statements = [s.strip() for s in stripped.split(";") if s.strip()]
        if len(statements) > 1:
            raise AnalyticsValidationError(
                "Only a single SELECT statement is permitted"
            )

        upper = stripped.upper()

        # Must start with SELECT
        if not upper.startswith("SELECT"):
            raise AnalyticsValidationError(
                "Only a single SELECT statement is permitted"
            )

        # Reject INSERT, UPDATE, DELETE, DROP keywords
        forbidden_keywords = ["INSERT", "UPDATE", "DELETE", "DROP"]
        for keyword in forbidden_keywords:
            if re.search(r"\b" + keyword + r"\b", upper):
                raise AnalyticsValidationError(
                    "Only a single SELECT statement is permitted"
                )

        # Reject JOINs
        if re.search(r"\bJOIN\b", upper):
            raise AnalyticsValidationError("Unsupported SQL feature: JOIN")

        # Reject UNION (check before subqueries since UNION naturally has multiple SELECTs)
        if re.search(r"\bUNION\b", upper):
            raise AnalyticsValidationError("Unsupported SQL feature: UNION")

        # Reject subqueries: nested SELECT (SELECT after the first one)
        # Look for SELECT that appears after the initial SELECT keyword
        select_occurrences = [m.start() for m in re.finditer(r"\bSELECT\b", upper)]
        if len(select_occurrences) > 1:
            raise AnalyticsValidationError(
                "Unsupported SQL feature: subqueries"
            )

        # Reject window functions: OVER( or OVER (
        if re.search(r"\bOVER\s*\(", upper):
            raise AnalyticsValidationError(
                "Unsupported SQL feature: window functions"
            )

    def execute(self, df: pd.DataFrame, query: str) -> SQLResponse:
        """Execute a SQL SELECT query against the DataFrame.

        Args:
            df: The DataFrame to query against.
            query: A SQL SELECT statement. The table name must be "dataset".

        Returns:
            SQLResponse with columns and rows (max 10,000 rows).

        Raises:
            AnalyticsValidationError: If the query is invalid or execution fails.
        """
        self.validate_query(query)

        try:
            conn = duckdb.connect(":memory:")
            conn.register("dataset", df)
            result = conn.execute(query).fetchdf()
            conn.close()
        except Exception as e:
            error_msg = str(e)
            if "does not exist" in error_msg.lower() or "not found" in error_msg.lower():
                raise AnalyticsValidationError(
                    f"Unknown column referenced in query: {error_msg}"
                )
            elif "syntax error" in error_msg.lower() or "parser" in error_msg.lower():
                raise AnalyticsValidationError(
                    f"SQL syntax error: {error_msg}"
                )
            else:
                raise AnalyticsValidationError(
                    f"SQL execution error: {error_msg}"
                )

        # Limit results to 10,000 rows
        result = result.head(10000)

        # Convert to response format
        columns = list(result.columns)

        # Handle NaN → None conversion
        result = result.where(pd.notna(result), None)
        # Also replace numpy NaN values explicitly
        result = result.replace({np.nan: None})

        rows = result.to_dict(orient="records")

        return SQLResponse(columns=columns, rows=rows)
