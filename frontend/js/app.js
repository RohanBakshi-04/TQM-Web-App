/**
 * Alpine.js Application Controller with RBAC Multi-Stakeholder Support
 * Course: BBAT104 Fundamentals of TQM
 * Quality Goal: Q05 - Reduce Response Time
 */

document.addEventListener("alpine:init", () => {
    Alpine.data("appRoot", () => ({
        activeSection: "welcome", // "welcome" | "login" | "dashboard" | "architecture"
        selectedRole: "superadmin",
        loginNotice: "",
        loginError: "",
        loginLoading: false,

        // Authentication State
        isAuthenticated: false,
        currentUser: null,
        userRoles: [],
        userPermissions: [],

        // Role-Specific State
        activeDashboardTab: "overview", // "overview" | "users" | "student_portal" | "roles" | "telemetry"
        rolesList: [],
        usersList: [],
        studentProfile: null,
        isolationTestResult: null,
        isolationTestLoading: false,

        // Credentials for Form
        loginCredentials: {
            username: "superadmin",
            password: "Password123!"
        },

        // System Health State
        systemHealth: {
            status: "connecting",
            database: { status: "checking", engine: "--", journal_mode: "--", ping_latency_ms: 0 },
            q05_telemetry: { meets_sla: false, sla_target_ms: 10.0 },
            serverLatencyMs: 0
        },
        healthCheckInterval: null,

        // Quick login presets for testing all 12 roles
        rolePresets: [
            { role: "super_admin", username: "superadmin", label: "Super Admin", icon: "fa-shield-halved" },
            { role: "hostel_admin", username: "hosteladmin", label: "Hostel Admin", icon: "fa-hotel" },
            { role: "warden", username: "warden", label: "Chief Warden", icon: "fa-user-tie" },
            { role: "assistant_warden", username: "asstwarden", label: "Asst Warden", icon: "fa-clipboard-user" },
            { role: "student", username: "rohan", label: "Student (Rohan)", icon: "fa-graduation-cap" },
            { role: "accountant", username: "accountant", label: "Accountant", icon: "fa-calculator" },
            { role: "mess_manager", username: "messmanager", label: "Mess Manager", icon: "fa-utensils" },
            { role: "maintenance_staff", username: "maintenance", label: "Maintenance", icon: "fa-wrench" },
            { role: "security_guard", username: "security", label: "Security", icon: "fa-id-badge" },
            { role: "admission_officer", username: "admission", label: "Admissions", icon: "fa-file-signature" },
            { role: "parent_guardian", username: "parent", label: "Parent/Guardian", icon: "fa-people-roof" },
            { role: "auditor", username: "evaluator", label: "TQM Auditor", icon: "fa-chart-line" }
        ],

        async init() {
            await this.fetchHealth();
            this.healthCheckInterval = setInterval(() => this.fetchHealth(), 8000);
            await this.checkCurrentSession();
            await this.loadRoles();
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
            } catch (err) {
                this.loginError = err.message || "Invalid credentials or account locked.";
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

            if (this.hasRole("student")) {
                this.activeDashboardTab = "student_portal";
                this.loadMyStudentProfile();
            } else if (this.hasRole("super_admin") || this.hasRole("hostel_admin")) {
                this.activeDashboardTab = "users";
                this.loadUsers();
            } else {
                this.activeDashboardTab = "overview";
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
            this.activeSection = "welcome";
        },

        hasRole(roleName) {
            return this.userRoles.includes(roleName) || this.userRoles.includes("super_admin");
        },

        hasPermission(permName) {
            return this.userPermissions.includes(permName) || this.userRoles.includes("super_admin");
        },

        async loadUsers() {
            try {
                this.usersList = await window.API.getUsers();
            } catch (err) {
                this.usersList = [];
            }
        },

        async loadMyStudentProfile() {
            if (!this.currentUser || !this.currentUser.linked_student_id) return;
            try {
                this.studentProfile = await window.API.getStudentProfile(this.currentUser.linked_student_id);
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
            } catch (err) {
                this.isolationTestResult = {
                    success: false,
                    status: 403,
                    targetId: targetStudentId,
                    message: `Security Barrier Enforced: ${err.message}`
                };
            } finally {
                this.isolationTestLoading = false;
            }
        }
    }));
});
