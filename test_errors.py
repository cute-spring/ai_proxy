#!/usr/bin/env python3
"""
Error handling test script for OpenAI API Proxy
Tests various error scenarios and edge cases
"""

import os
import sys
import json
import requests
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:4000"
MASTER_KEY = os.getenv("MASTER_KEY", "sk-1234")
INVALID_KEY = "invalid-key-123"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {MASTER_KEY}"
}

def test_authentication_errors():
    """Test authentication error scenarios"""
    print("🧪 Testing authentication errors...")
    
    # Test 1: No authorization header
    print("   Testing missing authorization header...")
    try:
        response = requests.get(f"{BASE_URL}/models", headers={"Content-Type": "application/json"})
        if response.status_code == 401:
            print("     ✅ Correctly rejected missing auth header")
        else:
            print(f"     ❌ Expected 401, got {response.status_code}")
            return False
    except Exception as e:
        print(f"     ❌ Request failed: {e}")
        return False
    
    # Test 2: Invalid authorization header format
    print("   Testing invalid auth header format...")
    try:
        response = requests.get(f"{BASE_URL}/models", headers={
            "Content-Type": "application/json",
            "Authorization": "InvalidFormat"
        })
        if response.status_code == 401:
            print("     ✅ Correctly rejected invalid auth format")
        else:
            print(f"     ❌ Expected 401, got {response.status_code}")
            return False
    except Exception as e:
        print(f"     ❌ Request failed: {e}")
        return False
    
    # Test 3: Invalid API key
    print("   Testing invalid API key...")
    try:
        response = requests.get(f"{BASE_URL}/models", headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {INVALID_KEY}"
        })
        if response.status_code == 401:
            print("     ✅ Correctly rejected invalid API key")
        else:
            print(f"     ❌ Expected 401, got {response.status_code}")
            return False
    except Exception as e:
        print(f"     ❌ Request failed: {e}")
        return False
    
    return True

def test_invalid_requests():
    """Test invalid request scenarios"""
    print("\n🧪 Testing invalid requests...")
    
    # Test 1: Invalid JSON
    print("   Testing invalid JSON...")
    try:
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=HEADERS,
            data="{invalid json",  # Malformed JSON
            timeout=5
        )
        if response.status_code == 422:
            print("     ✅ Correctly rejected invalid JSON")
        else:
            print(f"     ❌ Expected 422, got {response.status_code}")
            return False
    except Exception as e:
        print(f"     ❌ Request failed: {e}")
        return False
    
    # Test 2: Missing required fields
    print("   Testing missing required fields...")
    try:
        payload = {
            "temperature": 0.7
            # Missing 'model' and 'messages'
        }
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=HEADERS,
            json=payload,
            timeout=5
        )
        if response.status_code == 422:
            print("     ✅ Correctly rejected missing required fields")
        else:
            print(f"     ❌ Expected 422, got {response.status_code}")
            return False
    except Exception as e:
        print(f"     ❌ Request failed: {e}")
        return False
    
    # Test 3: Empty messages array
    print("   Testing empty messages array...")
    try:
        payload = {
            "model": "gpt-4o",
            "messages": []  # Empty array
        }
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=HEADERS,
            json=payload,
            timeout=5
        )
        if response.status_code == 400:
            print("     ✅ Correctly rejected empty messages")
        else:
            print(f"     ❌ Expected 400, got {response.status_code}")
            return False
    except Exception as e:
        print(f"     ❌ Request failed: {e}")
        return False
    
    return True

def test_nonexistent_endpoints():
    """Test non-existent endpoints"""
    print("\n🧪 Testing non-existent endpoints...")
    
    # Test 1: Non-existent endpoint
    print("   Testing non-existent endpoint...")
    try:
        response = requests.get(
            f"{BASE_URL}/nonexistent",
            headers=HEADERS,
            timeout=5
        )
        if response.status_code == 404:
            print("     ✅ Correctly returned 404 for non-existent endpoint")
        else:
            print(f"     ❌ Expected 404, got {response.status_code}")
            return False
    except Exception as e:
        print(f"     ❌ Request failed: {e}")
        return False
    
    # Test 2: Invalid method on existing endpoint
    print("   Testing invalid HTTP method...")
    try:
        response = requests.put(
            f"{BASE_URL}/chat/completions",
            headers=HEADERS,
            timeout=5
        )
        if response.status_code == 405:
            print("     ✅ Correctly returned 405 for invalid method")
        else:
            print(f"     ❌ Expected 405, got {response.status_code}")
            return False
    except Exception as e:
        print(f"     ❌ Request failed: {e}")
        return False
    
    return True

def test_rate_limiting():
    """Test rate limiting behavior"""
    print("\n🧪 Testing rate limiting...")
    
    # Send multiple rapid requests
    print("   Testing multiple rapid requests...")
    
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "Hello"}
        ],
        "max_tokens": 5
    }
    
    responses = []
    
    try:
        for i in range(5):  # Send 5 rapid requests
            response = requests.post(
                f"{BASE_URL}/chat/completions",
                headers=HEADERS,
                json=payload,
                timeout=10
            )
            responses.append(response.status_code)
    except Exception as e:
        print(f"     ❌ Request failed: {e}")
        return False
    
    # Check if all requests succeeded (or if some were rate limited)
    success_count = sum(1 for code in responses if code == 200)
    rate_limited_count = sum(1 for code in responses if code == 429)
    
    print(f"     Requests: {len(responses)}, Success: {success_count}, Rate limited: {rate_limited_count}")
    
    if success_count > 0:
        print("     ✅ Some requests succeeded (rate limiting may be configured)")
        return True
    else:
        print("     ⚠️  All requests failed - check if rate limiting is too aggressive")
        return False

def test_invalid_model():
    """Test requests with invalid model names"""
    print("\n🧪 Testing invalid model names...")
    
    payload = {
        "model": "nonexistent-model-123",
        "messages": [
            {"role": "user", "content": "Hello"}
        ]
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=HEADERS,
            json=payload,
            timeout=10
        )
        
        # Could be 400, 404, or 503 depending on implementation
        if response.status_code in [400, 404, 503]:
            print(f"     ✅ Correctly rejected invalid model (HTTP {response.status_code})")
            return True
        else:
            print(f"     ❌ Expected 400/404/503, got {response.status_code}")
            return False
            
    except Exception as e:
        print(f"     ❌ Request failed: {e}")
        return False

def test_large_requests():
    """Test requests with large payloads"""
    print("\n🧪 Testing large requests...")
    
    # Create a large message content
    large_content = "A" * 10000  # 10KB of text
    
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": large_content}
        ],
        "max_tokens": 10
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=HEADERS,
            json=payload,
            timeout=30  # Longer timeout for large requests
        )
        
        if response.status_code == 200:
            print("     ✅ Large request accepted")
            return True
        elif response.status_code == 413:
            print("     ✅ Large request correctly rejected (413 Payload Too Large)")
            return True
        else:
            print(f"     ❌ Unexpected status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"     ❌ Request failed: {e}")
        return False

def main():
    """Run all error handling tests"""
    print("🚀 Starting Error Handling Tests")
    print("=" * 60)
    
    tests = [
        test_authentication_errors,
        test_invalid_requests,
        test_nonexistent_endpoints,
        test_rate_limiting,
        test_invalid_model,
        test_large_requests
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print("-" * 60)
    
    print("📊 Error Handling Test Results:")
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    
    if passed == total:
        print("🎉 All error handling tests passed!")
        return 0
    else:
        print("💥 Some error handling tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())