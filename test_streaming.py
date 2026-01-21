#!/usr/bin/env python3
"""
Advanced streaming test script for OpenAI API Proxy
Tests various streaming scenarios and edge cases
"""

import os
import sys
import json
import requests
import time
from typing import Dict, Any, List

# Configuration
BASE_URL = "http://localhost:4000"
MASTER_KEY = os.getenv("MASTER_KEY", "sk-1234")
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {MASTER_KEY}"
}

def test_basic_streaming():
    """Test basic streaming functionality"""
    print("🧪 Testing basic streaming...")
    
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "Tell me a short story about a robot learning to dance."}
        ],
        "temperature": 0.7,
        "max_tokens": 200,
        "stream": True
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=HEADERS,
            json=payload,
            stream=True
        )
        response.raise_for_status()
        
        print("✅ Streaming connection established")
        
        chunks = []
        start_time = time.time()
        
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data_str = line_str[6:]  # Remove 'data: ' prefix
                    
                    if data_str == '[DONE]':
                        end_time = time.time()
                        duration = end_time - start_time
                        print(f"🏁 Stream completed in {duration:.2f}s")
                        break
                    
                    try:
                        data = json.loads(data_str)
                        chunks.append(data)
                        
                        if 'choices' in data and len(data['choices']) > 0:
                            delta = data['choices'][0].get('delta', {})
                            if 'content' in delta and delta['content']:
                                print(f"💬 {delta['content']}", end='', flush=True)
                                
                    except json.JSONDecodeError as e:
                        print(f"❌ JSON decode error: {e}")
                        continue
        
        # Analyze the stream
        print(f"\n📊 Stream analysis:")
        print(f"   Total chunks: {len(chunks)}")
        
        content_chunks = [c for c in chunks if 'choices' in c and c['choices'] and 'content' in c['choices'][0].get('delta', {})]
        print(f"   Content chunks: {len(content_chunks)}")
        
        if chunks:
            first_chunk = chunks[0]
            print(f"   First chunk ID: {first_chunk.get('id', 'unknown')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Streaming test failed: {e}")
        return False

def test_streaming_with_different_models():
    """Test streaming with different models"""
    print("\n🧪 Testing streaming with different models...")
    
    models_to_test = ["gpt-4o", "gpt-4-turbo"]  # Add Azure models if configured
    
    results = {}
    
    for model in models_to_test:
        print(f"   Testing model: {model}")
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": "What is 2 + 2?"}
            ],
            "temperature": 0.1,  # Low temperature for consistent output
            "max_tokens": 50,
            "stream": True
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/chat/completions",
                headers=HEADERS,
                json=payload,
                stream=True,
                timeout=30  # Add timeout for streaming
            )
            response.raise_for_status()
            
            chunks = []
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]
                        if data_str == '[DONE]':
                            break
                        try:
                            data = json.loads(data_str)
                            chunks.append(data)
                        except:
                            continue
            
            results[model] = {
                "success": True,
                "chunks": len(chunks),
                "has_content": any('choices' in c and c['choices'] and 'content' in c['choices'][0].get('delta', {}) for c in chunks)
            }
            
            print(f"     ✅ {model}: {len(chunks)} chunks")
            
        except Exception as e:
            print(f"     ❌ {model}: {e}")
            results[model] = {"success": False, "error": str(e)}
    
    return all(result["success"] for result in results.values())

def test_streaming_performance():
    """Test streaming performance metrics"""
    print("\n🧪 Testing streaming performance...")
    
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "Count from 1 to 10 with each number on a new line."}
        ],
        "temperature": 0.1,
        "max_tokens": 100,
        "stream": True
    }
    
    try:
        start_time = time.time()
        
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=HEADERS,
            json=payload,
            stream=True
        )
        response.raise_for_status()
        
        first_chunk_time = None
        chunk_count = 0
        content_received = False
        
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data_str = line_str[6:]
                    
                    if first_chunk_time is None:
                        first_chunk_time = time.time()
                        time_to_first_chunk = first_chunk_time - start_time
                        print(f"   ⏱️  Time to first chunk: {time_to_first_chunk:.3f}s")
                    
                    chunk_count += 1
                    
                    if data_str == '[DONE]':
                        break
                    
                    try:
                        data = json.loads(data_str)
                        if 'choices' in data and data['choices'] and 'content' in data['choices'][0].get('delta', {}):
                            content_received = True
                    except:
                        continue
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        print(f"   📊 Performance metrics:")
        print(f"     Total duration: {total_duration:.2f}s")
        print(f"     Total chunks: {chunk_count}")
        print(f"     Content received: {content_received}")
        
        if chunk_count > 0 and content_received:
            return True
        else:
            print("❌ No content received in stream")
            return False
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        return False

def test_streaming_edge_cases():
    """Test streaming edge cases"""
    print("\n🧪 Testing streaming edge cases...")
    
    # Test 1: Very short prompt
    print("   Testing short prompt...")
    
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "Hi"}
        ],
        "stream": True
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=HEADERS,
            json=payload,
            stream=True
        )
        response.raise_for_status()
        
        chunks = []
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data_str = line_str[6:]
                    if data_str == '[DONE]':
                        break
                    try:
                        data = json.loads(data_str)
                        chunks.append(data)
                    except:
                        continue
        
        print(f"     Short prompt: {len(chunks)} chunks")
        
    except Exception as e:
        print(f"     ❌ Short prompt failed: {e}")
        return False
    
    # Test 2: Empty messages (should fail gracefully)
    print("   Testing empty messages...")
    
    payload = {
        "model": "gpt-4o",
        "messages": [],
        "stream": True
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=HEADERS,
            json=payload,
            stream=True
        )
        # This should fail with 400 error
        if response.status_code == 400:
            print("     ✅ Properly rejected empty messages")
        else:
            print(f"     ❌ Expected 400, got {response.status_code}")
            return False
            
    except Exception as e:
        print(f"     ❌ Empty messages test failed: {e}")
        return False
    
    return True

def test_streaming_with_openai_sdk():
    """Test streaming using the official OpenAI Python SDK"""
    print("\n🧪 Testing streaming with OpenAI Python SDK...")
    
    try:
        from openai import OpenAI
        
        client = OpenAI(
            base_url=BASE_URL,
            api_key=MASTER_KEY
        )
        
        stream = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": "Explain streaming in one sentence."}
            ],
            stream=True
        )
        
        print("     Streaming response:")
        full_response = ""
        
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                print(content, end='', flush=True)
                full_response += content
        
        print("\n     ✅ SDK streaming test passed")
        
        if len(full_response) > 0:
            return True
        else:
            print("❌ No content received")
            return False
        
    except ImportError:
        print("     ℹ️  OpenAI SDK not installed, skipping SDK test")
        return True  # Not a failure, just skip
    except Exception as e:
        print(f"     ❌ SDK streaming test failed: {e}")
        return False

def main():
    """Run all streaming tests"""
    print("🚀 Starting Streaming Tests")
    print("=" * 60)
    
    tests = [
        test_basic_streaming,
        test_streaming_with_different_models,
        test_streaming_performance,
        test_streaming_edge_cases,
        test_streaming_with_openai_sdk
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print("-" * 60)
    
    print("📊 Streaming Test Results:")
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    
    if passed == total:
        print("🎉 All streaming tests passed!")
        return 0
    else:
        print("💥 Some streaming tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())