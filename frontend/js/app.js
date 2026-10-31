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
        searchCategory: "all",
        searchResults: [],
        searchLoading: false,
        searchResultsLatency: null,
        navigationLatencyMs: 0.0,

        // Reusable Modal & Confirmation Dialog State
        modal: {
            open: false,
            title: "",
            message: "",
            confirmText: "Confirm",
            cancelText: "Cancel",
            confirmType: "primary", // "primary" | "danger"
            onConfirm: null
        },

        openConfirmModal(title, message, onConfirm, confirmText = "Confirm", confirmType = "primary") {
            this.modal = {
                open: true,
                title,
                message,
                confirmText,
                cancelText: "Cancel",
                confirmType,
                onConfirm
            };
        },

        closeConfirmModal() {
            this.modal.open = false;
            this.modal.onConfirm = null;
        },

        executeModalConfirm() {
            if (typeof this.modal.onConfirm === "function") {
                this.modal.onConfirm();
            }
            this.closeConfirmModal();
        },

        // Reusable Data Table State
        tableSearch: "",
        tableFilter: "all",
        tablePage: 1,
        tablePageSize: 5,

        get filteredUsers() {
            let list = this.usersList || [];
            if (this.tableFilter !== "all") {
                const isActive = this.tableFilter === "active" ? 1 : 0;
                list = list.filter(u => u.is_active === isActive);
            }
            if (this.tableSearch && this.tableSearch.trim() !== "") {
                const q = this.tableSearch.toLowerCase();
                list = list.filter(u =>
                    (u.first_name && u.first_name.toLowerCase().includes(q)) ||
                    (u.last_name && u.last_name.toLowerCase().includes(q)) ||
                    (u.username && u.username.toLowerCase().includes(q)) ||
                    (u.email && u.email.toLowerCase().includes(q)) ||
                    (u.roles && u.roles.some(r => r.toLowerCase().includes(q)))
                );
            }
            return list;
        },

        get paginatedUsers() {
            return window.HMSComponents.paginate(this.filteredUsers, this.tablePage, this.tablePageSize);
        },

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

        // Allocation & Poka-Yoke Management State
        allocationsList: [],
        availableBedsList: [],
        transferRequestsList: [],
        allocationSuggestions: [],
        suggestionsLoading: false,
        selectedAllocationSlip: null,
        studentAllocationHistory: [],

        allocationModalOpen: false,
        transferModalOpen: false,
        suggestionsModalOpen: false,
        slipModalOpen: false,

        allocationForm: {
            student_id: "",
            bed_id: "",
            start_date: new Date().toISOString().split("T")[0],
            end_date: "",
            remarks: "",
            fee_status: "Pending"
        },

        transferForm: {
            allocation_id: null,
            to_bed_id: "",
            reason: ""
        },

        checkoutForm: {
            allocation_id: null,
            checkout_date: new Date().toISOString().split("T")[0],
            reason: "Academic Term Completed"
        },
        checkoutModalOpen: false,

        dashboardStats: {
            hostels: { total: 1, rooms: 3, beds: 6, occupied_beds: 2, available_beds: 4, occupancy_rate: 33.3 },
            students: { total: 3, active: 3 },
            users: { total: 12 },
            finance: { total_invoices: 0, total_invoiced: 0, total_collected: 0, outstanding_dues: 0 },
            operations: { pending_complaints: 0, pending_leaves: 0, active_visitors: 0, pending_admissions: 0, pending_maintenance: 0 },
            recent_activity: []
        },

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
            this.loadDashboardStats();

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

        async loadDashboardStats() {
            try {
                const stats = await window.API.getDashboardStats();
                if (stats) {
                    this.dashboardStats = stats;
                }
            } catch (e) {
                // Keep default seeded metrics
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
                this.loadDashboardStats();
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
        },

        // ==================== ALLOCATION CONTROLLER METHODS ====================

        async loadAllocations(filterHostel = null) {
            try {
                const params = {};
                if (filterHostel) params.hostel_id = filterHostel;
                this.allocationsList = await window.API.getAllocations(params);
            } catch (err) {
                this.showToast(`Failed to load allocations: ${err.message}`, "error");
            }
        },

        async loadAvailableBeds(gender = null) {
            try {
                const params = {};
                if (gender) params.gender = gender;
                this.availableBedsList = await window.API.getAvailableBeds(params);
            } catch (err) {
                this.showToast(`Failed to load available beds: ${err.message}`, "error");
            }
        },

        async loadTransfers() {
            try {
                this.transferRequestsList = await window.API.getTransfers();
            } catch (err) {
                this.showToast(`Failed to load transfer requests: ${err.message}`, "error");
            }
        },

        async submitAllocation() {
            if (!this.allocationForm.student_id || !this.allocationForm.bed_id || !this.allocationForm.start_date) {
                this.showToast("Please provide Student ID, Bed ID, and Start Date.", "warning");
                return;
            }
            try {
                const payload = {
                    student_id: parseInt(this.allocationForm.student_id),
                    bed_id: parseInt(this.allocationForm.bed_id),
                    start_date: this.allocationForm.start_date,
                    end_date: this.allocationForm.end_date ? this.allocationForm.end_date : null,
                    remarks: this.allocationForm.remarks,
                    fee_status: this.allocationForm.fee_status
                };
                const res = await window.API.createAllocation(payload);
                this.showToast(`Bed successfully allocated (Allocation #${res.id})`, "success");
                this.allocationModalOpen = false;
                this.loadAllocations();
                this.loadAvailableBeds();
                this.loadDashboardStats();
                this.viewSlip(res.id);
            } catch (err) {
                this.showToast(`Poka-Yoke Error: ${err.message}`, "error");
            }
        },

        async getSuggestionsForStudent(studentId) {
            if (!studentId) {
                this.showToast("Please enter a valid student ID first", "warning");
                return;
            }
            this.suggestionsLoading = true;
            try {
                this.allocationSuggestions = await window.API.getAllocationSuggestions(studentId);
                this.suggestionsModalOpen = true;
                if (this.allocationSuggestions.length === 0) {
                    this.showToast("No compatible rooms found for this student.", "info");
                }
            } catch (err) {
                this.showToast(`Suggestion Error: ${err.message}`, "error");
            } finally {
                this.suggestionsLoading = false;
            }
        },

        selectSuggestedBed(bedId) {
            this.allocationForm.bed_id = bedId;
            this.suggestionsModalOpen = false;
            this.showToast(`Selected Bed #${bedId} from intelligent suggestion engine.`, "success");
        },

        openTransferModal(allocation) {
            this.transferForm = {
                allocation_id: allocation.id,
                to_bed_id: "",
                reason: ""
            };
            this.loadAvailableBeds(allocation.student_gender);
            this.transferModalOpen = true;
        },

        async submitTransfer() {
            if (!this.transferForm.to_bed_id || !this.transferForm.reason) {
                this.showToast("Please select a target bed and state a reason.", "warning");
                return;
            }
            try {
                const res = await window.API.requestTransfer(
                    this.transferForm.allocation_id,
                    parseInt(this.transferForm.to_bed_id),
                    this.transferForm.reason
                );
                this.showToast(res.message || "Room transfer processed successfully.", "success");
                this.transferModalOpen = false;
                this.loadAllocations();
                this.loadAvailableBeds();
                this.loadTransfers();
            } catch (err) {
                this.showToast(`Transfer Failed: ${err.message}`, "error");
            }
        },

        openCheckoutModal(allocation) {
            this.checkoutForm = {
                allocation_id: allocation.id,
                checkout_date: new Date().toISOString().split("T")[0],
                reason: "Academic Term Completed"
            };
            this.checkoutModalOpen = true;
        },

        async submitCheckout() {
            try {
                const res = await window.API.checkoutAllocation(
                    this.checkoutForm.allocation_id,
                    this.checkoutForm.checkout_date,
                    this.checkoutForm.reason
                );
                this.showToast(`Check-out completed. Bed released to available.`, "success");
                this.checkoutModalOpen = false;
                this.loadAllocations();
                this.loadAvailableBeds();
                this.loadDashboardStats();
            } catch (err) {
                this.showToast(`Check-out Failed: ${err.message}`, "error");
            }
        },

        async performCheckin(allocationId) {
            try {
                await window.API.checkinAllocation(allocationId);
                this.showToast("Student check-in recorded successfully.", "success");
                this.loadAllocations();
            } catch (err) {
                this.showToast(`Check-in Error: ${err.message}`, "error");
            }
        },

        async viewSlip(allocationId) {
            try {
                this.selectedAllocationSlip = await window.API.getAllocation(allocationId);
                this.slipModalOpen = true;
            } catch (err) {
                this.showToast(`Failed to load allocation slip: ${err.message}`, "error");
            }
        },

        async loadMyAllocationHistory() {
            const sid = (this.currentUser && this.currentUser.linked_student_id) ? this.currentUser.linked_student_id : 1;
            try {
                this.studentAllocationHistory = await window.API.getStudentAllocationHistory(sid);
            } catch (err) {
                this.studentAllocationHistory = [];
            }
        },

        async performFastSearch() {
            if (!this.searchQuery || !this.searchQuery.trim()) {
                this.searchResults = [];
                this.searchResultsLatency = null;
                return;
            }
            this.searchLoading = true;
            try {
                const res = await window.API.search(this.searchQuery.trim(), this.searchCategory);
                this.searchResults = res.results || [];
                this.searchResultsLatency = res.execution_time_ms;
            } catch (err) {
                console.error("Fast search error:", err);
                this.searchResults = [];
                this.searchResultsLatency = null;
            } finally {
                this.searchLoading = false;
            }
        },

        setSearchCategory(cat) {
            this.searchCategory = cat;
            if (this.searchQuery && this.searchQuery.trim()) {
                this.performFastSearch();
            }
        },

        highlightMatch(text, query) {
            if (!text) return "";
            if (!query || !query.trim()) return text;
            const terms = query.trim().split(/\s+/).filter(Boolean);
            if (!terms.length) return text;
            const pattern = new RegExp(`(${terms.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi');
            return text.replace(pattern, '<mark class="bg-amber-200 dark:bg-amber-900/60 text-amber-900 dark:text-amber-200 font-bold px-0.5 rounded">$1</mark>');
        },

        navigateTo(section) {
            if (this.activeSection === section) return;
            const t0 = performance.now();
            this.activeSection = section;
            this.mobileMenuOpen = false;

            // Preserve view-specific state; avoid redundant network requests if already populated
            if (section === 'dashboard' && !this.dashboardStats) {
                this.loadDashboardStats();
            } else if (section === 'allocations' && (!this.allocations || !this.allocations.length)) {
                this.loadAllocations();
                this.loadAvailableBeds();
                this.loadTransfers();
            }
            this.navigationLatencyMs = parseFloat((performance.now() - t0).toFixed(2));
        },

        selectSearchResult(item) {
            this.searchModalOpen = false;
            if (item.category === 'allocations') {
                this.navigateTo('allocations');
            } else if (item.category === 'hostels' || item.category === 'rooms') {
                this.navigateTo('dashboard');
                this.switchRoleDashboard('hostel_admin');
            } else if (item.category === 'students') {
                this.navigateTo('dashboard');
                this.switchRoleDashboard('super_admin');
            } else {
                this.showToast(`Selected ${item.category}: ${item.title}`, "info");
            }
        }
    }));
});
