#!/usr/bin/env python3
"""
Basic test script for OpenAI API Proxy
Tests all major endpoints with both OpenAI and Azure OpenAI
"""

import os
import sys
import json
import requests
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:4000"
MASTER_KEY = os.getenv("MASTER_KEY", "sk-1234")
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {MASTER_KEY}"
}

def test_health_check():
    """Test health check endpoint"""
    print("🧪 Testing health check...")
    
    try:
        response = requests.get(f"{BASE_URL}/health/readiness")
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Health check passed: {data}")
        return True
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_list_models():
    """Test models listing endpoint"""
    print("\n🧪 Testing models endpoint...")
    
    try:
        response = requests.get(f"{BASE_URL}/models", headers=HEADERS)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Models retrieved: {len(data.get('data', []))} models")
        
        # Print available models
        for model in data.get('data', []):
            print(f"   - {model['id']} ({model['owned_by']})")
        
        return True
        
    except Exception as e:
        print(f"❌ Models endpoint failed: {e}")
        return False

def test_chat_completion(model: str, stream: bool = False):
    """Test chat completion endpoint"""
    print(f"\n🧪 Testing chat completion ({model}, stream={stream})...")
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello! Can you introduce yourself in one sentence?"}
        ],
        "temperature": 0.7,
        "max_tokens": 100,
        "stream": stream
    }
    
    try:
        if stream:
            # For streaming, we need to handle the SSE response differently
            response = requests.post(
                f"{BASE_URL}/chat/completions",
                headers=HEADERS,
                json=payload,
                stream=True
            )
            response.raise_for_status()
            
            print("✅ Streaming response received:")
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]  # Remove 'data: ' prefix
                        if data_str == '[DONE]':
                            print("   🏁 Stream completed")
                            break
                        try:
                            data = json.loads(data_str)
                            if 'choices' in data and len(data['choices']) > 0:
                                delta = data['choices'][0].get('delta', {})
                                if 'content' in delta and delta['content']:
                                    print(f"   💬 {delta['content']}", end='', flush=True)
                        except json.JSONDecodeError:
                            continue
            print("\n✅ Streaming test passed")
            return True
            
        else:
            # Non-streaming
            response = requests.post(
                f"{BASE_URL}/chat/completions",
                headers=HEADERS,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            if 'choices' in data and len(data['choices']) > 0:
                message = data['choices'][0]['message']
                print(f"✅ Response: {message['content']}")
                return True
            else:
                print("❌ No choices in response")
                return False
                
    except Exception as e:
        print(f"❌ Chat completion failed: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"   Response: {e.response.text}")
        return False

def test_completions():
    """Test text completions endpoint"""
    print("\n🧪 Testing text completions...")
    
    payload = {
        "model": "gpt-4o",  # Use a model that supports completions
        "prompt": "Once upon a time",
        "temperature": 0.7,
        "max_tokens": 50
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/completions",
            headers=HEADERS,
            json=payload
        )
        response.raise_for_status()
        
        data = response.json()
        if 'choices' in data and len(data['choices']) > 0:
            text = data['choices'][0]['text']
            print(f"✅ Completion: {text}")
            return True
        else:
            print("❌ No choices in response")
            return False
            
    except Exception as e:
        print(f"❌ Completions failed: {e}")
        return False

def test_embeddings():
    """Test embeddings endpoint"""
    print("\n🧪 Testing embeddings...")
    
    payload = {
        "model": "text-embedding-ada-002",  # Use embedding model
        "input": "Hello world"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/embeddings",
            headers=HEADERS,
            json=payload
        )
        response.raise_for_status()
        
        data = response.json()
        if 'data' in data and len(data['data']) > 0:
            embedding = data['data'][0]['embedding']
            print(f"✅ Embedding generated: {len(embedding)} dimensions")
            return True
        else:
            print("❌ No embedding data")
            return False
            
    except Exception as e:
        print(f"❌ Embeddings failed: {e}")
        return False

def test_root_endpoint():
    """Test root endpoint"""
    print("\n🧪 Testing root endpoint...")
    
    try:
        response = requests.get(f"{BASE_URL}/")
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Root endpoint: {data.get('name', 'Unknown')} v{data.get('version', '?')}")
        print(f"   Supported providers: {data.get('supported_providers', {})}")
        return True
        
    except Exception as e:
        print(f"❌ Root endpoint failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting OpenAI API Proxy Tests")
    print("=" * 50)
    
    # Check if server is running
    print("📡 Testing connection to proxy server...")
    
    tests = [
        test_health_check,
        test_root_endpoint,
        test_list_models,
        lambda: test_chat_completion("gpt-4o", False),  # Non-streaming
        lambda: test_chat_completion("gpt-4o", True),   # Streaming
        test_completions,
        # test_embeddings  # Temporarily disabled
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print("-" * 50)
    
    print("📊 Test Results:")
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("💥 Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())