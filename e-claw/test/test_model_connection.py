"""测试模型连通性"""
import requests
import json
import sys

# MiniMax LLM 配置
MINIMAX_API_KEY = "d053072f25b669a5c57a1e04daad3ec5a0781f8f_2037743140575162369"
MINIMAX_MODEL = "MiniMax-M2.5"
MINIMAX_BASE_URL = "http://maas1.ehuidata.com:30067/openai/v1"

# Embedding 配置
EMBEDDING_API_KEY = "b26378be9e4055e12295fbb6136d35a9397b84a5_2037743140575162369"
EMBEDDING_MODEL = "Qwen3-Embedding-8B"
EMBEDDING_BASE_URL = "http://maas1.ehuidata.com:30067/openai/v1"


def test_llm_connection():
    """测试 LLM 模型连通性"""
    print("\n" + "="*50)
    print("测试 LLM (MiniMax) 连通性...")
    print("="*50)
    
    url = f"{MINIMAX_BASE_URL}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MINIMAX_API_KEY}"
    }
    
    # 解析 API key 中的 group_id
    api_key = MINIMAX_API_KEY
    group_id = ""
    if "/" in api_key:
        parts = api_key.split("/")
        api_key = parts[0]
        group_id = parts[1] if len(parts) > 1 else ""
    
    payload = {
        "model": MINIMAX_MODEL,
        "messages": [
            {"role": "user", "content": "你好，请用一句话介绍自己"}
        ],
        "temperature": 0.7,
        "max_tokens": 100
    }
    
    if group_id:
        payload["group_id"] = group_id
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
            return True
        else:
            print(f"错误: {response.text}")
            return False
    except requests.exceptions.Timeout:
        print("连接超时!")
        return False
    except requests.exceptions.ConnectionError:
        print("无法连接到服务器!")
        return False
    except Exception as e:
        print(f"错误: {e}")
        return False


def test_embedding_connection():
    """测试 Embedding 模型连通性"""
    print("\n" + "="*50)
    print("测试 Embedding (Qwen3) 连通性...")
    print("="*50)
    
    url = f"{EMBEDDING_BASE_URL}/embeddings"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {EMBEDDING_API_KEY}"
    }
    
    payload = {
        "model": EMBEDDING_MODEL,
        "input": ["你好，这是一个测试"]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            embedding_dim = len(data["data"][0]["embedding"])
            print(f"Embedding 维度: {embedding_dim}")
            print(f"前5个值: {data['data'][0]['embedding'][:5]}")
            return True
        else:
            print(f"错误: {response.text}")
            return False
    except requests.exceptions.Timeout:
        print("连接超时!")
        return False
    except requests.exceptions.ConnectionError:
        print("无法连接到服务器!")
        return False
    except Exception as e:
        print(f"错误: {e}")
        return False


def main():
    print("模型连通性测试")
    print("="*50)
    print(f"LLM 地址: {MINIMAX_BASE_URL}")
    print(f"LLM 模型: {MINIMAX_MODEL}")
    print(f"Embedding 地址: {EMBEDDING_BASE_URL}")
    print(f"Embedding 模型: {EMBEDDING_MODEL}")
    
    # 测试 LLM
    llm_result = test_llm_connection()
    
    # 测试 Embedding
    embedding_result = test_embedding_connection()
    
    # 汇总结果
    print("\n" + "="*50)
    print("测试结果汇总")
    print("="*50)
    print(f"LLM (MiniMax) 连通性: {'✓ 成功' if llm_result else '✗ 失败'}")
    print(f"Embedding (Qwen3) 连通性: {'✓ 成功' if embedding_result else '✗ 失败'}")
    
    if llm_result and embedding_result:
        print("\n所有模型连通性测试通过!")
        return 0
    else:
        print("\n部分模型连通性测试失败!")
        return 1


if __name__ == "__main__":
    sys.exit(main())