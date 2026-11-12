"""Dependency injection factories for FastAPI endpoints.

Provides factory functions for services using FastAPI's Depends pattern.
When DATABASE_URL is set, uses Postgres (Neon) for storage.
Otherwise falls back to local file-based storage.
"""

import os

from fastapi import Depends

from app.services.analytics_engine import AnalyticsEngine
from app.services.chart_generator import ChartGenerator
from app.services.chat_service import ChatService
from app.services.csv_parser import CSVParser
from app.services.llm_service import LLMService
from app.services.preview_engine import PreviewEngine
from app.services.prompt_builder import PromptBuilder
from app.services.query_executor import QueryExecutor
from app.services.rest_importer import RESTImporter
from app.services.sql_engine import SQLEngine

# Determine storage mode
DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_POSTGRES = bool(DATABASE_URL)

# Local storage paths (fallback when no DATABASE_URL)
DATASET_STORAGE_PATH = os.environ.get("DATASET_STORAGE_PATH", "/data/datasets")
CHAT_HISTORY_STORAGE_PATH = os.environ.get("CHAT_HISTORY_STORAGE_PATH", "/data/chat_history")

# Singleton service instances (created once, reused across requests)
_dataset_service = None
_chat_history = None


def get_dataset_service():
    """Factory function for DatasetService (singleton)."""
    global _dataset_service
    if _dataset_service is None:
        if USE_POSTGRES:
            from app.services.dataset_service_pg import DatasetServicePG
            _dataset_service = DatasetServicePG()
        else:
            from app.services.dataset_service import DatasetService
            _dataset_service = DatasetService(storage_path=DATASET_STORAGE_PATH)
    return _dataset_service


def get_csv_parser() -> CSVParser:
    """Factory function for CSVParser."""
    return CSVParser()


def get_rest_importer() -> RESTImporter:
    """Factory function for RESTImporter."""
    return RESTImporter()


def get_preview_engine(
    dataset_service=Depends(get_dataset_service),
) -> PreviewEngine:
    """Factory function for PreviewEngine."""
    return PreviewEngine(dataset_service)


def get_analytics_engine() -> AnalyticsEngine:
    """Factory function for AnalyticsEngine."""
    return AnalyticsEngine()


def get_sql_engine() -> SQLEngine:
    """Factory function for SQLEngine."""
    return SQLEngine()


def get_chart_generator(
    analytics_engine: AnalyticsEngine = Depends(get_analytics_engine),
) -> ChartGenerator:
    """Factory function for ChartGenerator."""
    return ChartGenerator(analytics_engine)


def get_chat_history():
    """Factory function for ChatHistory (singleton)."""
    global _chat_history
    if _chat_history is None:
        if USE_POSTGRES:
            from app.services.chat_history_pg import ChatHistoryPG
            _chat_history = ChatHistoryPG()
        else:
            from app.services.chat_history import ChatHistory
            _chat_history = ChatHistory(storage_path=CHAT_HISTORY_STORAGE_PATH)
    return _chat_history


def get_chat_service(
    dataset_service=Depends(get_dataset_service),
) -> ChatService:
    """Factory function for ChatService."""
    prompt_builder = PromptBuilder()
    llm_service = LLMService()
    query_executor = QueryExecutor()
    chat_history = get_chat_history()

    return ChatService(
        dataset_service=dataset_service,
        prompt_builder=prompt_builder,
        llm_service=llm_service,
        query_executor=query_executor,
        chat_history=chat_history,
    )
