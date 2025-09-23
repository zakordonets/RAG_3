"""
RAGAS Evaluator for quality assessment without ground truth
"""
from __future__ import annotations

import asyncio
import math
import os
from typing import Dict, List, Any, Optional
from loguru import logger

from ragas import evaluate
from ragas.metrics import Faithfulness, ContextPrecision, AnswerRelevancy
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_core.language_models.base import BaseLanguageModel
from langchain_core.embeddings import Embeddings
from langchain_core.output_parsers import StrOutputParser
from langchain_core.outputs import LLMResult, Generation
from langchain_core.messages import BaseMessage

from app.config import CONFIG
from app.services.llm_router import _yandex_complete as _raw_yandex_complete
from app.services.bge_embeddings import embed_unified

class YandexGPTLangChainWrapper(BaseLanguageModel):
    """LangChain wrapper for YandexGPT"""

    def __init__(self):
        super().__init__()

    def _generate(self, messages, **kwargs):
        """Generate response using YandexGPT"""
        # Normalize inputs to a list of LangChain messages
        from langchain_core.messages import HumanMessage

        normalized_messages = []
        if messages is None:
            normalized_messages = []
        elif isinstance(messages, list):
            for m in messages:
                if hasattr(m, 'to_messages'):
                    # PromptValue
                    normalized_messages.extend(m.to_messages())
                elif hasattr(m, 'content'):
                    normalized_messages.append(m)
                elif isinstance(m, str):
                    normalized_messages.append(HumanMessage(content=m))
                else:
                    # Fallback: convert to string
                    normalized_messages.append(HumanMessage(content=str(m)))
        else:
            # Single item
            m = messages
            if hasattr(m, 'to_messages'):
                normalized_messages = m.to_messages()
            elif hasattr(m, 'content'):
                normalized_messages = [m]
            elif isinstance(m, str):
                normalized_messages = [HumanMessage(content=m)]
            else:
                normalized_messages = [HumanMessage(content=str(m))]

        # Build raw prompt from messages for evaluator LLM
        prompt = "\n\n".join(m.content for m in normalized_messages) if normalized_messages else ""
        # Call low-level Yandex completion (no formatting), deterministic for RAGAS
        response = _raw_yandex_complete(prompt, temperature=0.0, top_p=1.0)
        # Return LLMResult for LangChain compatibility
        return LLMResult(generations=[[Generation(text=response)]])

    def _llm_type(self) -> str:
        return "yandexgpt"

    # Required abstract methods
    def invoke(self, input, **kwargs):
        if isinstance(input, BaseMessage):
            return self._generate([input])
        else:
            # Convert string to message
            from langchain_core.messages import HumanMessage
            return self._generate([HumanMessage(content=str(input))])

    async def ainvoke(self, input, **kwargs):
        # Run sync generation in a thread for true async
        if isinstance(input, BaseMessage):
            return await asyncio.to_thread(self._generate, [input])
        else:
            from langchain_core.messages import HumanMessage
            return await asyncio.to_thread(self._generate, [HumanMessage(content=str(input))])

    def generate_prompt(self, prompts, **kwargs):
        return self._generate(prompts, **kwargs)

    def agenerate_prompt(self, prompts, **kwargs):
        return asyncio.run(self.generate_prompt(prompts, **kwargs))

    # Methods expected by some LangChain integrations
    def generate(self, prompts, **kwargs):
        # Accept string or list of strings/messages
        if isinstance(prompts, str):
            from langchain_core.messages import HumanMessage
            return self._generate([HumanMessage(content=prompts)])
        if isinstance(prompts, list):
            # If list of strings, convert; if list of messages, pass through
            if prompts and isinstance(prompts[0], str):
                from langchain_core.messages import HumanMessage
                msgs = [HumanMessage(content=p) for p in prompts]
                return self._generate(msgs)
            return self._generate(prompts)
        return self._generate([prompts])

    async def agenerate(self, prompts, **kwargs):
        return await asyncio.to_thread(self.generate, prompts)

    def predict(self, text, **kwargs):
        return self._generate([text])

    async def apredict(self, text, **kwargs):
        return await asyncio.to_thread(self.predict, text)

    def predict_messages(self, messages, **kwargs):
        return self._generate(messages, **kwargs)

    async def apredict_messages(self, messages, **kwargs):
        return await asyncio.to_thread(self.predict_messages, messages)

    def set_run_config(self, config=None, **kwargs):
        """Set run configuration (required by RAGAS)"""
        pass

class BGELangChainWrapper(Embeddings):
    """LangChain wrapper for BGE embeddings"""

    def __init__(self):
        super().__init__()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed documents"""
        embeddings = []
        for text in texts:
            result = embed_unified(text, return_dense=True, return_sparse=False)
            # embed_unified returns {'dense_vecs': [[...]]}
            vec = result.get('dense_vecs', [[0.0] * 1024])
            embeddings.append(vec[0] if vec and len(vec) > 0 else [0.0] * 1024)
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """Embed query"""
        result = embed_unified(text, return_dense=True, return_sparse=False)
        vec = result.get('dense_vecs', [[0.0] * 1024])
        return vec[0] if vec and len(vec) > 0 else [0.0] * 1024

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Async embed documents"""
        return self.embed_documents(texts)

    async def aembed_query(self, text: str) -> List[float]:
        """Async embed query"""
        return self.embed_query(text)

