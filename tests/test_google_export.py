#!/usr/bin/env python3
"""
Quick test script for Google Docs Export endpoint.

Usage:
    python test_google_export.py <job_id>

Example:
    python test_google_export.py abc-123-def-456
"""

import sys
import requests
import json

def test_google_export(job_id: str, backend_url: str = "http://localhost:8000"):
    """Test the Google Docs export endpoint."""
    
    print(f"\n{'='*60}")
    print(f"Testing Google Docs Export")
    print(f"{'='*60}")
    print(f"Job ID: {job_id}")
    print(f"Backend URL: {backend_url}")
    print()
    
    # Step 1: Check job status
    print("Step 1: Checking job status...")
    try:
        status_response = requests.get(f"{backend_url}/jobs/{job_id}/status")
        if status_response.status_code == 200:
            job_data = status_response.json()
            print(f"✅ Job found: {job_data.get('status', 'unknown')}")
            print(f"   File: {job_data.get('file_name', 'unknown')}")
        else:
            print(f"❌ Job not found or error: {status_response.status_code}")
            print(f"   Response: {status_response.text}")
            return False
    except Exception as e:
        print(f"❌ Failed to check job status: {e}")
        return False
    
    print()
    
    # Step 2: Test Google Docs export
    print("Step 2: Exporting to Google Docs...")
    try:
        export_response = requests.post(
            f"{backend_url}/jobs/{job_id}/export/google-doc",
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {export_response.status_code}")
        
        try:
            result = export_response.json()
            print(f"\nResponse:")
            print(json.dumps(result, indent=2))
            
            if export_response.status_code == 200:
                if result.get("status") in ["success", "partial_success"]:
                    print(f"\n✅ SUCCESS!")
                    print(f"   Document ID: {result.get('doc_id')}")
                    print(f"   Title: {result.get('title')}")
                    print(f"   URL: {result.get('doc_url')}")
                    if result.get("warnings"):
                        print(f"   ⚠️  Warnings: {', '.join(result['warnings'])}")
                    print(f"\n🎉 You can now open the document at:")
                    print(f"   {result.get('doc_url')}")
                    return True
                else:
                    print(f"\n❌ Export failed")
                    print(f"   Error: {result.get('error', 'Unknown error')}")
                    if result.get("warnings"):
                        print(f"   Warnings: {', '.join(result['warnings'])}")
                    return False
            else:
                print(f"\n❌ HTTP Error {export_response.status_code}")
                print(f"   Error: {result.get('error', 'Unknown error')}")
                if result.get("warnings"):
                    print(f"   Warnings: {', '.join(result['warnings'])}")
                return False
                
        except json.JSONDecodeError:
            print(f"❌ Failed to parse JSON response")
            print(f"   Raw response: {export_response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False
    
    print()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python test_google_export.py <job_id> [backend_url]")
        print("\nExample:")
        print("  python test_google_export.py abc-123-def-456")
        print("  python test_google_export.py abc-123-def-456 http://localhost:8000")
        sys.exit(1)
    
    job_id = sys.argv[1]
    backend_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"
    
    success = test_google_export(job_id, backend_url)
    
    print()
    print("="*60)
    if success:
        print("✅ TEST PASSED")
    else:
        print("❌ TEST FAILED")
    print("="*60)
    print()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
