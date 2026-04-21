"""Test model connectivity."""

import asyncio
import requests

def test_embedding_connection():
    """Test embedding endpoint."""
    base_url = "http://maas1.ehuidata.com:30067/openai/v1"
    model = "Qwen3-Embedding-8B"
    api_key = "b26378be9e4055e12295fbb6136d35a9397b84a5_2037743140575162369"
    
    url = f"{base_url}/embeddings"
    payload = {
        "model": model,
        "input": ["Hello, world"]
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        print(f"Testing embedding endpoint: {url}")
        print(f"Model: {model}")
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response data: {data}")
            print("Embedding connection SUCCESS")
            return True
        else:
            print(f"Error: {response.text}")
            print("Embedding connection FAILED")
            return False
    except Exception as e:
        print(f"Exception: {e}")
        print("Embedding connection FAILED")
        return False


def test_chat_completion():
    """Test chat completion endpoint."""
    base_url = "http://maas1.ehuidata.com:30067/openai/v1"
    model = "MiniMax-M2.5"
    api_key = "d053072f25b669a5c57a1e04daad3ec5a0781f8f_2037743140575162369"
    
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "Hello"}
        ],
        "max_tokens": 50
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        print(f"\nTesting chat completion endpoint: {url}")
        print(f"Model: {model}")
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {data}")
            print("Chat completion connection SUCCESS")
            return True
        else:
            print(f"Error: {response.text}")
            print("Chat completion connection FAILED")
            return False
    except Exception as e:
        print(f"Exception: {e}")
        print("Chat completion connection FAILED")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("Testing Model Connectivity")
    print("=" * 50)
    
    embedding_ok = test_embedding_connection()
    chat_ok = test_chat_completion()
    
    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)
    print(f"Embedding: {'OK' if embedding_ok else 'FAILED'}")
    print(f"Chat Completion: {'OK' if chat_ok else 'FAILED'}")
