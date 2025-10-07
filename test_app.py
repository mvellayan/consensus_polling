#!/usr/bin/env python3

import os
import requests
import time

def test_local_app():
    """Test the app locally before deployment"""
    print("🧪 Testing Flask app locally...")
    
    # Set environment variable for testing
    os.environ['OPENAI_API_KEY'] = 'test-key'
    
    try:
        # Import and test basic functionality
        from app import app
        
        with app.test_client() as client:
            # Test health endpoint
            response = client.get('/health')
            print(f"Health check: {response.status_code} - {response.get_json()}")
            
            # Test judges endpoint
            response = client.get('/api/judges')
            print(f"Judges API: {response.status_code} - {len(response.get_json())} judges")
            
            # Test main page
            response = client.get('/')
            print(f"Main page: {response.status_code}")
            
        print("✅ Local tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Local test failed: {e}")
        return False

if __name__ == "__main__":
    test_local_app()
