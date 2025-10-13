"""
RAGAS Evaluator for quality assessment without ground truth

Поддерживает:
- Эвристическую оценку (быстро, без LLM вызовов)
- RAGAS оценку с YandexGPT (требует async интеграцию)
- RAGAS оценку с OpenAI (опционально, если установлен OPENAI_API_KEY)
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
from langchain_core.callbacks.manager import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun

from app.config import CONFIG
from app.services.core.llm_router import _yandex_complete as _raw_yandex_complete
from app.services.core.embeddings import embed_unified

class YandexGPTLangChainWrapper(BaseLanguageModel):
    """
    LangChain wrapper for YandexGPT with proper async support for RAGAS

    ВАЖНО: Все async методы используют asyncio.to_thread() для запуска
    синхронных вызовов YandexGPT API в отдельном потоке.
    """

    def __init__(self):
        super().__init__()

    def _format_prompt(self, messages) -> str:
        """Format messages into a single prompt string"""
        from langchain_core.messages import HumanMessage

        normalized_messages = []
        if messages is None:
            return ""
        elif isinstance(messages, str):
            return messages
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
                    normalized_messages.append(HumanMessage(content=str(m)))
        else:
            # Single message object
            if hasattr(messages, 'to_messages'):
                normalized_messages = messages.to_messages()
            elif hasattr(messages, 'content'):
                normalized_messages = [messages]
            else:
                normalized_messages = [HumanMessage(content=str(messages))]

        # Build prompt from messages
        return "\n\n".join(m.content for m in normalized_messages if hasattr(m, 'content'))

    def _generate(
        self,
        prompts: List[str],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs
    ) -> LLMResult:
        """Generate responses for a list of prompts (sync)"""
        generations = []
        for prompt in prompts:
            try:
                # Call YandexGPT with deterministic parameters for RAGAS
                response = _raw_yandex_complete(prompt, temperature=0.0, top_p=1.0)
                generations.append([Generation(text=response)])
            except Exception as e:
                logger.error(f"YandexGPT generation failed: {e}")
                # Return empty generation on error
                generations.append([Generation(text="")])

        return LLMResult(generations=generations)

    async def _agenerate(
        self,
        prompts: List[str],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs
    ) -> LLMResult:
        """Generate responses for a list of prompts (async)"""
        # Run in thread pool to avoid blocking
        return await asyncio.to_thread(self._generate, prompts, stop, run_manager, **kwargs)

    def _llm_type(self) -> str:
        return "yandexgpt"

    # ВАЖНО: Переопределяем все методы для совместимости с RAGAS

    def invoke(self, input, **kwargs):
        """Invoke with single input"""
        prompt = self._format_prompt(input)
        result = self._generate([prompt], **kwargs)
        return result.generations[0][0].text if result.generations else ""

    async def ainvoke(self, input, **kwargs):
        """Async invoke with single input"""
        prompt = self._format_prompt(input)
        result = await self._agenerate([prompt], **kwargs)
        return result.generations[0][0].text if result.generations else ""

    def generate_prompt(self, prompts, **kwargs):
        """Generate from PromptValue list"""
        prompt_strings = [self._format_prompt(p) for p in prompts]
        return self._generate(prompt_strings, **kwargs)

    async def agenerate_prompt(self, prompts, **kwargs):
        """Async generate from PromptValue list"""
        prompt_strings = [self._format_prompt(p) for p in prompts]
        return await self._agenerate(prompt_strings, **kwargs)

    def generate(self, prompts, **kwargs):
        """Generate from string list"""
        if isinstance(prompts, str):
            prompts = [prompts]
        prompt_strings = [self._format_prompt(p) for p in prompts]
        return self._generate(prompt_strings, **kwargs)

    async def agenerate(self, prompts, **kwargs):
        """Async generate from string list"""
        if isinstance(prompts, str):
            prompts = [prompts]
        prompt_strings = [self._format_prompt(p) for p in prompts]
        return await self._agenerate(prompt_strings, **kwargs)

    # Дополнительные методы для полной совместимости
    def predict(self, text: str, stop: Optional[List[str]] = None, **kwargs) -> str:
        """Predict single text"""
        result = self._generate([text], stop=stop, **kwargs)
        return result.generations[0][0].text if result.generations else ""

    async def apredict(self, text: str, stop: Optional[List[str]] = None, **kwargs) -> str:
        """Async predict single text"""
        result = await self._agenerate([text], stop=stop, **kwargs)
        return result.generations[0][0].text if result.generations else ""

    def predict_messages(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> BaseMessage:
        """Predict from messages"""
        from langchain_core.messages import AIMessage
        prompt = self._format_prompt(messages)
        result = self._generate([prompt], stop=stop, **kwargs)
        text = result.generations[0][0].text if result.generations else ""
        return AIMessage(content=text)

    async def apredict_messages(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> BaseMessage:
        """Async predict from messages"""
        from langchain_core.messages import AIMessage
        prompt = self._format_prompt(messages)
        result = await self._agenerate([prompt], stop=stop, **kwargs)
        text = result.generations[0][0].text if result.generations else ""
        return AIMessage(content=text)

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
    """
    RAGAS evaluator with multiple LLM backend support

    Поддерживаемые режимы:
    1. Эвристическая оценка (по умолчанию, быстро, без LLM вызовов)
    2. RAGAS с YandexGPT (через исправленный async wrapper)
    3. RAGAS с OpenAI (требует OPENAI_API_KEY)
    4. RAGAS с Deepseek (требует DEEPSEEK_API_KEY, OpenAI-совместимый)
    5. RAGAS с GPT-5 (требует GPT5_API_KEY, OpenAI-совместимый)

    Выбор LLM для RAGAS через переменную: RAGAS_LLM_BACKEND
    """

    def __init__(self):
        # Определяем, какой LLM использовать для RAGAS
        ragas_backend = os.getenv("RAGAS_LLM_BACKEND", CONFIG.ragas_llm_model).lower()

        self.ragas_enabled = False
        self.backend_name = "heuristic"

        try:
            if ragas_backend == "yandexgpt" or ragas_backend == "yandex":
                # Используем исправленный YandexGPT wrapper
                self._init_yandex_backend()
            elif ragas_backend == "openai":
                # Используем OpenAI
                self._init_openai_backend()
            elif ragas_backend == "deepseek":
                # Используем Deepseek (OpenAI-совместимый)
                self._init_deepseek_backend()
            elif ragas_backend in ["gpt5", "gpt-5"]:
                # Используем GPT-5 (OpenAI-совместимый)
                self._init_gpt5_backend()
            else:
                logger.info(f"Unknown RAGAS backend '{ragas_backend}', using heuristics only")
        except Exception as e:
            logger.warning(f"Failed to initialize RAGAS backend '{ragas_backend}': {e}")
            logger.info("Falling back to heuristic evaluation")

    def _init_yandex_backend(self):
        """Initialize RAGAS with YandexGPT"""
        if not CONFIG.yandex_api_key:
            logger.warning("YANDEX_API_KEY not set, using heuristics")
            return

        self.llm_wrapper = YandexGPTLangChainWrapper()
        self.embeddings_wrapper = BGELangChainWrapper()

        self.evaluator_llm = LangchainLLMWrapper(self.llm_wrapper)
        self.evaluator_embeddings = LangchainEmbeddingsWrapper(self.embeddings_wrapper)

        self.faithfulness = Faithfulness(llm=self.evaluator_llm)
        self.context_precision = ContextPrecision(llm=self.evaluator_llm)
        self.answer_relevancy = AnswerRelevancy(llm=self.evaluator_llm)

        self.ragas_enabled = True
        self.backend_name = "YandexGPT"
        logger.info("RAGAS evaluator initialized with YandexGPT")

    def _init_openai_backend(self):
        """Initialize RAGAS with OpenAI"""
        if not os.getenv("OPENAI_API_KEY"):
            logger.warning("OPENAI_API_KEY not set, using heuristics")
            return

        from langchain_openai import ChatOpenAI, OpenAIEmbeddings

        self.llm_wrapper = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0.0
        )
        self.embeddings_wrapper = OpenAIEmbeddings()

        self.evaluator_llm = LangchainLLMWrapper(self.llm_wrapper)
        self.evaluator_embeddings = LangchainEmbeddingsWrapper(self.embeddings_wrapper)

        self.faithfulness = Faithfulness(llm=self.evaluator_llm)
        self.context_precision = ContextPrecision(llm=self.evaluator_llm)
        self.answer_relevancy = AnswerRelevancy(llm=self.evaluator_llm)

        self.ragas_enabled = True
        self.backend_name = "OpenAI"
        logger.info(f"RAGAS evaluator initialized with OpenAI ({self.llm_wrapper.model_name})")

    def _init_deepseek_backend(self):
        """Initialize RAGAS with Deepseek (OpenAI-compatible)"""
        if not CONFIG.deepseek_api_key:
            logger.warning("DEEPSEEK_API_KEY not set, using heuristics")
            return

        from langchain_openai import ChatOpenAI, OpenAIEmbeddings

        # Deepseek использует OpenAI-совместимый API
        # ВАЖНО: base_url должен быть БЕЗ /chat/completions (добавляется автоматически)
        base_url = CONFIG.deepseek_api_url.replace("/chat/completions", "").replace("/v1/chat/completions", "")
        if not base_url.endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"

        logger.debug(f"Deepseek base_url: {base_url}")

        # КРИТИЧНО: Deepseek НЕ поддерживает n > 1
        # В новой версии LangChain параметры n и seed должны быть указаны напрямую
        self.llm_wrapper = ChatOpenAI(
            model=CONFIG.deepseek_model,
            api_key=CONFIG.deepseek_api_key,
            base_url=base_url,
            temperature=0.0,
            n=1,  # Deepseek поддерживает только n=1 (явно указываем)
            seed=42  # Для детерминированности
        )

        # Для embeddings используем BGE (Deepseek embeddings API может отличаться)
        self.embeddings_wrapper = BGELangChainWrapper()

        self.evaluator_llm = LangchainLLMWrapper(self.llm_wrapper)
        self.evaluator_embeddings = LangchainEmbeddingsWrapper(self.embeddings_wrapper)

        self.faithfulness = Faithfulness(llm=self.evaluator_llm)
        self.context_precision = ContextPrecision(llm=self.evaluator_llm)

        # КРИТИЧНО: Answer Relevancy по умолчанию использует n=3 внутри
        # Deepseek не поддерживает это, поэтому НЕ используем эту метрику
        # Вместо нее используем эвристику для answer_relevancy
        self.answer_relevancy = None  # Отключаем для Deepseek

        self.ragas_enabled = True
        self.backend_name = "Deepseek"
        logger.info(f"RAGAS evaluator initialized with Deepseek ({CONFIG.deepseek_model}) at {base_url}")
        logger.warning("Deepseek limitation: Answer Relevancy metric disabled (requires n>1)")

    def _init_gpt5_backend(self):
        """Initialize RAGAS with GPT-5 (OpenAI-compatible)"""
        if not CONFIG.gpt5_api_key:
            logger.warning("GPT5_API_KEY not set, using heuristics")
            return

        from langchain_openai import ChatOpenAI, OpenAIEmbeddings

        # GPT-5 использует OpenAI-совместимый API
        # ВАЖНО: base_url должен быть БЕЗ /chat/completions
        base_url = CONFIG.gpt5_api_url.replace("/chat/completions", "").replace("/v1/chat/completions", "")
        if base_url and not base_url.endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"

        self.llm_wrapper = ChatOpenAI(
            model=CONFIG.gpt5_model,
            api_key=CONFIG.gpt5_api_key,
            base_url=base_url if base_url else None,
            temperature=0.0
        )
        self.embeddings_wrapper = OpenAIEmbeddings(
            api_key=CONFIG.gpt5_api_key,
            base_url=base_url if base_url else None
        )

        self.evaluator_llm = LangchainLLMWrapper(self.llm_wrapper)
        self.evaluator_embeddings = LangchainEmbeddingsWrapper(self.embeddings_wrapper)

        self.faithfulness = Faithfulness(llm=self.evaluator_llm)
        self.context_precision = ContextPrecision(llm=self.evaluator_llm)
        self.answer_relevancy = AnswerRelevancy(llm=self.evaluator_llm)

        self.ragas_enabled = True
        self.backend_name = "GPT-5"
        logger.info(f"RAGAS evaluator initialized with GPT-5 ({CONFIG.gpt5_model})")

    async def evaluate_interaction(
        self,
        query: str,
        response: str,
        contexts: List[str],
        sources: List[str]
    ) -> Dict[str, Any]:
        """
        Evaluate interaction using RAGAS metrics or heuristic fallback

        Args:
            query: User query
            response: System response
            contexts: Retrieved context documents
            sources: Source URLs

        Returns:
            Dictionary with RAGAS scores
        """
        try:
            # Check if RAGAS evaluation is completely disabled
            sample_rate = float(os.getenv("RAGAS_EVALUATION_SAMPLE_RATE", "1.0"))

            if sample_rate == 0.0:
                logger.info("RAGAS evaluation disabled (sample_rate=0), using fallback scores")
                return self._calculate_fallback_scores(query, response, contexts)

            # Check if RAGAS backend is available
            if not self.ragas_enabled:
                logger.debug("RAGAS backend not available, using heuristic evaluation")
                return self._calculate_fallback_scores(query, response, contexts)

            # Sample-based evaluation: randomly decide whether to run RAGAS
            import random
            if random.random() > sample_rate:
                logger.debug(f"Skipping RAGAS evaluation (sample rate: {sample_rate:.2%}), using fallback")
                return self._calculate_fallback_scores(query, response, contexts)

            # Run REAL RAGAS evaluation with configured LLM
            logger.info(f"Running RAGAS evaluation with {self.backend_name} (sample rate: {sample_rate:.2%})")
            return await self._evaluate_with_ragas(query, response, contexts)

        except Exception as e:
            logger.error(f"RAGAS evaluation failed with error: {e}", exc_info=True)
            # Return fallback scores only on error
            fallback_scores = self._calculate_fallback_scores(query, response, contexts)
            logger.warning(f"Using fallback scores due to error: {fallback_scores}")
            return fallback_scores

    async def _evaluate_with_ragas(
        self,
        query: str,
        response: str,
        contexts: List[str]
    ) -> Dict[str, Any]:
        """
        Evaluate using RAGAS metrics with LLM calls

        Returns:
            Dictionary with RAGAS scores
        """
        try:
            from datasets import Dataset

            # DETAILED LOGGING для отладки разницы метрик
            logger.info(f"RAGAS Evaluation Input Data (Backend: {self.backend_name}):")
            logger.info(f"  Query: {query[:100]}...")
            logger.info(f"  Response length: {len(response)} chars")
            logger.info(f"  Response preview: {response[:150]}...")
            logger.info(f"  Number of contexts: {len(contexts)}")
            for i, ctx in enumerate(contexts[:3], 1):  # Log first 3 contexts
                logger.info(f"  Context {i}: {ctx[:100]}...")

            # Create RAGAS Dataset
            # IMPORTANT: ground_truth must be a string, not a list!
            dataset = Dataset.from_dict({
                'question': [query],
                'answer': [response],
                'contexts': [contexts],  # List[str]
                'ground_truth': [""]     # Empty string (no ground truth available)
            })

            logger.debug(f"Created RAGAS dataset with {len(contexts)} contexts")

            # Run RAGAS evaluation
            from ragas import evaluate

            # Собираем доступные метрики (исключаем None для Deepseek)
            available_metrics = []
            metric_names = []
            if self.faithfulness:
                available_metrics.append(self.faithfulness)
                metric_names.append("Faithfulness")
            if self.context_precision:
                available_metrics.append(self.context_precision)
                metric_names.append("Context Precision")
            if self.answer_relevancy:
                available_metrics.append(self.answer_relevancy)
                metric_names.append("Answer Relevancy")

            logger.info(f"Starting RAGAS evaluation with metrics: {', '.join(metric_names)}")

            result = evaluate(
                dataset=dataset,
                metrics=available_metrics,
                llm=self.evaluator_llm,
                embeddings=self.evaluator_embeddings
            )

            logger.debug(f"RAGAS result type: {type(result)}")
            logger.debug(f"RAGAS raw result: {result}")

            # Extract scores from result
            # RAGAS returns dict-like object with scalar values (not arrays)
            # Access scores directly, handle different return formats
            scores = {}

            # Try different ways to access RAGAS result
            if hasattr(result, '__getitem__'):
                # Result is dict-like
                for key in ['faithfulness', 'context_precision', 'answer_relevancy']:
                    if key in result:
                        value = result[key]
                        # Handle both scalar and array formats
                        if isinstance(value, (list, tuple)) and len(value) > 0:
                            scores[key] = float(value[0])
                        elif isinstance(value, (int, float)):
                            scores[key] = float(value)
                        else:
                            scores[key] = 0.0
                            logger.warning(f"Unexpected value type for {key}: {type(value)}")
                    else:
                        # Метрика отсутствует - используем эвристику
                        if key == 'answer_relevancy' and self.answer_relevancy is None:
                            # Для Deepseek: используем эвристику
                            scores[key] = self._calculate_heuristic_answer_relevancy(query, response)
                            logger.info(f"Using heuristic for {key}: {scores[key]:.3f}")
                        else:
                            scores[key] = 0.0
                            logger.warning(f"Missing key in RAGAS result: {key}")
            else:
                # Result is object with attributes
                scores['faithfulness'] = float(getattr(result, 'faithfulness', 0.0))
                scores['context_precision'] = float(getattr(result, 'context_precision', 0.0))
                scores['answer_relevancy'] = float(getattr(result, 'answer_relevancy', 0.0))

            # Calculate overall score (ignore NaN values)
            valid_scores = [v for v in [scores['faithfulness'], scores['context_precision'], scores['answer_relevancy']]
                           if not math.isnan(v)]
            if valid_scores:
                scores['overall_score'] = sum(valid_scores) / len(valid_scores)
            else:
                scores['overall_score'] = 0.0

            logger.info(f"RAGAS evaluation completed ({self.backend_name}):")
            logger.info(f"  Faithfulness:      {scores['faithfulness']:.3f}")
            logger.info(f"  Context Precision: {scores['context_precision']:.3f}")
            logger.info(f"  Answer Relevancy:  {scores['answer_relevancy']:.3f}")
            logger.info(f"  Overall Score:     {scores['overall_score']:.3f}")

            return scores

        except Exception as e:
            logger.error(f"RAGAS evaluation internal error: {e}", exc_info=True)
            raise  # Re-raise to trigger fallback in parent method

    def _calculate_heuristic_answer_relevancy(self, query: str, response: str) -> float:
        """Эвристическая оценка Answer Relevancy (для Deepseek)"""
        answer_relevancy = 0.3

        if len(response) > 100:
            answer_relevancy += 0.2
        elif len(response) > 50:
            answer_relevancy += 0.1

        query_words = set(query.lower().split())
        response_words = set(response.lower().split())

        stop_words = {'и', 'в', 'на', 'с', 'по', 'для', 'как', 'что', 'а', 'но', 'или'}
        query_words = query_words - stop_words

        if query_words:
            overlap = query_words.intersection(response_words)
            relevance = len(overlap) / len(query_words)
            answer_relevancy += min(0.4, relevance * 0.8)

        generic_phrases = ['не могу помочь', 'не знаю', 'извините', 'недостаточно информации']
        if any(phrase in response.lower() for phrase in generic_phrases):
            answer_relevancy -= 0.2

        if any(word in response.lower() for word in ['api', 'метод', 'настройка', 'конфигурация', 'использовать']):
            answer_relevancy += 0.1

        return max(0.0, min(1.0, answer_relevancy))

    def _calculate_heuristic_faithfulness(
        self,
        query: str,
        response: str,
        contexts: List[str]
    ) -> float:
        """
        Calculate heuristic faithfulness score without LLM calls

        Faithfulness measures how much the response is grounded in provided contexts.
        Lower base score, rewards only meaningful context usage.
        """
        # Start with low base score - response must prove faithfulness
        faithfulness = 0.3

        # Check response length - too short responses are suspicious
        if len(response) < 20:
            return 0.1  # Very low score for too short responses
        elif len(response) > 100:
            faithfulness += 0.1  # Bonus for substantial responses

        # FIXED: Check if response actually uses context (substring matching)
        if contexts:
            context_usage = 0
            total_context_words = 0
            matched_words = 0

            for ctx in contexts:
                ctx_words = set(ctx.lower().split())
                response_words = set(response.lower().split())

                # Count word overlap
                overlap = ctx_words.intersection(response_words)
                matched_words += len(overlap)
                total_context_words += len(ctx_words)

                # Bonus if significant substring match (at least 10 chars)
                if len(ctx) > 10:
                    # Check for meaningful substring matches
                    ctx_lower = ctx.lower()
                    resp_lower = response.lower()
                    # Split into meaningful phrases (5+ words)
                    ctx_phrases = [' '.join(ctx_lower.split()[i:i+5])
                                  for i in range(len(ctx_lower.split()) - 4)]
                    for phrase in ctx_phrases:
                        if phrase in resp_lower:
                            context_usage += 1
                            break

            # Calculate context usage score
            if total_context_words > 0:
                usage_ratio = matched_words / total_context_words
                faithfulness += min(0.4, usage_ratio * 2.0)  # Up to 0.4 points

            # Bonus for using multiple contexts
            if context_usage > 0:
                faithfulness += min(0.2, context_usage * 0.1)

        # Boost if response contains specific details (numbers, dates, etc.)
        import re
        if re.search(r'\d+', response):  # Contains numbers
            faithfulness += 0.05

        # Check for dates/time references
        if re.search(r'\b(?:январь|февраль|март|апрель|май|июнь|июль|август|сентябрь|октябрь|ноябрь|декабрь|понедельник|вторник|среда|четверг|пятница|суббота|воскресенье)\b', response.lower()):
            faithfulness += 0.05

        # Penalty for generic responses
        generic_phrases = ['не знаю', 'не могу', 'извините', 'к сожалению']
        if any(phrase in response.lower() for phrase in generic_phrases):
            faithfulness -= 0.2

        result = max(0.0, min(1.0, faithfulness))
        logger.debug(f"Heuristic faithfulness: {result:.3f}")
        return result

    def _calculate_heuristic_context_precision(
        self,
        query: str,
        response: str,
        contexts: List[str]
    ) -> float:
        """
        Calculate heuristic context precision score without LLM calls

        Context precision measures how relevant the retrieved contexts are to the query.
        """
        if not contexts:
            return 0.0

        # FIXED: Start with lower base score - contexts must prove relevance
        context_precision = 0.4

        # FIXED: Check number of contexts (more isn't always better)
        # Optimal: 3-5 contexts
        num_contexts = len(contexts)
        if num_contexts >= 5:
            context_precision += 0.2  # Check LARGER value first!
        elif num_contexts >= 3:
            context_precision += 0.15
        elif num_contexts >= 1:
            context_precision += 0.1
        else:
            return 0.0  # No contexts

        # Calculate relevance of contexts to query
        query_words = set(query.lower().split())
        # Remove stop words for better matching
        stop_words = {'и', 'в', 'на', 'с', 'по', 'для', 'как', 'что', 'а', 'но', 'или'}
        query_words = query_words - stop_words

        if not query_words:
            return context_precision  # Can't judge without meaningful query words

        relevant_contexts = 0
        total_relevance = 0.0

        for ctx in contexts:
            ctx_words = set(ctx.lower().split()) - stop_words

            # Calculate Jaccard similarity
            intersection = query_words.intersection(ctx_words)
            union = query_words.union(ctx_words)

            if len(union) > 0:
                relevance = len(intersection) / len(union)
                total_relevance += relevance

                # Consider context relevant if at least 10% overlap
                if relevance > 0.1:
                    relevant_contexts += 1

        # Calculate average relevance
        if num_contexts > 0:
            avg_relevance = total_relevance / num_contexts
            context_precision += min(0.3, avg_relevance * 3.0)  # Up to 0.3 points

        # Bonus for having multiple relevant contexts
        if relevant_contexts > 0:
            relevance_ratio = relevant_contexts / num_contexts
            context_precision += min(0.1, relevance_ratio * 0.2)

        result = min(1.0, context_precision)
        logger.debug(f"Heuristic context precision: {result:.3f} ({relevant_contexts}/{num_contexts} relevant)")
        return result

    def _calculate_fallback_scores(
        self,
        query: str,
        response: str,
        contexts: List[str]
    ) -> Dict[str, float]:
        """
        Calculate fallback scores using improved heuristics

        This is used when RAGAS evaluation is disabled or fails.
        """
        # Use improved heuristic methods
        faithfulness = self._calculate_heuristic_faithfulness(query, response, contexts)
        context_precision = self._calculate_heuristic_context_precision(query, response, contexts)

        # Answer relevancy: how well response addresses the query
        answer_relevancy = 0.3  # Lower base score

        # Check if response is substantial
        if len(response) > 100:
            answer_relevancy += 0.2
        elif len(response) > 50:
            answer_relevancy += 0.1

        # Check if query terms appear in response
        query_words = set(query.lower().split())
        response_words = set(response.lower().split())

        # Remove stop words
        stop_words = {'и', 'в', 'на', 'с', 'по', 'для', 'как', 'что', 'а', 'но', 'или'}
        query_words = query_words - stop_words

        if query_words:
            overlap = query_words.intersection(response_words)
            relevance = len(overlap) / len(query_words)
            answer_relevancy += min(0.4, relevance * 0.8)  # Up to 0.4 points

        # Penalty for generic/evasive responses
        generic_phrases = ['не могу помочь', 'не знаю', 'извините', 'недостаточно информации']
        if any(phrase in response.lower() for phrase in generic_phrases):
            answer_relevancy -= 0.2

        # Bonus for specific, actionable content
        if any(word in response.lower() for word in ['api', 'метод', 'настройка', 'конфигурация', 'использовать']):
            answer_relevancy += 0.1

        answer_relevancy = max(0.0, min(1.0, answer_relevancy))

        scores = {
            'faithfulness': faithfulness,
            'context_precision': context_precision,
            'answer_relevancy': answer_relevancy,
            'overall_score': (faithfulness + context_precision + answer_relevancy) / 3.0
        }

        logger.debug(
            f"Heuristic scores: faithfulness={faithfulness:.3f}, "
            f"context_precision={context_precision:.3f}, "
            f"answer_relevancy={answer_relevancy:.3f}, "
            f"overall={scores['overall_score']:.3f}"
        )

        return scores

# Global instance
ragas_evaluator = RAGASEvaluatorWithoutGroundTruth()
