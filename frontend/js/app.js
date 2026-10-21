/**
 * Alpine.js Application Controller with RBAC Multi-Stakeholder Support
 * Course: BBAT104 Fundamentals of TQM
 * Quality Goal: Q05 - Reduce Response Time
 */

document.addEventListener("alpine:init", () => {
    Alpine.data("appRoot", () => ({
        // View & Navigation State
        activeSection: "welcome", // "welcome" | "login" | "dashboard" | "architecture"
        activeRoleView: "super_admin", // Current role dashboard view (can be switched by admin or set to user's role)
        sidebarCollapsed: false,
        mobileMenuOpen: false,
        darkMode: localStorage.getItem("hms_theme") === "dark",

        // Layout Dropdowns
        notificationOpen: false,
        userMenuOpen: false,
        searchQuery: "",
        searchModalOpen: false,

        // Authentication State
        isAuthenticated: false,
        currentUser: null,
        userRoles: [],
        userPermissions: [],

        // Notifications List
        notifications: [
            { id: 1, title: "System Initialized", message: "Hostel Management System v0.3.0 active in WAL mode.", time: "Just now", unread: true, type: "info" },
            { id: 2, title: "Q05 SLA Active", message: "Response time telemetry running under 10ms threshold.", time: "5m ago", unread: true, type: "success" },
            { id: 3, title: "Database Audit", message: "Initial 39 tables and 38 B-Tree indexes operational.", time: "1h ago", unread: false, type: "system" }
        ],

        // Toast Notification System
        toasts: [],

        // Form & Credential State
        selectedRole: "superadmin",
        loginNotice: "",
        loginError: "",
        loginLoading: false,
        loginCredentials: {
            username: "superadmin",
            password: "Password123!"
        },

        // System Health & Telemetry State
        systemHealth: {
            status: "connecting",
            database: { status: "checking", engine: "--", journal_mode: "--", ping_latency_ms: 0 },
            q05_telemetry: { meets_sla: false, sla_target_ms: 10.0 },
            serverLatencyMs: 0
        },
        healthCheckInterval: null,

        // Quick login presets for testing all 12 roles
        rolePresets: [
            { role: "super_admin", username: "superadmin", label: "Super Admin", icon: "fa-shield-halved", desc: "Global system control" },
            { role: "hostel_admin", username: "hosteladmin", label: "Hostel Admin", icon: "fa-hotel", desc: "Campus facilities oversight" },
            { role: "warden", username: "warden", label: "Chief Warden", icon: "fa-user-tie", desc: "Student welfare & discipline" },
            { role: "assistant_warden", username: "asstwarden", label: "Asst Warden", icon: "fa-clipboard-user", desc: "Daily operational rounds" },
            { role: "student", username: "rohan", label: "Student (Rohan)", icon: "fa-graduation-cap", desc: "Resident self-service portal" },
            { role: "accountant", username: "accountant", label: "Accountant", icon: "fa-calculator", desc: "Fee invoices & billing" },
            { role: "mess_manager", username: "messmanager", label: "Mess Manager", icon: "fa-utensils", desc: "Dietary plans & meal attendance" },
            { role: "maintenance_staff", username: "maintenance", label: "Maintenance", icon: "fa-wrench", desc: "Facility repairs & tasks" },
            { role: "security_guard", username: "security", label: "Security", icon: "fa-id-badge", desc: "Gate passes & visitor logs" },
            { role: "admission_officer", username: "admission", label: "Admissions", icon: "fa-file-signature", desc: "Applications & verification" },
            { role: "parent_guardian", username: "parent", label: "Parent/Guardian", icon: "fa-people-roof", desc: "Ward academic & fee tracking" },
            { role: "auditor", username: "evaluator", label: "TQM Auditor", icon: "fa-chart-line", desc: "Compliance & latency review" }
        ],

        // Role-Specific Loaded Data
        rolesList: [],
        usersList: [],
        studentProfile: null,
        isolationTestResult: null,
        isolationTestLoading: false,

        async init() {
            // Apply stored theme
            if (this.darkMode) {
                document.documentElement.classList.add("dark");
            } else {
                document.documentElement.classList.remove("dark");
            }

            // Keyboard shortcut for search
            window.addEventListener("keydown", (e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === "k") {
                    e.preventDefault();
                    this.searchModalOpen = !this.searchModalOpen;
                }
                if (e.key === "Escape") {
                    this.searchModalOpen = false;
                    this.notificationOpen = false;
                    this.userMenuOpen = false;
                    this.mobileMenuOpen = false;
                }
            });

            await this.fetchHealth();
            this.healthCheckInterval = setInterval(() => this.fetchHealth(), 8000);
            await this.checkCurrentSession();
            await this.loadRoles();
        },

        toggleDarkMode() {
            this.darkMode = !this.darkMode;
            if (this.darkMode) {
                document.documentElement.classList.add("dark");
                localStorage.setItem("hms_theme", "dark");
                this.showToast("Dark mode enabled", "info");
            } else {
                document.documentElement.classList.remove("dark");
                localStorage.setItem("hms_theme", "light");
                this.showToast("Light mode enabled", "info");
            }
        },

        toggleSidebar() {
            this.sidebarCollapsed = !this.sidebarCollapsed;
        },

        toggleMobileMenu() {
            this.mobileMenuOpen = !this.mobileMenuOpen;
        },

        showToast(message, type = "info") {
            const id = Date.now() + Math.random();
            this.toasts.push({ id, message, type });
            setTimeout(() => {
                this.toasts = this.toasts.filter(t => t.id !== id);
            }, 3500);
        },

        removeToast(id) {
            this.toasts = this.toasts.filter(t => t.id !== id);
        },

        get unreadNotificationCount() {
            return this.notifications.filter(n => n.unread).length;
        },

        markNotificationsRead() {
            this.notifications.forEach(n => n.unread = false);
            this.showToast("All notifications marked as read", "success");
        },

        get breadcrumbs() {
            const crumbs = [{ label: "Home", section: "welcome" }];
            if (this.activeSection === "welcome") {
                crumbs.push({ label: "Overview", section: "welcome" });
            } else if (this.activeSection === "login") {
                crumbs.push({ label: "Stakeholder Sign In", section: "login" });
            } else if (this.activeSection === "architecture") {
                crumbs.push({ label: "Q05 Architecture & Telemetry", section: "architecture" });
            } else if (this.activeSection === "dashboard") {
                const currentPreset = this.rolePresets.find(p => p.role === this.activeRoleView);
                crumbs.push({ label: "Stakeholder Portal", section: "dashboard" });
                crumbs.push({ label: currentPreset ? currentPreset.label : "Dashboard", section: "dashboard" });
            }
            return crumbs;
        },

        async fetchHealth() {
            const result = await window.API.checkHealth();
            if (result && result.status) {
                this.systemHealth = result;
            }
        },

        async checkCurrentSession() {
            try {
                const user = await window.API.getMe();
                if (user) {
                    this.onAuthenticated(user);
                }
            } catch (e) {
                this.currentUser = null;
                this.isAuthenticated = false;
            }
        },

        async loadRoles() {
            try {
                this.rolesList = await window.API.getRoles();
            } catch (e) {
                this.rolesList = [];
            }
        },

        selectPreset(preset) {
            this.loginCredentials.username = preset.username;
            this.loginCredentials.password = "Password123!";
            this.loginError = "";
            this.loginNotice = `Loaded credentials for ${preset.label} (${preset.username})`;
        },

        async handleLogin() {
            this.loginLoading = true;
            this.loginError = "";
            this.loginNotice = "";

            try {
                const authData = await window.API.login(
                    this.loginCredentials.username,
                    this.loginCredentials.password
                );
                this.onAuthenticated(authData.user);
                this.activeSection = "dashboard";
                this.showToast(`Welcome back, ${authData.user.first_name}!`, "success");
            } catch (err) {
                this.loginError = err.message || "Invalid credentials or account locked.";
                this.showToast(this.loginError, "error");
            } finally {
                this.loginLoading = false;
            }
        },

        onAuthenticated(user) {
            this.currentUser = user;
            this.isAuthenticated = true;
            this.userRoles = user.roles || [];
            this.userPermissions = user.permissions || [];
            this.isolationTestResult = null;

            // Automatically set the active role dashboard to user's primary role
            if (this.userRoles.length > 0) {
                this.activeRoleView = this.userRoles[0];
            } else {
                this.activeRoleView = "student";
            }

            if (this.activeRoleView === "student" && user.linked_student_id) {
                this.loadMyStudentProfile();
            } else if (this.activeRoleView === "super_admin" || this.activeRoleView === "hostel_admin") {
                this.loadUsers();
            }
        },

        async handleLogout() {
            await window.API.logout();
            this.currentUser = null;
            this.isAuthenticated = false;
            this.userRoles = [];
            this.userPermissions = [];
            this.studentProfile = null;
            this.usersList = [];
            this.isolationTestResult = null;
            this.userMenuOpen = false;
            this.activeSection = "welcome";
            this.showToast("Signed out successfully", "info");
        },

        hasRole(roleName) {
            return this.userRoles.includes(roleName) || this.userRoles.includes("super_admin");
        },

        hasPermission(permName) {
            return this.userPermissions.includes(permName) || this.userRoles.includes("super_admin");
        },

        switchRoleDashboard(roleKey) {
            // Super Admin can inspect all 12 dashboards, other users only switch if they possess the role
            if (this.hasRole("super_admin") || this.userRoles.includes(roleKey)) {
                this.activeRoleView = roleKey;
                this.activeSection = "dashboard";
                if (roleKey === "student") {
                    this.loadMyStudentProfile();
                } else if (roleKey === "super_admin" || roleKey === "hostel_admin") {
                    this.loadUsers();
                }
                const preset = this.rolePresets.find(p => p.role === roleKey);
                this.showToast(`Switched view to ${preset?.label || roleKey}`, "info");
            } else {
                this.showToast("Access Denied: You do not possess this stakeholder role", "error");
            }
        },

        async loadUsers() {
            try {
                this.usersList = await window.API.getUsers();
            } catch (err) {
                this.usersList = [];
            }
        },

        async loadMyStudentProfile() {
            const sid = (this.currentUser && this.currentUser.linked_student_id) ? this.currentUser.linked_student_id : 1;
            try {
                this.studentProfile = await window.API.getStudentProfile(sid);
            } catch (err) {
                this.studentProfile = null;
            }
        },

        async testStudentIsolation(targetStudentId) {
            this.isolationTestLoading = true;
            this.isolationTestResult = null;
            try {
                const data = await window.API.getStudentProfile(targetStudentId);
                this.isolationTestResult = {
                    success: true,
                    status: 200,
                    targetId: targetStudentId,
                    message: `Authorized Access: Retrieved profile for Student ID ${targetStudentId} (${data.first_name} ${data.last_name}).`
                };
                this.showToast(`Authorized: Loaded Student #${targetStudentId}`, "success");
            } catch (err) {
                this.isolationTestResult = {
                    success: false,
                    status: 403,
                    targetId: targetStudentId,
                    message: `Security Barrier Enforced: ${err.message}`
                };
                this.showToast(`HTTP 403: Student isolation barrier enforced`, "error");
            } finally {
                this.isolationTestLoading = false;
            }
        }
    }));
});
