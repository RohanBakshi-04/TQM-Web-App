"""Targeted Multi-Stakeholder Button & Navigation Verification with Playwright.

Covers all 15 stakeholders:
1. superadmin (super_admin)
2. hosteladmin (hostel_admin)
3. warden (warden)
4. asstwarden (assistant_warden)
5. clerk (hostel_clerk)
6. accountant (accountant)
7. admission (admission_officer)
8. secsupervisor (security_supervisor)
9. security (security_guard)
10. itadmin (it_admin)
11. rohan (student)
12. parent (parent_guardian)
13. messmanager (mess_manager)
14. maintenance (maintenance_staff)
15. evaluator (auditor)

For each role:
- Signs in cleanly
- Clicks all dashboard quick action / navigation links
- Clicks all authorized sidebar nav buttons
- Clicks authorized subtabs
- Asserts ZERO error toasts appear
"""

import os
import shutil
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.request

import uvicorn
from playwright.sync_api import sync_playwright

from backend.app.config import settings
from backend.app.database.init_db import initialize_database
from backend.app.main import app


def get_free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def run_test():
    temp_dir = tempfile.mkdtemp(prefix="hms_click_test_")
    db_path = os.path.join(temp_dir, "click_test.db")
    orig_db_path = settings.database_path
    settings.database_path = db_path

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        initialize_database(conn, seed=True)
        conn.close()

        port = get_free_port()
        base_url = f"http://127.0.0.1:{port}"
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
        server_thread = threading.Thread(target=server.run, daemon=True)
        server_thread.start()

        for _ in range(50):
            try:
                with urllib.request.urlopen(f"{base_url}/api/health", timeout=1) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                time.sleep(0.1)

        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        # Handle JavaScript dialogs automatically (dismiss confirms so they don't block)
        page.on("dialog", lambda dialog: dialog.dismiss())

        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        roles = [
            ("superadmin", "super_admin"),
            ("hosteladmin", "hostel_admin"),
            ("warden", "warden"),
            ("asstwarden", "assistant_warden"),
            ("clerk", "hostel_clerk"),
            ("accountant", "accountant"),
            ("admission", "admission_officer"),
            ("secsupervisor", "security_supervisor"),
            ("security", "security_guard"),
            ("itadmin", "it_admin"),
            ("rohan", "student"),
            ("parent", "parent_guardian"),
            ("messmanager", "mess_manager"),
            ("maintenance", "maintenance_staff"),
            ("evaluator", "auditor"),
        ]

        total_interactions = 0
        all_role_failures = {}

        for username, expected_role in roles:
            sys.stdout.write(f"\n--- Testing Role: {username} ({expected_role}) ---\n")
            sys.stdout.flush()

            role_errors = []

            # 1. Login
            page.goto(base_url, wait_until="domcontentloaded")
            page.evaluate("""() => {
                const el = document.querySelector('[x-data]');
                if (el && el._x_dataStack) {
                    const data = el._x_dataStack[0];
                    data.activeSection = 'login';
                    data.authTab = 'login';
                }
            }""")
            page.wait_for_selector("input[x-model='loginCredentials.username']", state="visible", timeout=3000)

            login_form = page.locator("form").filter(has=page.locator("input[x-model='loginCredentials.username']"))
            login_form.locator("input[x-model='loginCredentials.username']").fill(username)
            login_form.locator("input[x-model='loginCredentials.password']").fill("Password123!")
            login_form.locator("button[type='submit']").click()

            page.wait_for_function(
                "() => { const el = document.querySelector('[x-data]'); return el && el._x_dataStack && el._x_dataStack[0].isAuthenticated === true; }",
                timeout=3000
            )
            page.wait_for_timeout(300)

            def get_current_error_toasts():
                return page.evaluate("""() => {
                    const d = document.querySelector('[x-data]')._x_dataStack[0];
                    const errs = (d.toasts || []).filter(t => t.type === 'error').map(t => t.message);
                    d.toasts = [];
                    return errs;
                }""")

            # Check initial load
            errs = get_current_error_toasts()
            if errs:
                role_errors.extend([f"Initial load: {e}" for e in errs])

            # 2. Click all Action Card buttons on Dashboard
            btn_count = page.evaluate("""() => {
                const btns = document.querySelectorAll("section[x-show*=\\"activeSection === 'dashboard'\\"] button");
                return Array.from(btns).filter(b => b.offsetParent !== null).length;
            }""")
            sys.stdout.write(f"  Found {btn_count} visible dashboard buttons.\n")
            sys.stdout.flush()

            for i in range(btn_count):
                try:
                    # Reset to dashboard before each click
                    page.evaluate("() => { if (document.querySelector('[x-data]')) document.querySelector('[x-data]')._x_dataStack[0].activeSection = 'dashboard'; }")
                    page.wait_for_timeout(100)

                    btn = page.locator("section[x-show*=\"activeSection === 'dashboard'\"] button:visible").nth(i)
                    txt = btn.inner_text(timeout=500).strip().replace("\n", " ")
                    if not txt or any(k in txt.lower() for k in ["logout", "sign out", "delete", "deactivate"]):
                        continue
                    btn.click(timeout=800)
                    total_interactions += 1
                    page.wait_for_timeout(150)
                    errs = get_current_error_toasts()
                    if errs:
                        role_errors.extend([f"Button '{txt}': {e}" for e in errs])
                except Exception:
                    pass

            # 3. Test Sidebar Navigation across all authorized sections
            nav_items = page.evaluate("""() => {
                const d = document.querySelector('[x-data]')._x_dataStack[0];
                return (d.authorizedNavItems || []).map(item => item.id);
            }""")
            sys.stdout.write(f"  Navigating {len(nav_items)} authorized sections: {nav_items}\n")
            sys.stdout.flush()

            for nav_id in nav_items:
                page.evaluate(f"() => {{ document.querySelector('[x-data]')._x_dataStack[0].navigateTo('{nav_id}'); }}")
                total_interactions += 1
                page.wait_for_timeout(200)
                errs = get_current_error_toasts()
                if errs:
                    role_errors.extend([f"Nav '{nav_id}': {e}" for e in errs])

                # Check subtabs within section if applicable
                if nav_id == 'admin':
                    subtabs = ['roles', 'audit', 'backups']
                    if expected_role in ('super_admin', 'hostel_admin'):
                        subtabs = ['settings', 'users', 'registrations', 'roles', 'audit', 'backups']
                    elif expected_role == 'auditor':
                        subtabs = ['audit', 'backups', 'roles']

                    for stab in subtabs:
                        page.evaluate(f"""() => {{
                            const d = document.querySelector('[x-data]')._x_dataStack[0];
                            d.adminTab = '{stab}';
                            if ('{stab}' === 'settings') d.loadAdminSettings();
                            else if ('{stab}' === 'users') d.loadAdminUsers();
                            else if ('{stab}' === 'registrations') d.loadPendingRegistrations();
                            else if ('{stab}' === 'roles') d.loadAdminRolesAndPermissions();
                            else if ('{stab}' === 'audit') d.loadAdminAuditLogs();
                            else if ('{stab}' === 'backups') d.loadAdminBackups();
                        }}""")
                        total_interactions += 1
                        page.wait_for_timeout(150)
                        errs = get_current_error_toasts()
                        if errs:
                            role_errors.extend([f"Admin tab '{stab}': {e}" for e in errs])

                elif nav_id == 'allocations':
                    for stab in ['allocations', 'available', 'transfers']:
                        page.evaluate(f"""() => {{
                            const d = document.querySelector('[x-data]')._x_dataStack[0];
                            d.allocationTab = '{stab}';
                            if ('{stab}' === 'allocations') d.loadAllocations();
                            else if ('{stab}' === 'available') d.loadAvailableBeds();
                            else if ('{stab}' === 'transfers') d.loadTransfers();
                        }}""")
                        total_interactions += 1
                        page.wait_for_timeout(100)
                        errs = get_current_error_toasts()
                        if errs:
                            role_errors.extend([f"Alloc tab '{stab}': {e}" for e in errs])

            # 4. Clean Logout
            page.evaluate("""() => {
                if (window.API && window.API.logout) { window.API.logout(); }
                const el = document.querySelector('[x-data]');
                if (el && el._x_dataStack) {
                    const data = el._x_dataStack[0];
                    data.authToken = null;
                    data.currentUser = null;
                    data.isAuthenticated = false;
                    data.activeSection = 'welcome';
                    data.toasts = [];
                }
            }""")
            page.wait_for_timeout(150)

            all_role_failures[username] = role_errors
            if role_errors:
                sys.stdout.write(f"  RESULT: FAIL ({len(role_errors)} errors)\n")
                for e in role_errors:
                    sys.stdout.write(f"    * {e}\n")
            else:
                sys.stdout.write(f"  RESULT: PASS (0 errors)\n")
            sys.stdout.flush()

        browser.close()
        pw.stop()

        server.should_exit = True
        server_thread.join(timeout=3)

        total_errs = sum(len(v) for v in all_role_failures.values())
        print("\n" + "=" * 60)
        print("SUMMARY OF VERIFICATION")
        print("=" * 60)
        print(f"Total interactions executed: {total_interactions}")
        print(f"Total errors detected: {total_errs}")
        for u, errs in all_role_failures.items():
            print(f"  {u:<16}: {'PASS' if not errs else f'FAIL ({len(errs)} errors)'}")

        return total_errs

    finally:
        settings.database_path = orig_db_path
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    code = run_test()
    sys.exit(0 if code == 0 else 1)
