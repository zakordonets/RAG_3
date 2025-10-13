"""
Unified Quality Manager for RAGAS evaluation and user feedback
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger

from app.config import CONFIG
from app.models.quality_interaction import quality_db, QualityInteractionData
from app.services.quality.ragas_evaluator import ragas_evaluator
from app.infrastructure import get_metrics_collector

class UnifiedQualityManager:
    """Unified quality manager for RAGAS and user feedback"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self):
        """Initialize quality manager"""
        if self._initialized:
            return

        if CONFIG.quality_db_enabled:
            await quality_db.initialize()

        self._initialized = True
        logger.info("Quality manager initialized")

    def generate_interaction_id(self) -> str:
        """Generate unique interaction ID (exposed for orchestrator)."""
        return self._generate_interaction_id()

    def _generate_interaction_id(self) -> str:
        return f"interaction_{uuid.uuid4().hex[:8]}_{int(datetime.utcnow().timestamp())}"

    async def evaluate_interaction(
        self,
        query: str,
        response: str,
        contexts: List[str],
        sources: List[str],
        interaction_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Evaluate interaction and save to database

        Returns:
            interaction_id for later feedback updates
        """
        if not CONFIG.enable_ragas_evaluation:
            return None

        interaction_id = interaction_id or self._generate_interaction_id()

        try:
            # RAGAS evaluation
            ragas_scores = await ragas_evaluator.evaluate_interaction(
                query=query,
                response=response,
                contexts=contexts,
                sources=sources
            )

            # Calculate combined score
            combined_score = ragas_scores.get('overall_score', 0.0)

            # Create interaction data
            interaction_data = QualityInteractionData(
                interaction_id=interaction_id,
                query=query,
                response=response,
                contexts=contexts,
                sources=sources,
                ragas_faithfulness=ragas_scores.get('faithfulness'),
                ragas_context_precision=ragas_scores.get('context_precision'),
                ragas_answer_relevancy=ragas_scores.get('answer_relevancy'),
                ragas_overall_score=ragas_scores.get('overall_score'),
                combined_score=combined_score,
                created_at=datetime.utcnow()
            )

            # Save to database
            if CONFIG.quality_db_enabled:
                await quality_db.save_interaction(interaction_data)

            # Update metrics
            if CONFIG.enable_quality_metrics:
                logger.debug(f"Recording metrics for interaction {interaction_id}")
                # Record individual RAGAS metrics
                get_metrics_collector().record_ragas_score("faithfulness", ragas_scores.get('faithfulness', 0.0))
                get_metrics_collector().record_ragas_score("context_precision", ragas_scores.get('context_precision', 0.0))
                get_metrics_collector().record_ragas_score("answer_relevancy", ragas_scores.get('answer_relevancy', 0.0))
                get_metrics_collector().record_ragas_score("overall_score", ragas_scores.get('overall_score', 0.0))

                # Record combined quality score
                get_metrics_collector().record_combined_quality_score(combined_score)

                # Record quality interaction
                get_metrics_collector().record_quality_interaction("ragas_evaluation", "api", "completed")
                logger.debug(f"Metrics recorded successfully for {interaction_id}")
            else:
                logger.warning("Quality metrics are disabled in configuration")

            logger.info(f"Quality evaluation completed for {interaction_id}")
            return interaction_id

        except Exception as e:
            logger.error(f"Quality evaluation failed: {e}")
            return None

    async def add_user_feedback(
        self,
        interaction_id: str,
        feedback_type: str,  # 'positive' or 'negative'
        feedback_text: Optional[str] = None
    ) -> bool:
        """
        Add user feedback to existing interaction

        Args:
            interaction_id: ID of the interaction
            feedback_type: 'positive' or 'negative'
            feedback_text: Optional feedback text

        Returns:
            True if successful
        """
        if not CONFIG.quality_db_enabled:
            return False

        try:
            # Update interaction with feedback
            success = await quality_db.update_interaction(
                interaction_id=interaction_id,
                user_feedback_type=feedback_type,
                user_feedback_text=feedback_text
            )

            if success:
                # Update metrics
                if CONFIG.enable_quality_metrics:
                    get_metrics_collector().record_user_feedback("api", feedback_type, "user")
                    get_metrics_collector().record_quality_interaction("user_feedback", "api", feedback_type)

                logger.info(f"User feedback added for {interaction_id}: {feedback_type}")
                return True
            else:
                logger.warning(f"Failed to update interaction {interaction_id} with feedback")
                return False

        except Exception as e:
            logger.error(f"Failed to add user feedback: {e}")
            return False

    async def get_quality_statistics(self, days: int = 7) -> Dict[str, Any]:
        """Get quality statistics"""
        if not CONFIG.quality_db_enabled:
            return {}

        try:
            recent_interactions = await quality_db.get_recent_interactions(limit=100)

            if not recent_interactions:
                return {"error": "No interactions found"}

            # Calculate statistics
            total_interactions = len(recent_interactions)
            interactions_with_feedback = len([i for i in recent_interactions if i.user_feedback_type])
            positive_feedback = len([i for i in recent_interactions if i.user_feedback_type == 'positive'])
            negative_feedback = len([i for i in recent_interactions if i.user_feedback_type == 'negative'])

            # RAGAS scores
            ragas_scores = [i.ragas_overall_score for i in recent_interactions if i.ragas_overall_score is not None]
            avg_ragas_score = sum(ragas_scores) / len(ragas_scores) if ragas_scores else 0.0

            # Combined scores
            combined_scores = [i.combined_score for i in recent_interactions if i.combined_score is not None]
            avg_combined_score = sum(combined_scores) / len(combined_scores) if combined_scores else 0.0

            return {
                "period_days": days,
                "total_interactions": total_interactions,
                "interactions_with_feedback": interactions_with_feedback,
                "positive_feedback": positive_feedback,
                "negative_feedback": negative_feedback,
                "satisfaction_rate": (positive_feedback / interactions_with_feedback * 100) if interactions_with_feedback > 0 else 0.0,
                "avg_ragas_score": avg_ragas_score,
                "avg_combined_score": avg_combined_score
            }

        except Exception as e:
            logger.error(f"Failed to get quality statistics: {e}")
            return {"error": str(e)}

    async def get_recent_interactions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent quality interactions"""
        if not self._initialized:
            await self.initialize()

        if not self._initialized or not CONFIG.quality_db_enabled:
            return []

        try:
            interactions = await quality_db.get_recent_interactions(limit=limit)
            return interactions
        except Exception as e:
            logger.error(f"Failed to get recent interactions: {e}")
            return []

    async def get_quality_trends(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get quality trends over time"""
        if not self._initialized:
            await self.initialize()

        if not self._initialized or not CONFIG.quality_db_enabled:
            return []

        try:
            trends = await quality_db.get_quality_trends(days=days)
            return trends
        except Exception as e:
            logger.error(f"Failed to get quality trends: {e}")
            return []

    async def get_correlation_analysis(self) -> Dict[str, Any]:
        """Get correlation analysis between RAGAS and user feedback"""
        if not self._initialized:
            await self.initialize()

        if not self._initialized or not CONFIG.quality_db_enabled:
            return {}

        try:
            correlation = await quality_db.get_correlation_analysis()
            return correlation
        except Exception as e:
            logger.error(f"Failed to get correlation analysis: {e}")
            return {}

    async def close(self):
        """Close quality manager"""
        if CONFIG.quality_db_enabled:
            await quality_db.close()
        logger.info("Quality manager closed")

# Global instance
quality_manager = UnifiedQualityManager()
