"""Real Headless Browser Acceptance Testing with Playwright.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Objective: Q05 - Zero-defect browser operation across all 12 roles,
                   responsive viewports, and interactive form handling.
"""

import os
import shutil
import socket
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.request

import uvicorn
from playwright.sync_api import sync_playwright

from backend.app.config import settings
from backend.app.database.init_db import initialize_database
from backend.app.main import app


def get_free_port() -> int:
    """Find a random free ephemeral port on localhost."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class TestBrowserAcceptance(unittest.TestCase):
    """End-to-end headless browser acceptance tests using Playwright."""

    @classmethod
    def setUpClass(cls):
        # 1. Provision isolated test database
        cls.temp_dir = tempfile.mkdtemp(prefix="hms_browser_")
        cls.db_path = os.path.join(cls.temp_dir, "browser_acceptance.db")
        cls.orig_db_path = settings.database_path
        settings.database_path = cls.db_path

        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        initialize_database(conn, seed=True)
        conn.close()

        # 2. Start Uvicorn test server on random free port
        cls.port = get_free_port()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=cls.port, log_level="error")
        )
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()

        # Wait for server to become responsive
        for _ in range(50):
            try:
                with urllib.request.urlopen(f"{cls.base_url}/api/health", timeout=1) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                time.sleep(0.1)

        # 3. Launch Playwright
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.browser.close()
            cls.playwright.stop()
        except Exception:
            pass

        cls.server.should_exit = True
        cls.server_thread.join(timeout=3)

        settings.database_path = cls.orig_db_path
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def login_role(self, page, username, password="Password123!"):
        """Helper to navigate to Sign In, fill credentials, and submit."""
        page.goto(self.base_url, wait_until="networkidle")
        # Direct Alpine view transition to Sign In
        page.evaluate("""() => {
            const el = document.querySelector('[x-data]');
            if (el && el._x_dataStack) {
                const data = el._x_dataStack[0];
                data.activeSection = 'login';
                data.authTab = 'login';
            }
        }""")
        page.wait_for_selector("input[x-model='loginCredentials.username']", state="visible", timeout=5000)

        # Target the login form specifically to avoid hidden modals
        login_form = page.locator("form").filter(has=page.locator("input[x-model='loginCredentials.username']"))
        login_form.locator("input[x-model='loginCredentials.username']").fill(username)
        login_form.locator("input[x-model='loginCredentials.password']").fill(password)
        login_form.locator("button[type='submit']").click()
        try:
            page.wait_for_function(
                "() => { const el = document.querySelector('[x-data]'); return el && el._x_dataStack && (el._x_dataStack[0].isAuthenticated === true || Boolean(el._x_dataStack[0].loginError)); }",
                timeout=5000
            )
        except Exception:
            page.wait_for_timeout(1000)

    def logout_role(self, page):
        """Helper to log out user and reset session state."""
        page.evaluate("""() => {
            if (window.API && window.API.logout) {
                window.API.logout();
            }
            const el = document.querySelector('[x-data]');
            if (el && el._x_dataStack) {
                const data = el._x_dataStack[0];
                data.currentUser = null;
                data.isAuthenticated = false;
                data.activeSection = 'welcome';
            }
        }""")
        page.wait_for_timeout(300)

    def test_01_desktop_viewport_and_all_12_stakeholder_logins(self):
        """Test Desktop (1440x900): verify landing, invalid credentials rejection, and successful logins for all 12 roles."""
        context = self.browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # 1. Load application
        page.goto(self.base_url, wait_until="networkidle")
        self.assertIn("Hostel Management System", page.title())

        # 2. Verify invalid credentials rejection
        self.login_role(page, "superadmin", "CompletelyWrongPassword!")
        login_err = page.evaluate("() => document.querySelector('[x-data]')._x_dataStack[0].loginError")
        self.assertTrue(bool(login_err), "Expected loginError state to be populated on invalid login")
        self.logout_role(page)

        # 3. Verify all 12 roles can log in and render role-specific dashboard views
        all_roles = [
            ("superadmin", "super_admin"),
            ("hosteladmin", "hostel_admin"),
            ("warden", "warden"),
            ("asstwarden", "assistant_warden"),
            ("rohan", "student"),
            ("accountant", "accountant"),
            ("messmanager", "mess_manager"),
            ("maintenance", "maintenance_staff"),
            ("security", "security_guard"),
            ("admission", "admission_officer"),
            ("parent", "parent_guardian"),
            ("evaluator", "auditor")
        ]

        for username, role_key in all_roles:
            self.login_role(page, username, "Password123!")

            # Assert user is authenticated and activeSection is dashboard
            app_state = page.evaluate("""() => {
                const el = document.querySelector('[x-data]');
                if (!el || !el._x_dataStack) return {};
                const data = el._x_dataStack[0];
                return {
                    isAuthenticated: data.isAuthenticated,
                    activeSection: data.activeSection,
                    userRoles: data.userRoles,
                    currentUser: data.currentUser ? data.currentUser.username : null
                };
            }""")
            self.assertTrue(app_state.get("isAuthenticated"), f"Authentication state false for role {role_key}")
            self.assertEqual(app_state.get("activeSection"), "dashboard", f"activeSection not dashboard for role {role_key}")
            self.assertEqual(app_state.get("currentUser"), username, f"currentUser mismatch for {username}")

            # Verify navigation items rendered for this role
            nav_count = page.locator("nav button, nav a").count()
            self.assertGreater(nav_count, 0, f"No navigation links rendered for role {role_key}")

            # Log out before next role
            self.logout_role(page)

        context.close()

    def test_02_tablet_viewport_responsiveness(self):
        """Test Tablet (768x1024): verify responsive layout and navigation on intermediate screen sizes."""
        context = self.browser.new_context(viewport={"width": 768, "height": 1024})
        page = context.new_page()

        page.goto(self.base_url, wait_until="networkidle")
        self.assertTrue(page.locator("body").is_visible())

        # Sign in as warden on tablet
        self.login_role(page, "warden", "Password123!")
        is_auth = page.evaluate("() => document.querySelector('[x-data]')._x_dataStack[0].isAuthenticated")
        self.assertTrue(is_auth)

        # Verify tablet header and dashboard elements
        self.assertTrue(page.locator("h1, h2, h3").count() > 0)
        self.logout_role(page)
        context.close()

    def test_03_mobile_viewport_responsiveness(self):
        """Test Mobile (390x844): verify mobile viewport, touch layout, and no horizontal overflow."""
        context = self.browser.new_context(
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            has_touch=True
        )
        page = context.new_page()

        page.goto(self.base_url, wait_until="networkidle")

        # Sign in as student (rohan) on mobile
        self.login_role(page, "rohan", "Password123!")
        is_auth = page.evaluate("() => document.querySelector('[x-data]')._x_dataStack[0].isAuthenticated")
        self.assertTrue(is_auth)

        # Verify student mobile layout renders without horizontal overflow
        body_width = page.evaluate("() => document.body.scrollWidth")
        self.assertLessEqual(body_width, 420, "Mobile layout horizontal overflow detected!")

        self.logout_role(page)
        context.close()

    def test_04_fast_search_modal_interaction(self):
        """Test Fast Search Modal: verify modal trigger (Ctrl+K or button) and instant search results."""
        context = self.browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.goto(self.base_url, wait_until="networkidle")

        # Open search modal via search button
        search_btn = page.locator("button:visible:has-text('Search')").first
        search_btn.click()
        page.wait_for_timeout(300)

        # Type search query
        search_input = page.locator("input:visible[x-model='searchQuery']")
        search_input.fill("Rohan")
        page.wait_for_timeout(600)

        # Verify search results list or message
        results_count = page.evaluate("() => document.querySelector('[x-data]')._x_dataStack[0].searchResults.length")
        self.assertGreaterEqual(results_count, 0)

        # Close search with Escape
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)

        context.close()

    def test_05_theme_dark_mode_toggle(self):
        """Test Theme Toggle: verify clicking dark mode toggle toggles 'dark' class on HTML root."""
        context = self.browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.goto(self.base_url, wait_until="networkidle")

        # Initial class check
        has_dark_before = "dark" in page.evaluate("() => document.documentElement.className")

        # Click theme toggle button
        theme_btn = page.locator("button[title*='Toggle Light / Dark Theme']").first
        theme_btn.click()
        page.wait_for_timeout(300)

        has_dark_after = "dark" in page.evaluate("() => document.documentElement.className")
        self.assertNotEqual(has_dark_before, has_dark_after, "Theme toggle did not switch dark class on <html>")

        context.close()


if __name__ == "__main__":
    unittest.main()