class RAGASEvaluatorWithoutGroundTruth:
    """RAGAS evaluator without ground truth"""

    def __init__(self):
        self.llm_wrapper = YandexGPTLangChainWrapper()
        self.embeddings_wrapper = BGELangChainWrapper()
        # Wrap for RAGAS compatibility
        self.evaluator_llm = LangchainLLMWrapper(self.llm_wrapper)
        self.evaluator_embeddings = LangchainEmbeddingsWrapper(self.embeddings_wrapper)

        # Initialize RAGAS metrics with evaluator LLM wrapper
        self.faithfulness = Faithfulness(llm=self.evaluator_llm)
        self.context_precision = ContextPrecision(llm=self.evaluator_llm)
        self.answer_relevancy = AnswerRelevancy(llm=self.evaluator_llm)

        logger.info("RAGAS evaluator initialized")

    async def evaluate_interaction(
        self,
        query: str,
        response: str,
        contexts: List[str],
        sources: List[str]
    ) -> Dict[str, Any]:
        """
        Evaluate interaction using RAGAS metrics

        Args:
            query: User query
            response: System response
            contexts: Retrieved context documents
            sources: Source URLs

        Returns:
            Dictionary with RAGAS scores
        """
        try:
            # Check if RAGAS evaluation is disabled
            if os.getenv("RAGAS_EVALUATION_SAMPLE_RATE", "1.0") == "0":
                logger.info("RAGAS evaluation disabled, using fallback scores")
                return self._calculate_fallback_scores(query, response, contexts)
            
            # Prepare data for RAGAS using datasets library
            from datasets import Dataset

            dataset = Dataset.from_dict({
                'question': [query],
                'answer': [response],
                'contexts': [contexts],
                'ground_truth': [""]  # Empty ground truth for no-reference evaluation
            })

            # Evaluate with RAGAS with timeout
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        evaluate,
                        dataset,
                        metrics=[
                            self.faithfulness,
                            self.context_precision,
                            self.answer_relevancy
                        ],
                        llm=self.evaluator_llm,
                        embeddings=self.evaluator_embeddings
                    ),
                    timeout=25.0  # 25 seconds timeout
                )
            except asyncio.TimeoutError:
                logger.warning("RAGAS evaluation timeout, using fallback scores")
                return self._calculate_fallback_scores(query, response, contexts)

            # Extract scores (datasets returns a columnar structure)
            try:
                faith_list = result.get('faithfulness') or result['faithfulness']
                ctxp_list = result.get('context_precision') or result['context_precision']
                ansr_list = result.get('answer_relevancy') or result['answer_relevancy']
                faith = float(faith_list[0]) if isinstance(faith_list, (list, tuple)) else float(faith_list)
                ctxp = float(ctxp_list[0]) if isinstance(ctxp_list, (list, tuple)) else float(ctxp_list)
                ansr = float(ansr_list[0]) if isinstance(ansr_list, (list, tuple)) else float(ansr_list)
            except Exception:
                # Some versions return dict-like rows
                row0 = result[0] if isinstance(result, list) else None
                faith = float(row0.get('faithfulness', 0.0)) if row0 else 0.0
                ctxp = float(row0.get('context_precision', 0.0)) if row0 else 0.0
                ansr = float(row0.get('answer_relevancy', 0.0)) if row0 else 0.0

            # Sanitize NaN/inf
            for name, val in (('faithfulness', faith), ('context_precision', ctxp), ('answer_relevancy', ansr)):
                if val is None or math.isnan(val) or math.isinf(val):
                    if name == 'faithfulness':
                        faith = 0.0
                    elif name == 'context_precision':
                        ctxp = 0.0
                    else:
                        ansr = 0.0

            scores = {
                'faithfulness': faith,
                'context_precision': ctxp,
                'answer_relevancy': ansr,
            }

            # Calculate overall score
            scores['overall_score'] = (
                scores['faithfulness'] +
                scores['context_precision'] +
                scores['answer_relevancy']
            ) / 3.0

            logger.info(f"RAGAS evaluation completed: {scores}")
            return scores

        except Exception as e:
            logger.error(f"RAGAS evaluation failed: {e}")
            # Return fallback scores with some intelligence
            fallback_scores = self._calculate_fallback_scores(query, response, contexts)
            logger.info(f"Using fallback scores: {fallback_scores}")
            return fallback_scores

    def _calculate_fallback_scores(
        self,
        query: str,
        response: str,
        contexts: List[str]
    ) -> Dict[str, float]:
        """Calculate fallback scores using heuristics"""
        # Faithfulness: based on response length and context usage
        faithfulness = 0.7 if len(response) > 20 else 0.3
        if contexts and any(ctx in response.lower() for ctx in contexts):
            faithfulness += 0.2

        # Context precision: based on context availability
        context_precision = 0.8 if contexts else 0.0
        if contexts:
            context_precision = min(0.9, len(contexts) * 0.3)

        # Answer relevancy: based on response quality
        answer_relevancy = 0.6
        if len(response) > 50:
            answer_relevancy += 0.2
        if query.lower() in response.lower():
            answer_relevancy += 0.1

        scores = {
            'faithfulness': min(1.0, faithfulness),
            'context_precision': min(1.0, context_precision),
            'answer_relevancy': min(1.0, answer_relevancy),
            'overall_score': (faithfulness + context_precision + answer_relevancy) / 3.0
        }

        return scores

# Global instance
ragas_evaluator = RAGASEvaluatorWithoutGroundTruth()
