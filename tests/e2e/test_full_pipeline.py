import os
import subprocess
import time
import sys
import pytest
import requests
from playwright.sync_api import Page, expect

# Constants
BACKEND_PORT = 8000
FRONTEND_PORT = 3000
BACKEND_URL = f"http://localhost:{BACKEND_PORT}"
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"

def kill_process_on_port(port):
    """Try to kill process on port in a cross-platform way (best effort)."""
    try:
        if sys.platform != "win32":
            subprocess.run(f"kill $(lsof -t -i :{port}) 2>/dev/null || true", shell=True)
        else:
            # Windows approach
            cmd = f"FOR /F \"tokens=5\" %a IN ('netstat -aon ^| findstr :{port}') DO taskkill /F /PID %a"
            subprocess.run(cmd, shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    except Exception:
        pass

@pytest.fixture(scope="module")
def services():
    """Start backend and frontend services."""
    print("Starting services...")
    # Start Backend
    backend_env = os.environ.copy()
    backend_env["MOCK_LLM_RESPONSES"] = "true"

    kill_process_on_port(BACKEND_PORT)
    kill_process_on_port(FRONTEND_PORT)

    backend_process = subprocess.Popen(
        ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", str(BACKEND_PORT)],
        env=backend_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Start Frontend
    frontend_process = subprocess.Popen(
        ["npm", "run", "dev", "--", "--port", str(FRONTEND_PORT)],
        cwd="frontend",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for services to be ready
    print("Waiting for services to be ready...")
    for _ in range(30):
        try:
            if requests.get(f"{BACKEND_URL}/api/health").status_code == 200:
                print("Backend ready")
                break
        except:
            time.sleep(1)
    else:
        print("Backend failed to start")
        # Print logs
        out, err = backend_process.communicate()
        print(f"Backend STDOUT: {out.decode()}")
        print(f"Backend STDERR: {err.decode()}")

    # Wait a bit more for frontend
    time.sleep(5)

    yield

    # Cleanup
    print("Stopping services...")
    backend_process.terminate()
    frontend_process.terminate()

    kill_process_on_port(BACKEND_PORT)
    kill_process_on_port(FRONTEND_PORT)

def test_upload_and_process(services, page: Page):
    # Mock Auth
    page.route("**/api/auth/me", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body='{"id": "test-user", "name": "Test User", "email": "test@example.com"}'
    ))

    # Go to Dashboard
    try:
        page.goto(f"{FRONTEND_URL}/", timeout=10000)
    except Exception as e:
        # If timeout, maybe it's still loading or redirection happens
        print(f"Navigation error: {e}")

    # Handle potential Login Redirect
    if "login" in page.url or page.locator("text=Sign In").count() > 0:
        print("On Login Page, setting fake token...")
        page.evaluate("localStorage.setItem('tiger-cafe-token', 'fake-token')")
        page.goto(f"{FRONTEND_URL}/dashboard")

    # Check if we are on dashboard
    try:
        expect(page.locator(".add-document-button")).to_be_visible(timeout=10000)
    except:
        # Take screenshot for debugging
        page.screenshot(path="tests/e2e/debug_dashboard_load.png")
        raise

    # Upload Document
    page.click(".add-document-button")

    # Locate file input
    # Note: File input might be hidden or inside the dropzone
    # We use set_input_files directly on the file input element.
    # We don't use page.expect_file_chooser() because we are setting the file directly.
    page.locator("input[type=file]").set_input_files("tests/e2e/mock_document.pdf")

    page.click("button:has-text('Upload')")

    # Wait for processing to complete
    # Expect the document name to appear in the list
    expect(page.locator("text=mock_document.pdf")).to_be_visible(timeout=20000)

    # Click on the document to view details (if that's how it works)
    page.click("text=mock_document.pdf")

    # Trigger Extraction if needed (or verify if it auto-starts)
    # If there is an "Extract" button
    if page.locator("button:has-text('Run Extraction')").count() > 0:
        page.click("button:has-text('Run Extraction')")

    # Verify Mock Results appear
    # The mock response has "Cash and Cash Equivalents"
    expect(page.locator("text=Cash and Cash Equivalents")).to_be_visible(timeout=30000)
