from playwright.sync_api import sync_playwright

def verify_buttons():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate to the frontend (assuming it runs on port 3000, as seen in logs)
        try:
            page.goto("http://localhost:3000", timeout=30000)
        except Exception as e:
            print(f"Failed to load page: {e}")
            return

        # Mock the /api/auth/me endpoint BEFORE ANY NAVIGATION
        print("Setting up auth mock...")
        page.route("**/api/auth/me", lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"id": "test-user", "name": "Test User", "email": "test@example.com"}'
        ))

        # We might be redirected to login page if not authenticated
        try:
            # Check if we are on login page or redirected there
            if "login" in page.url:
                print("On Login Page - Authenticating...")

                # Set a fake token
                page.evaluate("localStorage.setItem('tiger-cafe-token', 'fake-token')")

                # Navigate to dashboard
                print("Navigating to dashboard...")
                page.goto("http://localhost:3000/dashboard")

            page.wait_for_selector(".header-title", timeout=10000)
        except Exception as e:
            print(f"Failed to verify main app: {e}")
            page.screenshot(path="verification/error_state.png")
            return

        # 1. Verify Header Buttons
        print("Verifying Header...")
        page.screenshot(path="verification/1_header.png")

        # 2. Verify LeftPanel Buttons
        # The 'Add Document' button should be visible and use the primary color
        print("Verifying LeftPanel...")
        try:
            page.wait_for_selector(".add-document-button", timeout=5000)

            # Check computed styles for Add Document button
            add_doc_btn = page.locator(".add-document-button")
            bg_color = add_doc_btn.evaluate("el => getComputedStyle(el).backgroundColor")
            print(f"Add Document Button Background: {bg_color}")
            # Expected: rgb(10, 132, 255) for #0A84FF or similar blue

            page.screenshot(path="verification/2_left_panel.png")

            # 3. Verify Upload Modal Buttons
            print("Verifying Upload Modal...")
            add_doc_btn.click()
            page.wait_for_selector(".modal-content")

            # Check Cancel and Upload buttons
            cancel_btn = page.locator(".button-secondary", has_text="Cancel")
            upload_btn = page.locator(".button-primary", has_text="Upload")

            page.screenshot(path="verification/3_upload_modal.png")

            # Close modal
            cancel_btn.click()
        except Exception as e:
            print(f"Error checking LeftPanel/Modal: {e}")
            page.screenshot(path="verification/error_leftpanel.png")

        browser.close()

if __name__ == "__main__":
    verify_buttons()
