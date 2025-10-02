#!/usr/bin/env python3
"""
Metadata-aware indexing service for optimized document processing
"""

from __future__ import annotations

import time
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, SparseVector, Filter, FieldCondition, MatchValue

from app.config import CONFIG
from app.services.bge_embeddings import embed_batch_optimized
from app.models.enhanced_metadata import EnhancedMetadata
from ingestion.chunker import text_hash
import uuid


class MetadataAwareIndexer:
    """Enhanced indexer with metadata-driven optimization"""

    def __init__(self):
        self.client = QdrantClient(
            url=CONFIG.qdrant_url,
            api_key=CONFIG.qdrant_api_key or None
        )
        self.collection_name = CONFIG.qdrant_collection

    def get_optimal_batch_size(self, vector_type: str, device: str = "auto") -> int:
        """Get optimal batch size based on vector type and device"""
        if CONFIG.adaptive_batching:
            if vector_type == "sparse":
                return CONFIG.sparse_batch_size
            elif vector_type == "dense":
                return CONFIG.dense_batch_size
            else:  # unified
                return max(CONFIG.sparse_batch_size, CONFIG.dense_batch_size)
        return CONFIG.embedding_batch_size

    def get_optimal_chunk_size(self, metadata: EnhancedMetadata) -> int:
        """Calculate optimal chunk size based on metadata"""
        base_size = CONFIG.chunk_max_tokens

        # Adjust based on page type
        if metadata.page_type == "api":
            return min(base_size * 1.5, 1200)  # API docs can be longer
        elif metadata.page_type == "guide":
            return min(base_size * 1.2, 1000)  # Guides benefit from context
        elif metadata.page_type == "faq":
            return min(base_size * 0.8, 600)   # FAQ items are usually shorter

        # Adjust based on complexity
        if metadata.complexity_score > 0.8:
            return min(base_size * 0.9, 800)  # Complex content needs smaller chunks
        elif metadata.complexity_score < 0.3:
            return min(base_size * 1.3, 1000)  # Simple content can be larger

        return base_size

    def get_search_strategy(self, metadata: EnhancedMetadata) -> Dict[str, float]:
        """Determine optimal search strategy based on metadata"""
        if metadata.page_type == "api":
            return {"sparse_weight": 0.7, "dense_weight": 0.3}  # API queries benefit from exact matching
        elif metadata.complexity_score > 0.7:
            return {"sparse_weight": 0.3, "dense_weight": 0.7}  # Complex content benefits from semantic search
        elif metadata.semantic_density > 0.6:
            return {"sparse_weight": 0.4, "dense_weight": 0.6}  # Dense content needs semantic understanding
        else:
            return {"sparse_weight": 0.5, "dense_weight": 0.5}  # Balanced approach

    def optimize_sparse_conversion(self, lex_weights: Dict[str, float]) -> Tuple[List[int], List[float]]:
        """Optimized sparse vector conversion with sorting and compression"""
        if not lex_weights:
            return [], []

        # Sort by weight for better compression and performance
        sorted_items = sorted(lex_weights.items(), key=lambda x: x[1], reverse=True)

        # Limit to top weights to reduce noise and improve performance
        max_indices = 1000  # Reasonable limit for sparse vectors
        if len(sorted_items) > max_indices:
            sorted_items = sorted_items[:max_indices]
            logger.debug(f"Limited sparse vector to top {max_indices} weights")

        indices = [int(k) for k, v in sorted_items]
        values = [float(v) for k, v in sorted_items]

        return indices, values

    def index_chunks_with_metadata(self, chunks: List[Dict[str, Any]]) -> int:
        """Index chunks with enhanced metadata processing"""
        if not chunks:
            return 0

        logger.info(f"Starting metadata-aware indexing of {len(chunks)} chunks")
        start_time = time.time()

        points: List[PointStruct] = []
        texts = [c["text"] for c in chunks]

        # Process metadata for all chunks
        enhanced_metadata_list = []
        for i, chunk in enumerate(chunks):
            payload = chunk.get("payload", {})
            metadata = EnhancedMetadata.from_text_and_metadata(
                text=chunk["text"],
                url=payload.get("url", ""),
                title=payload.get("title", ""),
                page_type=payload.get("page_type", "guide"),
                chunk_index=payload.get("chunk_index", i),
                section=payload.get("section")
            )

            # Add adaptive chunking metadata
            metadata.adaptive_chunking = payload.get("adaptive_chunking", False)
            metadata.chunk_type = payload.get("chunk_type")
            metadata.total_chunks = payload.get("total_chunks", 1)

            enhanced_metadata_list.append(metadata)

        # Determine optimal batch size
        batch_size = self.get_optimal_batch_size("unified")
        logger.info(f"Using batch size: {batch_size}")

        # Generate embeddings in small batches to avoid OOM
        dense_vecs = []
        sparse_results = []

        # Process in ultra-small batches to prevent OOM
        micro_batch_size = 1  # Process one text at a time!
        total_batches = (len(texts) + micro_batch_size - 1) // micro_batch_size

        logger.info(f"Processing {len(texts)} texts in {total_batches} micro-batches of {micro_batch_size}")

        for i in range(0, len(texts), micro_batch_size):
            batch_texts = texts[i:i + micro_batch_size]
            batch_num = (i // micro_batch_size) + 1

            logger.info(f"Processing micro-batch {batch_num}/{total_batches} ({len(batch_texts)} texts)")

            try:
                # Process single batch
                embedding_results = embed_batch_optimized(
                    batch_texts,
                    max_length=CONFIG.embedding_max_length_doc,
                    return_dense=True,
                    return_sparse=CONFIG.use_sparse,
                    context="document"
                )

                # Extract results immediately to free memory
                batch_dense = embedding_results.get('dense_vecs', [[0.0] * 1024] * len(batch_texts))
                batch_sparse = embedding_results.get('lexical_weights', [{}] * len(batch_texts))

                dense_vecs.extend(batch_dense)
                sparse_results.extend(batch_sparse)

                # Force garbage collection after each batch
                import gc
                gc.collect()

                logger.info(f"✅ Micro-batch {batch_num}/{total_batches} completed")

            except Exception as e:
                logger.error(f"❌ Error in micro-batch {batch_num}: {e}")
                # Add fallback vectors
                dense_vecs.extend([[0.0] * 1024] * len(batch_texts))
                sparse_results.extend([{}] * len(batch_texts))

        logger.info(f"✅ All {len(texts)} texts processed in {total_batches} micro-batches")

        # Create points with enhanced metadata
        for i, (chunk, metadata) in enumerate(zip(chunks, enhanced_metadata_list)):
            # Generate deterministic ID
            raw_hash = chunk.get("id") or text_hash(chunk["text"])
            hex32 = raw_hash.replace("-", "")[:32]
            pid = str(uuid.UUID(hex=hex32))

            # Build vector dictionary
            vector_dict = {"dense": dense_vecs[i]}

            # Add optimized sparse vector
            if CONFIG.use_sparse and sparse_results[i]:
                try:
                    indices, values = self.optimize_sparse_conversion(sparse_results[i])
                    if indices:
                        vector_dict["sparse"] = SparseVector(indices=indices, values=values)
                        logger.debug(f"Chunk {i}: Added optimized sparse vector with {len(indices)} indices")
                except Exception as e:
                    logger.warning(f"Failed to process sparse vector for chunk {i}: {e}")

            # Create optimized payload (including text for search)
            search_payload = metadata.to_search_payload()
            search_payload["hash"] = pid
            search_payload["search_strategy"] = self.get_search_strategy(metadata)

            # Add the actual text content for search
            search_payload["text"] = chunk["text"]

            # Add original payload fields that might be needed
            original_payload = chunk.get("payload", {})
            for key in ["indexed_via", "indexed_at", "url_hash"]:
                if key in original_payload:
                    search_payload[key] = original_payload[key]

            # Add adaptive chunking fields
            adaptive_fields = ["adaptive_chunking", "chunk_type", "total_chunks", "section_title", "section_index"]
            for key in adaptive_fields:
                if key in original_payload:
                    search_payload[key] = original_payload[key]

            point = PointStruct(
                id=pid,
                vector=vector_dict,
                payload=search_payload
            )
            points.append(point)

        # Upsert to Qdrant
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)
            elapsed = time.time() - start_time
            logger.info(f"Successfully indexed {len(points)} chunks in {elapsed:.2f}s")

            # Log metadata statistics
            self._log_metadata_stats(enhanced_metadata_list)

        return len(points)

    def _log_metadata_stats(self, metadata_list: List[EnhancedMetadata]):
        """Log statistics about processed metadata"""
        if not metadata_list:
            return

        # Calculate averages
        avg_complexity = sum(m.complexity_score for m in metadata_list) / len(metadata_list)
        avg_density = sum(m.semantic_density for m in metadata_list) / len(metadata_list)
        avg_readability = sum(m.readability_score for m in metadata_list) / len(metadata_list)
        avg_boost = sum(m.boost_factor for m in metadata_list) / len(metadata_list)

        # Count by page type
        page_types = {}
        for m in metadata_list:
            page_types[m.page_type] = page_types.get(m.page_type, 0) + 1

        logger.info(f"Metadata statistics:")
        logger.info(f"  Average complexity: {avg_complexity:.3f}")
        logger.info(f"  Average density: {avg_density:.3f}")
        logger.info(f"  Average readability: {avg_readability:.3f}")
        logger.info(f"  Average boost factor: {avg_boost:.3f}")
        logger.info(f"  Page types: {page_types}")

    def search_with_metadata_filtering(
        self,
        query: str,
        dense_vector: List[float],
        sparse_vector: Dict[str, Any],
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Enhanced search with metadata filtering"""

        # Build Qdrant filter (simplified for now)
        qdrant_filter = None
        if filters:
            conditions = []
            for key, value in filters.items():
                # Handle simple string/integer matches only
                if isinstance(value, (str, int, bool)):
                    conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
                elif isinstance(value, list):
                    # For lists, match any value in the list
                    for item in value:
                        conditions.append(FieldCondition(key=key, match=MatchValue(value=item)))

            if conditions:
                qdrant_filter = Filter(must=conditions)

        # Perform search
        try:
            # Dense search
            dense_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=("dense", dense_vector),
                query_filter=qdrant_filter,
                limit=limit * 2,  # Get more results for better fusion
                with_payload=True
            )

            # Sparse search (if enabled)
            sparse_results = []
            if CONFIG.use_sparse and sparse_vector.get("indices"):
                sparse_results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=("sparse", SparseVector(
                        indices=sparse_vector["indices"],
                        values=sparse_vector["values"]
                    )),
                    query_filter=qdrant_filter,
                    limit=limit * 2,
                    with_payload=True
                )

            # Convert to standard format
            dense_hits = [{"id": str(r.id), "score": r.score, "payload": r.payload} for r in dense_results]
            sparse_hits = [{"id": str(r.id), "score": r.score, "payload": r.payload} for r in sparse_results]

            # Apply RRF fusion
            from app.services.retrieval import rrf_fuse
            fused_results = rrf_fuse(dense_hits, sparse_hits)

            return fused_results[:limit]

        except Exception as e:
            logger.error(f"Metadata-filtered search failed: {e}")
            return []

    def get_collection_metadata_stats(self) -> Dict[str, Any]:
        """Get metadata statistics for the collection"""
        try:
            # Get collection info
            collection_info = self.client.get_collection(self.collection_name)

            # Sample documents for metadata analysis
            sample_points = self.client.scroll(
                collection_name=self.collection_name,
                limit=1000,
                with_payload=True,
                with_vectors=False
            )[0]

            if not sample_points:
                return {"error": "No documents found"}

            # Analyze metadata
            page_types = {}
            complexity_scores = []
            density_scores = []
            boost_factors = []

            for point in sample_points:
                payload = point.payload or {}

                # Page type distribution
                page_type = payload.get("page_type", "unknown")
                page_types[page_type] = page_types.get(page_type, 0) + 1

                # Collect scores
                if "complexity_score" in payload:
                    complexity_scores.append(payload["complexity_score"])
                if "semantic_density" in payload:
                    density_scores.append(payload["semantic_density"])
                if "boost_factor" in payload:
                    boost_factors.append(payload["boost_factor"])

            stats = {
                "total_documents": collection_info.points_count,
                "sample_size": len(sample_points),
                "page_type_distribution": page_types,
                "avg_complexity_score": sum(complexity_scores) / len(complexity_scores) if complexity_scores else 0,
                "avg_semantic_density": sum(density_scores) / len(density_scores) if density_scores else 0,
                "avg_boost_factor": sum(boost_factors) / len(boost_factors) if boost_factors else 0,
                "metadata_enabled": bool(complexity_scores),  # Check if enhanced metadata is present
            }

            return stats

        except Exception as e:
            logger.error(f"Failed to get collection metadata stats: {e}")
            return {"error": str(e)}
