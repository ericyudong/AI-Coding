"""LLM Service for handling multiple LLM providers."""

import os
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod
from loguru import logger

from backend.config import settings


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate a response from the LLM."""
        pass


class EmbeddingProvider(ABC):
    """Abstract base class for Embedding providers."""
    
    @abstractmethod
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding for text."""
        pass


class QwenEmbeddingProvider(EmbeddingProvider):
    """Qwen embedding provider using HTTP requests (OpenAI-compatible API)."""
    
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        import requests
        self.base_url = base_url or settings.embedding_base_url or "http://10.65.16.24:41213/v1"
        self.model = model or settings.embedding_model or "Qwen3-Embedding-8B"
        # Use embedding_api_key first, fallback to openai_api_key
        self.api_key = api_key or settings.embedding_api_key or os.environ.get("EMBEDDING_API_KEY") or settings.openai_api_key or os.environ.get("OPENAI_API_KEY") or ""
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        })
        logger.info(f"Qwen Embedding provider initialized with model: {self.model}, base_url: {self.base_url}")
    
    async def get_embedding(self, text: str) -> List[float]:
        import requests
        
        url = f"{self.base_url}/embeddings"
        payload = {
            "model": self.model,
            "input": [text]
        }
        
        try:
            response = self.session.post(url, json=payload, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            return data["data"][0]["embedding"]
        except Exception as e:
            logger.error(f"Qwen embedding error: {e}")
            raise


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Custom embedding provider using HTTP requests (OpenAI-compatible)."""
    
    def __init__(self, api_key: str = None, base_url: str = None):
        import requests
        self.base_url = base_url or settings.embedding_base_url or "https://api.openai.com/v1"
        self.model = settings.embedding_model
        # Use embedding_api_key first, fallback to openai_api_key
        self.api_key = api_key or settings.embedding_api_key or os.environ.get("EMBEDDING_API_KEY") or settings.openai_api_key or os.environ.get("OPENAI_API_KEY") or ""
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        })
        logger.info(f"Custom Embedding provider initialized with model: {self.model}, base_url: {self.base_url}")
    
    async def get_embedding(self, text: str) -> List[float]:
        import requests
        
        url = f"{self.base_url}/embeddings"
        payload = {
            "model": self.model,
            "input": [text]
        }
        
        response = self.session.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        return data["data"][0]["embedding"]


class GoogleEmbeddingProvider(EmbeddingProvider):
    """Google embedding provider."""
    
    def __init__(self):
        try:
            import google.generativeai as genai
            genai.configure(
                api_key=settings.google_api_key or os.environ.get("GOOGLE_API_KEY")
            )
            self.model = "models/embedding-001"
            logger.info(f"Google Embedding provider initialized with model: {self.model}")
        except ImportError:
            logger.error("Google Generative AI package not installed")
            raise
    
    async def get_embedding(self, text: str) -> List[float]:
        import google.generativeai as genai
        result = await genai.embed_content_async(
            model=self.model,
            content=text
        )
        return result["embedding"]


class OpenAILLMProvider(LLMProvider):
    """OpenAI LLM provider."""
    
    def __init__(self):
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(
                api_key=settings.openai_api_key or os.environ.get("OPENAI_API_KEY"),
                base_url=settings.openai_base_url
            )
            self.model = settings.openai_model
            logger.info(f"OpenAI provider initialized with model: {self.model}")
        except ImportError:
            logger.error("OpenAI package not installed")
            raise
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content


class AnthropicProvider(LLMProvider):
    """Anthropic LLM provider."""
    
    def __init__(self):
        try:
            import anthropic
            self.client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
            )
            self.model = settings.anthropic_model
            logger.info(f"Anthropic provider initialized with model: {self.model}")
        except ImportError:
            logger.error("Anthropic package not installed")
            raise
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        # Convert messages format for Anthropic
        system_message = ""
        anthropic_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                anthropic_messages.append(msg)
        
        response = await self.client.messages.create(
            model=self.model,
            system=system_message if system_message else None,
            messages=anthropic_messages,
            temperature=temperature,
            max_tokens=max_tokens or 4096
        )
        return response.content[0].text


class GoogleProvider(LLMProvider):
    """Google Gemini LLM provider."""
    
    def __init__(self):
        try:
            import google.generativeai as genai
            genai.configure(
                api_key=settings.google_api_key or os.environ.get("GOOGLE_API_KEY")
            )
            self.model = genai.GenerativeModel(settings.google_model)
            logger.info(f"Google provider initialized with model: {settings.google_model}")
        except ImportError:
            logger.error("Google Generative AI package not installed")
            raise
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        # Convert messages format for Gemini
        chat = self.model.start_chat(history=[])
        
        # Find the last user message
        last_user_msg = None
        for msg in reversed(messages):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break
        
        if not last_user_msg:
            raise ValueError("No user message found")
        
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens
        }
        
        response = await chat.send_message_async(
            last_user_msg,
            generation_config=generation_config
        )
        return response.text


class MiniMaxProvider(LLMProvider):
    """MiniMax LLM provider."""
    
    def __init__(self):
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(
                api_key=settings.minimax_api_key or os.environ.get("MINIMAX_API_KEY"),
                base_url=settings.minimax_base_url
            )
            self.model = settings.minimax_model
            # Extract group ID from API key for MiniMax
            api_key = settings.minimax_api_key or os.environ.get("MINIMAX_API_KEY", "")
            # MiniMax API key format: api_key/group_id
            self.group_id = ""
            if "/" in api_key:
                parts = api_key.split("/")
                self.client.api_key = parts[0]
                self.group_id = parts[1] if len(parts) > 1 else ""
            logger.info(f"MiniMax provider initialized with model: {self.model}")
        except ImportError:
            logger.error("OpenAI package not installed")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize MiniMax: {e}")
            raise
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        # MiniMax uses a different format
        # Convert messages to MiniMax format
        minimax_messages = []
        for msg in messages:
            role = msg["role"]
            # Map roles: system -> system, user -> user, assistant -> assistant
            if role == "system":
                role = "system"
            elif role == "user":
                role = "user"
            elif role == "assistant":
                role = "assistant"
            minimax_messages.append({
                "role": role,
                "content": msg["content"]
            })
        
        # Make API call
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=minimax_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body={
                    "group_id": self.group_id
                } if self.group_id else {}
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"MiniMax API error: {e}")
            raise


class LLMService:
    """Service for managing LLM interactions."""
    
    def __init__(self):
        self.provider: Optional[LLMProvider] = None
        self.embedding_provider: Optional[EmbeddingProvider] = None
    
    def _ensure_provider(self):
        """Lazy initialize the LLM provider."""
        if self.provider is None:
            self._initialize_provider()
    
    def _ensure_embedding_provider(self):
        """Lazy initialize the embedding provider."""
        if self.embedding_provider is None:
            self._initialize_embedding_provider()
    
    def _initialize_provider(self):
        """Initialize the LLM provider based on configuration."""
        provider_name = settings.llm_provider.lower()
        
        if provider_name == "openai":
            self.provider = OpenAILLMProvider()
        elif provider_name == "anthropic":
            self.provider = AnthropicProvider()
        elif provider_name == "google":
            self.provider = GoogleProvider()
        elif provider_name == "minimax":
            self.provider = MiniMaxProvider()
        else:
            raise ValueError(f"Unknown LLM provider: {provider_name}")
        
        logger.info(f"LLM Service initialized with provider: {provider_name}")
    
    def _initialize_embedding_provider(self):
        """Initialize the embedding provider based on configuration."""
        # Check for Qwen embedding model first (most common case for local models)
        embedding_model = settings.embedding_model or ""
        if "qwen" in embedding_model.lower() or "embedding" in embedding_model.lower():
            self.embedding_provider = QwenEmbeddingProvider()
            logger.info(f"Embedding Service initialized with provider: Qwen (model: {settings.embedding_model})")
        # Use Google if explicitly configured
        elif settings.google_api_key or os.environ.get("GOOGLE_API_KEY"):
            self.embedding_provider = GoogleEmbeddingProvider()
            logger.info("Embedding Service initialized with provider: google")
        else:
            # Default to custom HTTP-based embedding provider (OpenAI-compatible)
            self.embedding_provider = OpenAIEmbeddingProvider()
            logger.info("Embedding Service initialized with provider: custom (HTTP)")
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate a response using the configured LLM provider."""
        self._ensure_provider()
        return await self.provider.generate(messages, temperature, max_tokens)
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding for text using the configured embedding provider."""
        self._ensure_embedding_provider()
        return await self.embedding_provider.get_embedding(text)


# Global instance (lazy)
llm_service = LLMService()
