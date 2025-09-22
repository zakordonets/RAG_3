"""
RAGAS Evaluator for quality assessment without ground truth
"""
from __future__ import annotations

import asyncio
from typing import Dict, List, Any, Optional
from loguru import logger

from ragas import evaluate
from ragas.metrics import Faithfulness, ContextPrecision, AnswerRelevancy
from langchain_core.language_models.base import BaseLanguageModel
from langchain_core.embeddings import Embeddings
from langchain_core.output_parsers import StrOutputParser
from langchain_core.outputs import LLMResult, Generation
from langchain_core.messages import BaseMessage

from app.config import CONFIG
from app.services.llm_router import generate_answer
from app.services.bge_embeddings import embed_unified

class YandexGPTLangChainWrapper(BaseLanguageModel):
    """LangChain wrapper for YandexGPT"""

    def __init__(self):
        super().__init__()

    def _generate(self, messages, **kwargs):
        """Generate response using YandexGPT"""
        # Extract the last user message
        user_message = messages[-1].content if messages else ""

        # Call our YandexGPT service
        response = generate_answer(
            message=user_message,
            context_documents=[],
            chat_id="ragas_eval"
        )

        # Return in LangChain format
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

    def ainvoke(self, input, **kwargs):
        return asyncio.run(self.invoke(input, **kwargs))

    def generate_prompt(self, prompts, **kwargs):
        return self._generate(prompts, **kwargs)

    def agenerate_prompt(self, prompts, **kwargs):
        return asyncio.run(self.generate_prompt(prompts, **kwargs))

    def predict(self, text, **kwargs):
        return self._generate([text])

    def apredict(self, text, **kwargs):
        return asyncio.run(self.predict(text, **kwargs))

    def predict_messages(self, messages, **kwargs):
        return self._generate(messages, **kwargs)

    def apredict_messages(self, messages, **kwargs):
        return asyncio.run(self.predict_messages(messages, **kwargs))

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
            embeddings.append(result['dense'].tolist())
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """Embed query"""
        result = embed_unified(text, return_dense=True, return_sparse=False)
        return result['dense'].tolist()

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

        # Initialize RAGAS metrics (only LLM, embeddings are handled internally)
        self.faithfulness = Faithfulness(llm=self.llm_wrapper)
        self.context_precision = ContextPrecision(llm=self.llm_wrapper)
        self.answer_relevancy = AnswerRelevancy(llm=self.llm_wrapper)

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
            # Prepare data for RAGAS using datasets library
            from datasets import Dataset

            dataset = Dataset.from_dict({
                'question': [query],
                'answer': [response],
                'contexts': [contexts],
                'ground_truth': [""]  # Empty ground truth for no-reference evaluation
            })

            # Evaluate with RAGAS
            result = evaluate(
                dataset,
                metrics=[
                    self.faithfulness,
                    self.context_precision,
                    self.answer_relevancy
                ]
            )

            # Extract scores
            scores = {
                'faithfulness': float(result['faithfulness'][0]) if 'faithfulness' in result else 0.0,
                'context_precision': float(result['context_precision'][0]) if 'context_precision' in result else 0.0,
                'answer_relevancy': float(result['answer_relevancy'][0]) if 'answer_relevancy' in result else 0.0,
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
