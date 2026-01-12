from playwright.sync_api import Page, expect


def test_login_and_navigate(page: Page):
    """
    Test the critical path: Login -> Select Company -> Select Document.
    Relies on 'dev_user' and seeded data in the backend.
    """
    try:
        # 1. Login
        page.goto("http://localhost:3000/login")

        # Check if we are on login page
        expect(page.get_by_role("heading", name="Tiger-Cafe")).to_be_visible()

        # Fill login form
        page.fill('input[name="email"]', "dev@example.com")
        page.fill('input[name="password"]', "devpassword")

        # Click Sign In
        page.click('button[type="submit"]')

        # 2. Check Dashboard
        # Wait for navigation (increased timeout for initial load/API)
        expect(page).to_have_url("http://localhost:3000/dashboard", timeout=15000)

        # Wait for "Loading companies..." to disappear
        # If it doesn't appear at all, that's fine too (fast load)
        # But if it appears, wait for it to go.
        loading = page.get_by_text("Loading companies...")
        if loading.is_visible():
            expect(loading).not_to_be_visible(timeout=10000)

        # 3. Select Company
        # Specifically look for our seeded test company
        company_loc = page.get_by_text("Fake Railroad Company for Testing, Inc.")
        expect(company_loc).to_be_visible(timeout=10000)
        company_loc.click()

        # 4. Check Document List
        # Specifically look for our seeded test document
        doc_loc = page.get_by_text("Earnings Announcement")
        expect(doc_loc).to_be_visible(timeout=10000)

        # 5. Select Document
        doc_loc.click()

        # 6. Verify Document View
        # Check for visible element specific to Document View since URL might not change in SPA
        expect(page.get_by_text("Status & Metadata")).to_be_visible(timeout=10000)

    except Exception as e:
        print(f"\n❌ Test Failed: {e}")
        # print(f"Page Content dump: {page.content()[:1000]}...")
        raise e
