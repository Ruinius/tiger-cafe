import time
from playwright.sync_api import sync_playwright

def verify_restored_sections():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Debug console
        page.on("console", lambda msg: print(f"BROWSER CONSOLE: {msg.text}"))
        page.on("pageerror", lambda err: print(f"BROWSER ERROR: {err}"))

        API_BASE_URL = "http://localhost:8000/api"

        # Mock Auth
        page.route(f"{API_BASE_URL}/auth/me", lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"id": 1, "email": "test@example.com", "name": "Test User"}'
        ))

        # Mock Companies
        page.route(f"{API_BASE_URL}/companies/", lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='[{"id": 1, "name": "Test Company", "ticker": "TEST"}]'
        ))

        # Mock Documents
        page.route(f"{API_BASE_URL}/documents/?company_id=1", lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='[{"id": 101, "filename": "10-K.pdf", "document_type": "annual_filing", "time_period": "FY2023", "indexing_status": "indexed", "analysis_status": "completed"}]'
        ))

        # Mock Document Status
        page.route(f"{API_BASE_URL}/documents/101/status", lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"id": 101, "indexing_status": "indexed", "analysis_status": "completed", "document_type": "annual_filing"}'
        ))

        # Mock Progress (All completed)
        progress_body = '''{
                "status": "completed",
                "milestones": {
                    "balance_sheet": {"status": "completed"},
                    "income_statement": {"status": "completed"},
                    "extracting_additional_items": {"status": "completed"},
                    "classifying_non_operating_items": {"status": "completed"}
                }
            }'''
        page.route(f"{API_BASE_URL}/documents/101/financial-statement-progress", lambda route: route.fulfill(
            status=200, content_type="application/json", body=progress_body))
        page.route(f"{API_BASE_URL}/documents/101/financial-statement-progress-test", lambda route: route.fulfill(
            status=200, content_type="application/json", body=progress_body))

        # Mock Balance Sheet (Simplified)
        bs_body = '{"status": "exists", "data": {"unit": "millions", "currency": "USD", "line_items": []}}'
        page.route(f"{API_BASE_URL}/documents/101/balance-sheet", lambda route: route.fulfill(
            status=200, content_type="application/json", body=bs_body))

        # Mock Income Statement (Simplified)
        is_body = '{"status": "exists", "data": {"unit": "millions", "currency": "USD", "line_items": []}}'
        page.route(f"{API_BASE_URL}/documents/101/income-statement", lambda route: route.fulfill(
            status=200, content_type="application/json", body=is_body))

        # Mock Additional Items
        for endpoint in ['organic-growth', 'amortization', 'other-assets', 'other-liabilities', 'non-operating-classification']:
            page.route(f"{API_BASE_URL}/documents/101/{endpoint}", lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body='{"data": {"line_items": []}}'
            ))

        # Mock Historical Calculations
        historical_body = '''
        {
            "unit": "millions",
            "currency": "USD",
            "entries": [
                {
                    "revenue": 1000,
                    "revenue_growth_yoy": 0.1,
                    "ebita": 200,
                    "ebita_margin": 0.2,
                    "effective_tax_rate": 0.25,
                    "adjusted_tax_rate": 0.20,
                    "net_working_capital": 100,
                    "net_long_term_operating_assets": 500,
                    "invested_capital": 600,
                    "capital_turnover": 1.6667,
                    "nopat": 160,
                    "roic": 0.2667,
                    "marginal_capital_turnover": 2.0,

                    "net_working_capital_breakdown": {
                        "total": 100,
                        "current_assets": [
                            {"line_name": "Accounts Receivable", "line_value": 200, "line_category": "Current Assets"},
                            {"line_name": "Inventory", "line_value": 150, "line_category": "Current Assets"}
                        ],
                        "current_assets_total": 350,
                        "current_liabilities": [
                            {"line_name": "Accounts Payable", "line_value": 250, "line_category": "Current Liabilities"}
                        ],
                        "current_liabilities_total": 250
                    },
                    "net_long_term_operating_assets_breakdown": {
                        "total": 500,
                        "non_current_assets": [
                            {"line_name": "PP&E", "line_value": 600, "line_category": "Non-Current Assets"}
                        ],
                        "non_current_assets_total": 600,
                        "non_current_liabilities": [
                            {"line_name": "Pension Liability", "line_value": 100, "line_category": "Non-Current Liabilities"}
                        ],
                        "non_current_liabilities_total": 100
                    },
                    "ebita_breakdown": {
                        "operating_income": 180,
                        "adjustments": [
                            {"line_name": "Restructuring Charges", "line_value": 20, "is_operating": false}
                        ],
                        "total": 200
                    },
                    "adjusted_tax_rate_breakdown": {
                        "reported_tax_expense": 40,
                        "adjusted_tax_expense": 45,
                        "adjusted_tax_rate": 0.225,
                        "adjustments": [
                             {"line_name": "Tax Effect of Restructuring", "tax_effect": 5, "source": "Non-GAAP"}
                        ]
                    }
                }
            ]
        }
        '''
        page.route(f"{API_BASE_URL}/documents/101/historical-calculations", lambda route: route.fulfill(
            status=200, content_type="application/json", body=historical_body))
        page.route(f"{API_BASE_URL}/documents/101/historical-calculations/test", lambda route: route.fulfill(
            status=200, content_type="application/json", body=historical_body))

        # Go to app
        page.goto("http://localhost:3000/login")
        page.evaluate("localStorage.setItem('tiger-cafe-token', 'fake-token')")
        page.goto("http://localhost:3000/dashboard")

        # Navigate
        print("Navigating...")
        page.click("text=Test Company")
        page.click("text=Annual Filing")

        print("Waiting for Document Analysis...")
        page.wait_for_selector("text=Document Analysis")

        # Use precise selector for the header
        print("Waiting for Historical Calculations Heading...")
        page.wait_for_selector("h3:has-text('Historical Calculations')", timeout=10000)

        print("Verifying sections...")
        page.wait_for_selector("text=1. Invested Capital Analysis")
        page.wait_for_selector("text=2. EBITA Analysis")
        page.wait_for_selector("text=3. Adjusted Tax Rate Analysis")
        page.wait_for_selector("text=4. NOPAT & ROIC Analysis")
        page.wait_for_selector("text=5. Summary Table")

        # Scroll to section for screenshot
        page.locator("h3:has-text('Historical Calculations')").scroll_into_view_if_needed()
        time.sleep(1)

        page.screenshot(path="verification/restored_sections.png", full_page=True)
        print("Verification screenshot captured: verification/restored_sections.png")

        browser.close()

if __name__ == "__main__":
    verify_restored_sections()
