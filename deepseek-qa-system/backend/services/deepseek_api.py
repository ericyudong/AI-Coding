"""DeepSeek API Service - handles all interactions with DeepSeek API."""
import httpx
import json
import logging
from typing import List, Dict, Any
from backend.config import get_settings
from backend.models import Message

logger = logging.getLogger(__name__)


class DeepSeekAPI:
    """Service for interacting with DeepSeek API."""
    
    def __init__(self):
        """Initialize DeepSeek API service."""
        self.settings = get_settings()
        self.client = httpx.AsyncClient(
            base_url=self.settings.deepseek_base_url,
            headers={
                "Authorization": f"Bearer {self.settings.deepseek_api_key}",
                "Content-Type": "application/json"
            }
        )
    
    async def chat(self, messages: List[Message], system_prompt: str = None) -> str:
        """
        Send a chat request to DeepSeek API.
        
        Args:
            messages: List of Message objects in conversation history
            system_prompt: Optional system prompt to set conversation context
            
        Returns:
            The assistant's response text
            
        Raises:
            httpx.HTTPError: If the API request fails
        """
        try:
            # Convert Message objects to API format
            message_list = []
            
            if system_prompt:
                message_list.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            for msg in messages:
                message_list.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # Prepare request payload
            payload = {
                "model": self.settings.deepseek_model,
                "messages": message_list,
                "temperature": 0.7,
                "top_p": 0.95,
                "max_tokens": 2048
            }
            
            logger.debug(f"Sending request to DeepSeek API with {len(messages)} messages")
            
            # Send request to DeepSeek API
            response = await self.client.post(
                "/chat/completions",
                json=payload,
                timeout=30.0
            )
            
            # Handle response
            if response.status_code != 200:
                logger.error(f"API error: {response.status_code} - {response.text}")
                raise Exception(f"API returned status {response.status_code}")
            
            data = response.json()
            
            # Extract message from response
            if "choices" in data and len(data["choices"]) > 0:
                message_content = data["choices"][0]["message"]["content"]
                logger.debug("Successfully received response from DeepSeek API")
                return message_content
            else:
                logger.error(f"Unexpected API response format: {data}")
                raise Exception("Invalid response format from API")
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error while calling DeepSeek API: {str(e)}")
            raise Exception(f"Failed to communicate with DeepSeek API: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse API response: {str(e)}")
            raise Exception("Invalid JSON response from API")
        except Exception as e:
            logger.error(f"Unexpected error in DeepSeek API call: {str(e)}")
            raise
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Global instance
_deepseek_api = None


async def get_deepseek_api() -> DeepSeekAPI:
    """Get or create DeepSeek API instance."""
    global _deepseek_api
    if _deepseek_api is None:
        _deepseek_api = DeepSeekAPI()
    return _deepseek_api
