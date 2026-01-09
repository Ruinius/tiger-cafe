import time
from playwright.sync_api import sync_playwright

def verify_dashboard():
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Define route for mocking
        API_BASE_URL = "http://localhost:8000/api"

        # Mock Login (if redirected)
        page.route(f"{API_BASE_URL}/auth/me", lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"id": 1, "email": "test@example.com", "name": "Test User"}'
        ))

        # Mock Companies
        page.route(f"{API_BASE_URL}/companies/", lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='[{"id": 1, "name": "Apple Inc.", "ticker": "AAPL"}, {"id": 2, "name": "Microsoft", "ticker": "MSFT"}]'
        ))

        # Mock Documents for Company 1
        page.route(f"{API_BASE_URL}/documents/?company_id=1", lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='[{"id": 101, "filename": "10-K 2023.pdf", "document_type": "annual_filing", "time_period": "FY2023", "indexing_status": "indexed", "analysis_status": "completed", "uploaded_at": "2023-01-01T00:00:00Z"}]'
        ))

        # Mock Company Analysis (Historical)
        page.route(f"{API_BASE_URL}/companies/1/historical-calculations", lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"entries": [], "unit": "millions", "currency": "USD"}'
        ))

        # Mock Document Status
        page.route(f"{API_BASE_URL}/documents/101/status", lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"id": 101, "indexing_status": "indexed", "analysis_status": "completed", "document_type": "annual_filing"}'
        ))

        # Mock Document Chunks
        page.route(f"{API_BASE_URL}/documents/101/chunks", lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"chunks": [{"chunk_index": 0, "text": "This is a mock chunk.", "page_start": 1, "page_end": 1}]}'
        ))

        # Mock Document File (PDF)
        page.route(f"{API_BASE_URL}/documents/101/file", lambda route: route.fulfill(
            status=200,
            content_type="application/pdf",
            body=b'%PDF-1.4\n%...'
        ))

        # Manually set local storage to simulate authentication
        # The app checks 'tiger-cafe-token' in localStorage
        page.goto("http://localhost:3000/login")

        # Set token
        page.evaluate("localStorage.setItem('tiger-cafe-token', 'fake-token')")

        # Navigate to dashboard
        page.goto("http://localhost:3000/dashboard")

        # Wait for navigation to dashboard
        page.wait_for_url("**/dashboard")

        # Verify Global View
        page.wait_for_selector("text=Companies", timeout=10000)
        page.wait_for_selector("text=Apple Inc.")
        page.screenshot(path="verification/1_dashboard_global.png")
        print("Captured Global View")

        # 3. Company View Verification
        page.click("text=Apple Inc.")
        # Wait for Document List to appear (it shows "Annual Filing" or similar based on mock)
        # document_type: annual_filing -> "Annual Filing"
        page.wait_for_selector("text=Annual Filing")
        # Check if right panel loaded (Company Analysis)
        page.wait_for_selector("text=Apple Inc. Financial Analysis")
        page.screenshot(path="verification/2_dashboard_company.png")
        print("Captured Company View")

        # 4. Document View Verification
        page.click("text=Annual Filing")
        # Wait for PdfViewer (Left) and Extraction View (Right)
        # Left: "Original PDF" or "Status & Metadata"
        page.wait_for_selector("text=Status & Metadata")
        # Right: "Document Analysis"
        page.wait_for_selector("text=Document Analysis")

        page.screenshot(path="verification/3_dashboard_document.png")
        print("Captured Document View")

        # 5. Back Navigation
        # Click "Apple Inc." in breadcrumb to go back to Company View
        # Need to find the breadcrumb link.
        # Structure: <button class="breadcrumb-link">Apple Inc.</button>
        # We can click text="Apple Inc." but that might be the title.
        # The breadcrumb is in .panel-header

        # Let's locate specifically the breadcrumb link
        page.click(".breadcrumb-link >> text=Apple Inc.")

        # Should be back to Company View
        page.wait_for_selector("text=Apple Inc. Financial Analysis")
        page.wait_for_selector("text=Companies") # Breadcrumb to global
        page.screenshot(path="verification/4_dashboard_back_to_company.png")
        print("Captured Back to Company View")

        # Back to Global
        page.click(".breadcrumb-link >> text=Companies")
        page.wait_for_selector("input[placeholder='Search companies...']")
        page.screenshot(path="verification/5_dashboard_back_to_global.png")
        print("Captured Back to Global View")

        # 6. Upload Modal (Global)
        page.click("text=+ Add Document")
        page.wait_for_selector("text=Upload Document")
        page.screenshot(path="verification/6_upload_modal.png")
        print("Captured Upload Modal")

        browser.close()

if __name__ == "__main__":
    verify_dashboard()
