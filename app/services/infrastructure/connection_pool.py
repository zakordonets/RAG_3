#!/usr/bin/env python3
"""
Connection pooling for improved crawler performance
"""

from __future__ import annotations

import time
from typing import Optional, Dict, Any
from threading import Lock
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from loguru import logger

from app.config import CONFIG


class ConnectionPool:
    """Thread-safe connection pool for HTTP requests"""

    def __init__(self, max_connections: int = 10, max_retries: int = 3):
        self.max_connections = max_connections
        self.max_retries = max_retries
        self._sessions: Dict[str, requests.Session] = {}
        self._session_creation_time: Dict[str, float] = {}
        self._lock = Lock()
        self._session_timeout = 300  # 5 minutes

    def get_session(self, base_url: str) -> requests.Session:
        """Get or create a session for the given base URL"""
        with self._lock:
            current_time = time.time()

            # Clean up old sessions
            self._cleanup_old_sessions(current_time)

            # Check if we have a valid session
            if base_url in self._sessions:
                return self._sessions[base_url]

            # Create new session if we don't exceed max connections
            if len(self._sessions) < self.max_connections:
                session = self._create_session()
                self._sessions[base_url] = session
                self._session_creation_time[base_url] = current_time
                logger.debug(f"Created new session for {base_url}")
                return session

            # Reuse oldest session if we're at capacity
            oldest_url = min(
                self._sessions.keys(),
                key=lambda url: self._session_creation_time.get(url, 0)
            )

            logger.debug(f"Reusing session from {oldest_url} for {base_url}")
            session = self._sessions.pop(oldest_url)
            self._session_creation_time.pop(oldest_url)

            self._sessions[base_url] = session
            self._session_creation_time[base_url] = current_time

            return session

    def _create_session(self) -> requests.Session:
        """Create a new HTTP session with optimized settings"""
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            backoff_factor=CONFIG.crawler_backoff_factor
        )

        # Configure adapter with connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=5,
            pool_maxsize=10,
            pool_block=False
        )

        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set headers
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

        # Set timeout
        session.timeout = (10, CONFIG.crawl_timeout_s)

        return session

    def _cleanup_old_sessions(self, current_time: float) -> None:
        """Clean up sessions that are older than timeout"""
        expired_urls = [
            url for url, creation_time in self._session_creation_time.items()
            if current_time - creation_time > self._session_timeout
        ]

        for url in expired_urls:
            if url in self._sessions:
                self._sessions[url].close()
                del self._sessions[url]
                del self._session_creation_time[url]
                logger.debug(f"Cleaned up expired session for {url}")

    def close_all(self) -> None:
        """Close all sessions"""
        with self._lock:
            for session in self._sessions.values():
                session.close()
            self._sessions.clear()
            self._session_creation_time.clear()
            logger.info("Closed all connection pool sessions")

    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        with self._lock:
            current_time = time.time()
            session_ages = [
                current_time - creation_time
                for creation_time in self._session_creation_time.values()
            ]

            return {
                "active_sessions": len(self._sessions),
                "max_sessions": self.max_connections,
                "session_timeout": self._session_timeout,
                "average_session_age": sum(session_ages) / len(session_ages) if session_ages else 0,
                "oldest_session_age": max(session_ages) if session_ages else 0
            }


# Global connection pool instance
_connection_pool: Optional[ConnectionPool] = None


def get_connection_pool() -> ConnectionPool:
    """Get global connection pool instance"""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = ConnectionPool(
            max_connections=CONFIG.crawl_concurrency,
            max_retries=CONFIG.crawler_max_retries
        )
    return _connection_pool


def close_connection_pool() -> None:
    """Close global connection pool"""
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.close_all()
        _connection_pool = None
