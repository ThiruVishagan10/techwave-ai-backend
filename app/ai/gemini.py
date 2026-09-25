import logging
import json
import numpy as np
from typing import Optional, Any, Dict, List, Type
from pydantic import BaseModel
from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger(__name__)


class GeminiService:
    def __init__(self):
        self._client: Optional[genai.Client] = None
        self._init_client()

    def _init_client(self):
        if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip():
            try:
                self._client = genai.Client(api_key=settings.GEMINI_API_KEY.strip())
                logger.info(f"Initialized Google GenAI client with model {settings.GEMINI_MODEL}")
            except Exception as e:
                logger.warning(f"Failed to initialize Google GenAI Client: {e}")
                self._client = None
        else:
            logger.info("GEMINI_API_KEY not set. Operating in resilient demo/rule-based fallback mode.")
            self._client = None

    @property
    def is_available(self) -> bool:
        return self._client is not None

    async def generate_structured(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        response_schema: Optional[Type[BaseModel]] = None,
        model: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate structured JSON using Gemini API."""
        if not self.is_available:
            return None

        target_model = model or settings.GEMINI_MODEL
        try:
            config_args = {
                "response_mime_type": "application/json",
            }
            if response_schema:
                config_args["response_schema"] = response_schema
            if system_instruction:
                config_args["system_instruction"] = system_instruction

            config = types.GenerateContentConfig(**config_args)

            # google-genai client.models.generate_content is synchronous, or we can use async or run in thread
            # in google-genai 2.x, client.aio.models.generate_content exists for async!
            if hasattr(self._client, "aio") and hasattr(self._client.aio, "models"):
                response = await self._client.aio.models.generate_content(
                    model=target_model,
                    contents=prompt,
                    config=config,
                )
            else:
                response = self._client.models.generate_content(
                    model=target_model,
                    contents=prompt,
                    config=config,
                )

            if response and response.text:
                return json.loads(response.text)
            return None
        except Exception as e:
            logger.error(f"Gemini API structured call failed ({target_model}): {e}")
            return None

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Generate text embedding using Gemini."""
        if not self.is_available or not text.strip():
            return None

        try:
            model = settings.GEMINI_EMBEDDING_MODEL
            if hasattr(self._client, "aio") and hasattr(self._client.aio, "models"):
                response = await self._client.aio.models.embed_content(
                    model=model,
                    contents=text,
                )
            else:
                response = self._client.models.embed_content(
                    model=model,
                    contents=text,
                )

            if response and hasattr(response, "embedding") and response.embedding:
                # response.embedding.values
                if hasattr(response.embedding, "values"):
                    return list(response.embedding.values)
                elif isinstance(response.embedding, list):
                    return response.embedding
            return None
        except Exception as e:
            logger.warning(f"Gemini embedding call failed: {e}")
            return None

    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        try:
            a = np.array(vec1, dtype=float)
            b = np.array(vec2, dtype=float)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return float(np.dot(a, b) / (norm_a * norm_b))
        except Exception:
            return 0.0


gemini_service = GeminiService()
