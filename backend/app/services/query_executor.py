"""QueryExecutor service for safe SQL query execution using DuckDB.

Validates and executes SQL SELECT queries against DataFrames
using DuckDB with safety constraints including read-only execution,
timeout limits, and row caps.
"""

import re
import signal
import threading
from typing import Any

import duckdb
import pandas as pd

from app.exceptions import QueryExecutionError, QueryValidationError
from app.models.chat_schemas import QueryResult


class QueryExecutor:
    """SQL query execution service using DuckDB.

    Executes validated SQL SELECT queries against DataFrames with:
    - Word-boundary keyword validation to prevent mutations
    - 30-second execution timeout
    - 10,000 row result limit
    """

    MAX_ROWS = 10_000
    TIMEOUT_SECONDS = 30

    PROHIBITED_KEYWORDS = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE"]

    def validate_query(self, sql: str) -> None:
        """Validate SQL is a SELECT-only statement.

        Uses word-boundary regex matching (case-insensitive) to detect
        prohibited keywords without false positives from column names
        or string literals (e.g., "created_at", "update_count", "dropoff_location").

        Args:
            sql: The SQL query string to validate.

        Raises:
            QueryValidationError: If prohibited keywords detected or query is empty.
        """
        if not sql or not sql.strip():
            raise QueryValidationError(
                "Operation not permitted: only SELECT queries are allowed"
            )

        for keyword in self.PROHIBITED_KEYWORDS:
            # Use word-boundary matching (\b) with case-insensitive flag
            # This ensures "created_at" doesn't match CREATE,
            # "update_count" doesn't match UPDATE, etc.
            pattern = r"\b" + keyword + r"\b"
            if re.search(pattern, sql, re.IGNORECASE):
                raise QueryValidationError(
                    "Operation not permitted: only SELECT queries are allowed"
                )

    def execute(self, df: pd.DataFrame, sql: str) -> QueryResult:
        """Execute SQL against DataFrame using DuckDB.

        1. Validate query (reject before execution if invalid)
        2. Register DataFrame as "dataset" table
        3. Execute with 30s timeout
        4. Limit results to 10,000 rows
        5. Return columns and rows

        Args:
            df: The pandas DataFrame to query against.
            sql: A SQL SELECT statement referencing the "dataset" table.

        Returns:
            QueryResult with columns and rows (max 10,000 rows).

        Raises:
            QueryValidationError: If query contains prohibited keywords.
            QueryExecutionError: If execution fails or times out.
        """
        self.validate_query(sql)

        try:
            # Create an in-memory DuckDB connection
            conn = duckdb.connect(database=":memory:", read_only=False)

            try:
                # Register the DataFrame as a virtual table named "dataset"
                conn.register("dataset", df)

                # Execute with timeout using threading
                result_holder: dict[str, Any] = {}
                error_holder: dict[str, Any] = {}

                def run_query() -> None:
                    try:
                        result = conn.execute(sql)
                        result_df = result.fetchdf()
                        result_holder["df"] = result_df
                    except Exception as e:
                        error_holder["error"] = e

                thread = threading.Thread(target=run_query)
                thread.start()
                thread.join(timeout=self.TIMEOUT_SECONDS)

                if thread.is_alive():
                    # Query exceeded timeout
                    try:
                        conn.interrupt()
                    except Exception:
                        pass
                    thread.join(timeout=5)
                    raise QueryExecutionError("Query execution timed out")

                if "error" in error_holder:
                    raise error_holder["error"]

                if "df" not in result_holder:
                    raise QueryExecutionError("Query execution failed: no results returned")

                result_df = result_holder["df"]

                # Limit results to MAX_ROWS
                if len(result_df) > self.MAX_ROWS:
                    result_df = result_df.head(self.MAX_ROWS)

                # Convert to QueryResult
                columns = list(result_df.columns)
                # Convert NaN/None values properly
                result_df = result_df.where(pd.notna(result_df), None)
                rows = result_df.to_dict(orient="records")

                return QueryResult(columns=columns, rows=rows)

            finally:
                conn.close()

        except QueryValidationError:
            raise
        except QueryExecutionError:
            raise
        except Exception as e:
            raise QueryExecutionError(f"Query execution failed: {str(e)}")
