"""
Test script for document upload endpoint
"""

import requests
import sys
import os

# Configuration
API_BASE_URL = "http://localhost:8000"
UPLOAD_ENDPOINT = f"{API_BASE_URL}/api/documents/upload"

def test_upload(pdf_path: str, google_token: str):
    """
    Test the document upload endpoint.
    
    Args:
        pdf_path: Path to the PDF file to upload
        google_token: Google OAuth ID token (from Google Sign-In)
    """
    
    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}")
        return
    
    # Prepare headers with authentication
    headers = {
        "Authorization": f"Bearer {google_token}"
    }
    
    # Prepare file for upload
    with open(pdf_path, 'rb') as f:
        files = {
            'file': (os.path.basename(pdf_path), f, 'application/pdf')
        }
        
        print(f"Uploading {pdf_path}...")
        print(f"Endpoint: {UPLOAD_ENDPOINT}")
        
        try:
            response = requests.post(
                UPLOAD_ENDPOINT,
                headers=headers,
                files=files
            )
            
            print(f"\nStatus Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print("\n✅ Upload successful!")
                print(f"\nDocument ID: {result.get('document_id')}")
                print(f"\nClassification Results:")
                classification = result.get('classification', {})
                print(f"  - Document Type: {classification.get('document_type')}")
                print(f"  - Company: {classification.get('company_name')}")
                print(f"  - Ticker: {classification.get('ticker')}")
                print(f"  - Time Period: {classification.get('time_period')}")
                print(f"  - Confidence: {classification.get('confidence')}")
                
                duplicate_info = result.get('duplicate_info')
                if duplicate_info and duplicate_info.get('is_duplicate'):
                    print(f"\n⚠️  Duplicate detected!")
                    print(f"  - Match Reason: {duplicate_info.get('match_reason')}")
                    print(f"  - Existing Document ID: {duplicate_info.get('existing_document_id')}")
                
                print(f"\nMessage: {result.get('message')}")
                print(f"\nRequires Confirmation: {result.get('requires_confirmation')}")
                
                if result.get('requires_confirmation'):
                    print("\n📝 Next step: Call /api/documents/confirm-upload with document_id to index the document")
            else:
                print(f"\n❌ Upload failed!")
                print(f"Response: {response.text}")
                
        except requests.exceptions.ConnectionError:
            print(f"\n❌ Error: Could not connect to {API_BASE_URL}")
            print("Make sure the server is running: python run.py")
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_upload.py <path_to_pdf> <google_oauth_token>")
        print("\nExample:")
        print("  python test_upload.py sample.pdf eyJhbGciOiJSUzI1NiIs...")
        print("\nNote: You need a Google OAuth ID token to authenticate.")
        print("For testing, you can get one from Google Sign-In in your frontend.")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    google_token = sys.argv[2]
    
    test_upload(pdf_path, google_token)

