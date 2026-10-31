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

        // Complaint & Maintenance Workflow State
        myComplaints: [],
        complaintsLoading: false,
        selectedComplaint: null,
        complaintDetailModalOpen: false,
        complaintSubmitModalOpen: false,
        complaintFilterStatus: "all",
        complaintFilterCategory: "all",
        newComplaint: {
            category: "Electrical",
            title: "",
            description: "",
            severity: "Medium",
            room_id: null,
            attachment_url: ""
        },
        complaintNewComment: "",
        complaintReopenReason: "",
        complaintRating: 5,
        complaintFeedbackComment: "",

        // Maintenance Work-Orders State
        maintenanceTasks: [],
        maintenanceLoading: false,
        selectedMaintenanceTask: null,
        maintenanceTaskDetailModalOpen: false,
        maintenanceCompleteModalOpen: false,
        maintenanceHoldModalOpen: false,
        maintenanceFilterStatus: "all",
        maintenanceFilterPriority: "all",
        staffAvailabilityList: [],
        taskCompleteForm: {
            resolution_notes: "",
            actual_cost: 0,
            completion_photo_url: ""
        },
        taskHoldForm: {
            hold_reason: "",
            notes: ""
        },
        taskProgressNote: "",

        // Warden Grievance Oversight & Workflow State
        wardenComplaints: [],
        wardenComplaintsLoading: false,
        wardenComplaintsTotal: 0,
        wardenComplaintsPage: 1,
        wardenComplaintFilterStatus: "all",
        wardenComplaintFilterCategory: "all",
        wardenComplaintSearch: "",
        complaintAnalytics: null,
        complaintAssignModalOpen: false,
        complaintRejectModalOpen: false,
        complaintEscalateModalOpen: false,
        complaintAssignForm: {
            assigned_to: "",
            priority: "Medium",
            deadline: "",
            internal_remarks: "",
            affects_occupancy: false
        },
        complaintRejectForm: {
            reason: ""
        },
        complaintEscalateForm: {
            reason: ""
        },

        // Attendance State
        attendanceSubTab: "dashboard", // "dashboard" | "mark" | "history" | "reports"
        attendanceDate: new Date().toISOString().split("T")[0],
        attendanceHostelId: "",
        attendanceBuildingId: "",
        attendanceFloorId: "",
        attendanceRoomId: "",
        attendanceSummary: null,
        attendanceMarkingStudents: [],
        attendanceRecords: [],
        attendanceRecordsTotal: 0,
        attendanceFilterStatus: "all",
        attendanceReportStartDate: new Date(Date.now() - 30 * 86400000).toISOString().split("T")[0],
        attendanceReportEndDate: new Date().toISOString().split("T")[0],
        attendanceReportData: null,
        attendanceCorrectionModal: {
            open: false,
            attendanceId: null,
            studentName: "",
            date: "",
            previousStatus: "",
            newStatus: "Present",
            reason: ""
        },

        // Leave & Outpass State
        leaveSubTab: "my_leaves", // "my_leaves" | "apply" | "approvals" | "outpasses" | "overdue"
        leaveApplications: [],
        leaveApplicationsTotal: 0,
        selectedLeave: null,
        leaveDetailModalOpen: false,
        leaveFilterStatus: "all",
        leaveFilterType: "all",
        newLeave: {
            leave_type: "Home Leave",
            start_date: new Date().toISOString().split("T")[0],
            end_date: new Date(Date.now() + 2 * 86400000).toISOString().split("T")[0],
            departure_time: "08:00",
            expected_return_time: "20:00",
            reason: "",
            destination: "",
            emergency_contact: "",
            guardian_contact: "",
            document_url: "",
            is_draft: false
        },
        leaveRejectModalOpen: false,
        leaveRejectReason: "",
        outpassesList: [],
        outpassesTotal: 0,
        outpassFilterStatus: "all",
        overdueOutpassesList: [],
        outpassVerifyRemarks: "",

        // Visitor Management State
        visitorSubTab: "active", // "active" | "register" | "history" | "approvals"
        activeVisitorsList: [],
        visitorLogs: [],
        visitorLogsTotal: 0,
        visitorSearch: "",
        visitorFilterStatus: "all",
        newVisitor: {
            name: "",
            phone: "",
            id_proof_type: "Aadhaar",
            id_proof_number: "",
            address: "",
            student_id: 1,
            purpose: "Family Visit",
            expected_exit_time: "",
            immediate_checkin: true
        },
        selectedVisitor: null,
        visitorDetailModalOpen: false,
        visitorRejectModalOpen: false,
        visitorRejectReason: "",

        // Fee & Financial Management State
        feeSubTab: "invoices", // "structures" | "invoices" | "payments" | "refunds" | "reports"
        feeStructures: [],
        invoicesList: [],
        invoicesTotal: 0,
        invoiceSearch: "",
        invoiceFilterStatus: "all",
        selectedInvoice: null,
        invoiceDetailModalOpen: false,
        feeStructureModalOpen: false,
        newInvoiceModalOpen: false,
        bulkInvoiceModalOpen: false,
        discountModalOpen: false,
        cancelInvoiceModalOpen: false,
        receiptModalOpen: false,
        activeReceipt: null,
        discountForm: { invoice_id: null, amount: "", reason: "" },
        cancelForm: { invoice_id: null, reason: "" },
        newFeeStructure: {
            name: "",
            fee_category: "Hostel Accommodation Fee",
            hostel_id: null,
            room_type: "All",
            academic_year: "2026-27",
            semester: "All",
            amount: 25000,
            payment_frequency: "Semester",
            is_mandatory: true,
            late_fine_amount: 500,
            description: ""
        },
        newInvoice: {
            student_id: 1,
            fee_structure_id: null,
            issue_date: new Date().toISOString().split('T')[0],
            due_date: new Date(Date.now() + 15 * 86400000).toISOString().split('T')[0],
            total_amount: 25000,
            discount_amount: 0,
            discount_reason: "",
            remarks: "Standard semester invoice"
        },
        bulkInvoiceForm: {
            hostel_id: 1,
            academic_year: "2026-27",
            room_type: "All",
            fee_structure_id: null,
            issue_date: new Date().toISOString().split('T')[0],
            due_date: new Date(Date.now() + 15 * 86400000).toISOString().split('T')[0],
            remarks: "Semester bulk billing"
        },

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
                this.loadMyComplaints();
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
                    this.loadMyComplaints();
                } else if (roleKey === "maintenance_staff") {
                    this.loadMaintenanceTasks();
                } else if (roleKey === "warden" || roleKey === "assistant_warden") {
                    this.loadStaffAvailability();
                    this.loadMaintenanceTasks();
                    this.loadWardenComplaints();
                    this.loadComplaintAnalytics();
                } else if (roleKey === "super_admin" || roleKey === "hostel_admin") {
                    this.loadUsers();
                    this.loadStaffAvailability();
                    this.loadMaintenanceTasks();
                    this.loadWardenComplaints();
                    this.loadComplaintAnalytics();
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
            } else if (section === 'attendance') {
                this.loadAttendanceSummary();
                this.loadStudentsForMarking();
            } else if (section === 'leaves') {
                this.loadLeaveApplications();
                this.loadOutpasses();
                this.loadOverdueOutpasses();
            } else if (section === 'visitors') {
                this.loadActiveVisitors();
                this.loadVisitorLogs();
            } else if (section === 'finance') {
                this.loadFeeStructures();
                this.loadInvoicesList();
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
            } else if (item.category === 'complaints') {
                this.openComplaintDetails(item.entity_id);
            } else {
                this.showToast(`Selected ${item.category}: ${item.title}`, "info");
            }
        },

        // ==================== STUDENT COMPLAINT METHODS ====================
        async loadMyComplaints() {
            this.complaintsLoading = true;
            try {
                const status = this.complaintFilterStatus !== "all" ? this.complaintFilterStatus : null;
                const cat = this.complaintFilterCategory !== "all" ? this.complaintFilterCategory : null;
                this.myComplaints = await window.API.getMyComplaints(status, cat);
            } catch (err) {
                console.error("Failed to load student complaints:", err);
                this.myComplaints = [];
            } finally {
                this.complaintsLoading = false;
            }
        },

        openComplaintSubmitModal() {
            this.newComplaint = {
                category: "Electrical",
                title: "",
                description: "",
                severity: "Medium",
                room_id: (this.studentProfile && this.studentProfile.allocation) ? this.studentProfile.allocation.room_id : null,
                attachment_url: ""
            };
            this.complaintSubmitModalOpen = true;
        },

        async submitNewComplaint() {
            if (!this.newComplaint.title || !this.newComplaint.title.trim()) {
                this.showToast("Please enter a complaint title", "error");
                return;
            }
            if (!this.newComplaint.description || !this.newComplaint.description.trim()) {
                this.showToast("Please describe the issue", "error");
                return;
            }

            try {
                const res = await window.API.submitComplaint({
                    category: this.newComplaint.category,
                    title: this.newComplaint.title.trim(),
                    description: this.newComplaint.description.trim(),
                    severity: this.newComplaint.severity,
                    room_id: this.newComplaint.room_id || undefined,
                    attachment_url: this.newComplaint.attachment_url ? this.newComplaint.attachment_url.trim() : null
                });
                this.showToast(`Grievance submitted successfully: ${res.complaint_id}`, "success");
                this.complaintSubmitModalOpen = false;
                await this.loadMyComplaints();
                this.loadDashboardStats();
            } catch (err) {
                this.showToast(`Submission failed: ${err.message}`, "error");
            }
        },

        async openComplaintDetails(complaintId) {
            try {
                this.selectedComplaint = await window.API.getComplaintDetails(complaintId);
                this.complaintNewComment = "";
                this.complaintReopenReason = "";
                this.complaintRating = this.selectedComplaint.feedback_rating || 5;
                this.complaintFeedbackComment = this.selectedComplaint.feedback_comment || "";
                this.complaintDetailModalOpen = true;
            } catch (err) {
                this.showToast(`Failed to load grievance details: ${err.message}`, "error");
            }
        },

        async postComplaintComment() {
            if (!this.complaintNewComment || !this.complaintNewComment.trim()) return;
            try {
                const res = await window.API.addComplaintComment(this.selectedComplaint.id, this.complaintNewComment.trim());
                this.showToast("Comment added to record", "success");
                this.selectedComplaint.updates = res.updates || [];
                this.complaintNewComment = "";
                await this.loadMyComplaints();
            } catch (err) {
                this.showToast(`Comment failed: ${err.message}`, "error");
            }
        },

        async triggerReopenComplaint() {
            if (!this.complaintReopenReason || !this.complaintReopenReason.trim()) {
                this.showToast("Please provide an explanation for reopening", "error");
                return;
            }
            try {
                const res = await window.API.reopenComplaint(this.selectedComplaint.id, this.complaintReopenReason.trim());
                this.showToast(`Grievance reopened (Ticket #${res.complaint_id})`, "info");
                this.selectedComplaint = res;
                this.complaintReopenReason = "";
                await this.loadMyComplaints();
                this.loadDashboardStats();
            } catch (err) {
                this.showToast(`Reopening failed: ${err.message}`, "error");
            }
        },

        async submitComplaintFeedback() {
            try {
                const res = await window.API.submitComplaintFeedback(
                    this.selectedComplaint.id,
                    this.complaintRating,
                    this.complaintFeedbackComment
                );
                this.showToast("Feedback submitted. Thank you!", "success");
                this.selectedComplaint = res;
                await this.loadMyComplaints();
            } catch (err) {
                this.showToast(`Feedback failed: ${err.message}`, "error");
            }
        },

        // ==================== MAINTENANCE WORK-ORDER METHODS ====================
        async loadMaintenanceTasks() {
            this.maintenanceLoading = true;
            try {
                const status = this.maintenanceFilterStatus !== "all" ? this.maintenanceFilterStatus : null;
                const prio = this.maintenanceFilterPriority !== "all" ? this.maintenanceFilterPriority : null;
                this.maintenanceTasks = await window.API.getMaintenanceTasks(status, prio);
            } catch (err) {
                console.error("Failed to load maintenance tasks:", err);
                this.maintenanceTasks = [];
            } finally {
                this.maintenanceLoading = false;
            }
        },

        async loadStaffAvailability() {
            try {
                this.staffAvailabilityList = await window.API.getStaffAvailability();
            } catch (err) {
                this.staffAvailabilityList = [];
            }
        },

        async openMaintenanceTaskDetails(taskId) {
            try {
                this.selectedMaintenanceTask = await window.API.getMaintenanceTask(taskId);
                this.taskProgressNote = "";
                this.maintenanceTaskDetailModalOpen = true;
            } catch (err) {
                this.showToast(`Failed to load task details: ${err.message}`, "error");
            }
        },

        async handleAcceptTask(taskId) {
            try {
                const res = await window.API.acceptMaintenanceTask(taskId);
                this.showToast(`Task ${res.task_code} accepted`, "success");
                await this.loadMaintenanceTasks();
                if (this.selectedMaintenanceTask && this.selectedMaintenanceTask.id === taskId) {
                    this.selectedMaintenanceTask = res;
                }
            } catch (err) {
                this.showToast(`Failed to accept: ${err.message}`, "error");
            }
        },

        async handleStartTask(taskId) {
            try {
                const res = await window.API.startMaintenanceTask(taskId);
                this.showToast(`Task ${res.task_code} started`, "info");
                await this.loadMaintenanceTasks();
                if (this.selectedMaintenanceTask && this.selectedMaintenanceTask.id === taskId) {
                    this.selectedMaintenanceTask = res;
                }
            } catch (err) {
                this.showToast(`Failed to start: ${err.message}`, "error");
            }
        },

        openHoldTaskModal(task) {
            this.selectedMaintenanceTask = task;
            this.taskHoldForm = { hold_reason: "", notes: "" };
            this.maintenanceHoldModalOpen = true;
        },

        async submitHoldTask() {
            if (!this.taskHoldForm.hold_reason || !this.taskHoldForm.hold_reason.trim()) {
                this.showToast("Please provide reason for holding work", "error");
                return;
            }
            try {
                const res = await window.API.holdMaintenanceTask(
                    this.selectedMaintenanceTask.id,
                    this.taskHoldForm.hold_reason.trim(),
                    this.taskHoldForm.notes.trim()
                );
                this.showToast(`Task ${res.task_code} set to On Hold`, "warning");
                this.maintenanceHoldModalOpen = false;
                await this.loadMaintenanceTasks();
                if (this.selectedMaintenanceTask && this.selectedMaintenanceTask.id === res.id) {
                    this.selectedMaintenanceTask = res;
                }
            } catch (err) {
                this.showToast(`Failed to hold: ${err.message}`, "error");
            }
        },

        openCompleteTaskModal(task) {
            this.selectedMaintenanceTask = task;
            this.taskCompleteForm = {
                resolution_notes: "",
                actual_cost: task.estimated_cost || 0,
                completion_photo_url: ""
            };
            this.maintenanceCompleteModalOpen = true;
        },

        async submitCompleteTask() {
            if (!this.taskCompleteForm.resolution_notes || !this.taskCompleteForm.resolution_notes.trim()) {
                this.showToast("Please enter repair resolution notes", "error");
                return;
            }
            try {
                const res = await window.API.completeMaintenanceTask(
                    this.selectedMaintenanceTask.id,
                    this.taskCompleteForm.resolution_notes.trim(),
                    this.taskCompleteForm.actual_cost,
                    this.taskCompleteForm.completion_photo_url ? this.taskCompleteForm.completion_photo_url.trim() : null
                );
                this.showToast(`Task ${res.task_code} marked Completed`, "success");
                this.maintenanceCompleteModalOpen = false;
                await this.loadMaintenanceTasks();
                if (this.selectedMaintenanceTask && this.selectedMaintenanceTask.id === res.id) {
                    this.selectedMaintenanceTask = res;
                }
            } catch (err) {
                this.showToast(`Failed to complete: ${err.message}`, "error");
            }
        },

        async submitTaskProgress() {
            if (!this.taskProgressNote || !this.taskProgressNote.trim()) return;
            try {
                const res = await window.API.updateMaintenanceTaskProgress(this.selectedMaintenanceTask.id, this.taskProgressNote.trim());
                this.showToast("Progress log added", "success");
                this.selectedMaintenanceTask = res;
                this.taskProgressNote = "";
                await this.loadMaintenanceTasks();
            } catch (err) {
                this.showToast(`Failed to add note: ${err.message}`, "error");
            }
        },

        // ==================== WARDEN WORKFLOW METHODS ====================
        async loadWardenComplaints() {
            this.wardenComplaintsLoading = true;
            try {
                const res = await window.API.getComplaints(
                    null,
                    this.wardenComplaintFilterStatus,
                    this.wardenComplaintFilterCategory,
                    null,
                    this.wardenComplaintSearch ? this.wardenComplaintSearch.trim() : null,
                    this.wardenComplaintsPage,
                    15
                );
                this.wardenComplaints = res.items || [];
                this.wardenComplaintsTotal = res.total || 0;
            } catch (err) {
                console.error("Failed to load warden complaints:", err);
                this.wardenComplaints = [];
            } finally {
                this.wardenComplaintsLoading = false;
            }
        },

        async loadComplaintAnalytics() {
            try {
                this.complaintAnalytics = await window.API.getComplaintAnalytics();
            } catch (err) {
                console.error("Failed to load complaint analytics:", err);
            }
        },

        openAssignModal(complaint) {
            this.selectedComplaint = complaint;
            this.complaintAssignForm = {
                assigned_to: (this.staffAvailabilityList && this.staffAvailabilityList.length > 0) ? this.staffAvailabilityList[0].user_id : "",
                priority: complaint.severity || "Medium",
                deadline: "",
                internal_remarks: "",
                affects_occupancy: complaint.severity === "Critical"
            };
            this.complaintAssignModalOpen = true;
        },

        async submitAssignComplaint() {
            if (!this.complaintAssignForm.assigned_to) {
                this.showToast("Please select a maintenance technician", "error");
                return;
            }
            try {
                const res = await window.API.assignComplaint(
                    this.selectedComplaint.id,
                    parseInt(this.complaintAssignForm.assigned_to),
                    this.complaintAssignForm.priority,
                    this.complaintAssignForm.deadline || null,
                    this.complaintAssignForm.internal_remarks.trim(),
                    this.complaintAssignForm.affects_occupancy
                );
                this.showToast(`Complaint ${res.complaint_id} assigned to technician`, "success");
                this.complaintAssignModalOpen = false;
                await this.loadWardenComplaints();
                await this.loadComplaintAnalytics();
                this.loadMaintenanceTasks();
                this.loadDashboardStats();
            } catch (err) {
                this.showToast(`Assignment failed: ${err.message}`, "error");
            }
        },

        openRejectModal(complaint) {
            this.selectedComplaint = complaint;
            this.complaintRejectForm = { reason: "" };
            this.complaintRejectModalOpen = true;
        },

        async submitRejectComplaint() {
            if (!this.complaintRejectForm.reason || !this.complaintRejectForm.reason.trim()) {
                this.showToast("Please provide justification for rejection", "error");
                return;
            }
            try {
                const res = await window.API.rejectComplaint(this.selectedComplaint.id, this.complaintRejectForm.reason.trim());
                this.showToast(`Complaint ${res.complaint_id} rejected`, "info");
                this.complaintRejectModalOpen = false;
                await this.loadWardenComplaints();
                await this.loadComplaintAnalytics();
                this.loadDashboardStats();
            } catch (err) {
                this.showToast(`Rejection failed: ${err.message}`, "error");
            }
        },

        openEscalateModal(complaint) {
            this.selectedComplaint = complaint;
            this.complaintEscalateForm = { reason: "" };
            this.complaintEscalateModalOpen = true;
        },

        async submitEscalateComplaint() {
            if (!this.complaintEscalateForm.reason || !this.complaintEscalateForm.reason.trim()) {
                this.showToast("Please explain reasons for escalation", "error");
                return;
            }
            try {
                const res = await window.API.escalateComplaint(this.selectedComplaint.id, this.complaintEscalateForm.reason.trim());
                this.showToast(`Complaint ${res.complaint_id} escalated to Senior Administration`, "warning");
                this.complaintEscalateModalOpen = false;
                await this.loadWardenComplaints();
                await this.loadComplaintAnalytics();
            } catch (err) {
                this.showToast(`Escalation failed: ${err.message}`, "error");
            }
        },

        async handleWardenCloseComplaint(complaintId) {
            this.openConfirmModal(
                "Approve Grievance Closure",
                "Have you inspected and verified that the repair meets institutional standards and that the room/bed is restored?",
                async () => {
                    try {
                        const res = await window.API.closeComplaint(complaintId, "Resolution inspected and verified by Warden.");
                        this.showToast(`Grievance ${res.complaint_id} verified and closed`, "success");
                        await this.loadWardenComplaints();
                        await this.loadComplaintAnalytics();
                        this.loadMaintenanceTasks();
                        this.loadDashboardStats();
                    } catch (err) {
                        this.showToast(`Closure failed: ${err.message}`, "error");
                    }
                },
                "Approve Closure",
                "primary"
            );
        },

        // ==================== ATTENDANCE MODULE ====================
        async loadAttendanceSummary() {
            try {
                this.attendanceSummary = await window.API.getDailyAttendanceSummary(
                    this.attendanceDate,
                    this.attendanceHostelId || null
                );
            } catch (err) {
                console.error("Attendance summary error:", err);
            }
        },

        async loadStudentsForMarking() {
            try {
                const students = await window.API.getStudentsForMarking(
                    this.attendanceDate,
                    this.attendanceHostelId || null,
                    this.attendanceBuildingId || null,
                    this.attendanceFloorId || null,
                    this.attendanceRoomId || null
                );
                this.attendanceMarkingStudents = students.map(s => ({
                    student_id: s.student_id,
                    student_name: s.student_name,
                    roll_no: s.roll_no,
                    room_number: s.room_number,
                    bed_code: s.bed_code,
                    hostel_name: s.hostel_name,
                    status: s.marked_status || s.suggested_status || "Present",
                    remarks: s.marked_remarks || "",
                    is_already_marked: !!s.marked_status,
                    is_on_leave: !!s.is_on_leave
                }));
            } catch (err) {
                this.showToast(`Failed to load students for roll call: ${err.message}`, "error");
            }
        },

        async submitAttendanceSheet() {
            if (!this.attendanceMarkingStudents.length) {
                this.showToast("No resident students loaded for attendance marking.", "warning");
                return;
            }
            try {
                const records = this.attendanceMarkingStudents.map(s => ({
                    student_id: s.student_id,
                    status: s.status,
                    remarks: s.remarks || ""
                }));
                const res = await window.API.bulkMarkAttendance({
                    date: this.attendanceDate,
                    records,
                    hostel_id: this.attendanceHostelId ? parseInt(this.attendanceHostelId) : null
                });
                this.showToast(`Attendance saved: ${res.marked_count} marked, ${res.skipped_count} skipped.`, "success");
                await this.loadAttendanceSummary();
                await this.loadStudentsForMarking();
            } catch (err) {
                this.showToast(`Failed to submit attendance: ${err.message}`, "error");
            }
        },

        async loadAttendanceRecords() {
            try {
                const filters = {
                    date: this.attendanceDate,
                    hostel_id: this.attendanceHostelId || null,
                    status: this.attendanceFilterStatus !== "all" ? this.attendanceFilterStatus : null,
                    limit: 50,
                    offset: 0
                };
                const res = await window.API.getAttendanceRecords(filters);
                this.attendanceRecords = res.records || [];
                this.attendanceRecordsTotal = res.total || 0;
            } catch (err) {
                this.showToast(`Failed to load attendance records: ${err.message}`, "error");
            }
        },

        openAttendanceCorrectionModal(rec) {
            this.attendanceCorrectionModal = {
                open: true,
                attendanceId: rec.id,
                studentName: rec.student_name,
                date: rec.date,
                previousStatus: rec.status,
                newStatus: rec.status === "Present" ? "Absent" : "Present",
                reason: ""
            };
        },

        async submitAttendanceCorrection() {
            const m = this.attendanceCorrectionModal;
            if (!m.reason || m.reason.trim().length < 5) {
                this.showToast("Mandatory audit reason required (minimum 5 characters).", "error");
                return;
            }
            try {
                await window.API.correctAttendance(m.attendanceId, {
                    new_status: m.newStatus,
                    reason: m.reason.trim()
                });
                this.showToast(`Attendance status corrected to ${m.newStatus}`, "success");
                this.attendanceCorrectionModal.open = false;
                await this.loadAttendanceRecords();
                await this.loadAttendanceSummary();
            } catch (err) {
                this.showToast(`Correction failed: ${err.message}`, "error");
            }
        },

        async loadAttendanceReports() {
            try {
                this.attendanceReportData = await window.API.getAttendanceReports(
                    this.attendanceReportStartDate,
                    this.attendanceReportEndDate,
                    this.attendanceHostelId || null
                );
            } catch (err) {
                this.showToast(`Failed to generate attendance report: ${err.message}`, "error");
            }
        },

        // ==================== LEAVE & OUTPASS MODULE ====================
        async loadLeaveApplications() {
            try {
                const filters = {
                    status: this.leaveFilterStatus !== "all" ? this.leaveFilterStatus : null,
                    leave_type: this.leaveFilterType !== "all" ? this.leaveFilterType : null,
                    limit: 50,
                    offset: 0
                };
                const res = await window.API.getLeaveApplications(filters);
                this.leaveApplications = res.records || [];
                this.leaveApplicationsTotal = res.total || 0;
            } catch (err) {
                console.error("Failed to load leave applications:", err);
            }
        },

        async submitNewLeave(isDraft = false) {
            const form = this.newLeave;
            if (!form.reason || form.reason.trim().length < 5) {
                this.showToast("Please provide a valid leave reason (min 5 characters).", "error");
                return;
            }
            if (!form.destination || !form.destination.trim()) {
                this.showToast("Please enter travel destination address.", "error");
                return;
            }
            if (!form.emergency_contact || form.emergency_contact.trim().length < 7) {
                this.showToast("Please provide emergency contact number.", "error");
                return;
            }
            try {
                form.is_draft = isDraft;
                const res = await window.API.submitLeaveApplication(form);
                this.showToast(isDraft ? "Leave saved as Draft" : "Leave application submitted to Warden", "success");
                this.leaveSubTab = "my_leaves";
                await this.loadLeaveApplications();
            } catch (err) {
                this.showToast(`Submission failed: ${err.message}`, "error");
            }
        },

        async openLeaveDetails(leaveId) {
            try {
                this.selectedLeave = await window.API.getLeaveApplication(leaveId);
                this.leaveDetailModalOpen = true;
            } catch (err) {
                this.showToast(`Failed to load details: ${err.message}`, "error");
            }
        },

        async handleApproveLeave(leaveId) {
            this.openConfirmModal(
                "Approve Student Leave Request",
                "Approving this request will automatically generate a verified digital gate outpass for campus departure. Proceed?",
                async () => {
                    try {
                        const res = await window.API.approveLeaveApplication(leaveId, "Approved by Warden");
                        this.showToast(`Leave approved! Outpass #${res.outpass ? res.outpass.outpass_number : ''} issued.`, "success");
                        await this.loadLeaveApplications();
                        await this.loadOutpasses();
                        if (this.selectedLeave && this.selectedLeave.id === leaveId) {
                            this.selectedLeave = res;
                        }
                    } catch (err) {
                        this.showToast(`Approval failed: ${err.message}`, "error");
                    }
                },
                "Approve & Issue Outpass",
                "primary"
            );
        },

        openLeaveRejectModal(leaveId) {
            this.leaveRejectModalOpen = true;
            this.leaveRejectReason = "";
            if (this.selectedLeave && this.selectedLeave.id === leaveId) {
                // Already selected
            } else {
                this.openLeaveDetails(leaveId);
            }
        },

        async submitLeaveReject() {
            if (!this.leaveRejectReason || this.leaveRejectReason.trim().length < 5) {
                this.showToast("Mandatory justification reason required for rejection (min 5 characters).", "error");
                return;
            }
            try {
                const res = await window.API.rejectLeaveApplication(this.selectedLeave.id, this.leaveRejectReason.trim());
                this.showToast(`Leave request #${res.id} has been rejected.`, "warning");
                this.leaveRejectModalOpen = false;
                await this.loadLeaveApplications();
                if (this.selectedLeave) {
                    this.selectedLeave = res;
                }
            } catch (err) {
                this.showToast(`Rejection failed: ${err.message}`, "error");
            }
        },

        async loadOutpasses() {
            try {
                const filters = {
                    status: this.outpassFilterStatus !== "all" ? this.outpassFilterStatus : null,
                    limit: 50,
                    offset: 0
                };
                const res = await window.API.getOutpasses(filters);
                this.outpassesList = res.records || [];
                this.outpassesTotal = res.total || 0;
            } catch (err) {
                console.error("Failed to load outpasses:", err);
            }
        },

        async loadOverdueOutpasses() {
            try {
                this.overdueOutpassesList = await window.API.getOverdueOutpasses();
            } catch (err) {
                console.error("Failed to load overdue outpasses:", err);
            }
        },

        async handleVerifyGateExit(outpassRef) {
            try {
                const res = await window.API.verifyOutpassExit(outpassRef, this.outpassVerifyRemarks || "Verified gate exit");
                this.showToast(`Gate departure verified for student: Outpass #${res.outpass ? res.outpass.outpass_number : outpassRef}`, "success");
                await this.loadOutpasses();
                await this.loadOverdueOutpasses();
                this.outpassVerifyRemarks = "";
                if (this.selectedLeave) this.selectedLeave = res;
            } catch (err) {
                this.showToast(`Exit verification failed: ${err.message}`, "error");
            }
        },

        async handleVerifyGateReturn(outpassRef) {
            try {
                const res = await window.API.verifyOutpassReturn(outpassRef, this.outpassVerifyRemarks || "Verified gate return");
                this.showToast(`Gate return verified! Welcome back.`, "success");
                await this.loadOutpasses();
                await this.loadOverdueOutpasses();
                this.outpassVerifyRemarks = "";
                if (this.selectedLeave) this.selectedLeave = res;
            } catch (err) {
                this.showToast(`Return verification failed: ${err.message}`, "error");
            }
        },

        // ==================== VISITOR MANAGEMENT MODULE ====================
        async loadActiveVisitors() {
            try {
                this.activeVisitorsList = await window.API.getActiveVisitors();
            } catch (err) {
                console.error("Failed to load active visitors:", err);
            }
        },

        async loadVisitorLogs() {
            try {
                const filters = {
                    status: this.visitorFilterStatus !== "all" ? this.visitorFilterStatus : null,
                    search: this.visitorSearch || null,
                    limit: 50,
                    offset: 0
                };
                const res = await window.API.getVisitorLogs(filters);
                this.visitorLogs = res.records || [];
                this.visitorLogsTotal = res.total || 0;
            } catch (err) {
                console.error("Failed to load visitor logs:", err);
            }
        },

        async submitVisitorRegistration() {
            const form = this.newVisitor;
            if (!form.name || form.name.trim().length < 2) {
                this.showToast("Please enter visitor's legal name.", "error");
                return;
            }
            if (!form.phone || form.phone.trim().length < 7) {
                this.showToast("Please enter a valid contact phone number.", "error");
                return;
            }
            if (!form.id_proof_number || form.id_proof_number.trim().length < 4) {
                this.showToast("Please enter ID proof document number.", "error");
                return;
            }
            if (!form.purpose || form.purpose.trim().length < 3) {
                this.showToast("Please state visit purpose.", "error");
                return;
            }
            try {
                const res = await window.API.registerVisitor(form);
                this.showToast(`Visitor pass #${res.pass_number} created successfully!`, "success");
                this.visitorSubTab = "active";
                // Reset form
                this.newVisitor = {
                    name: "",
                    phone: "",
                    id_proof_type: "Aadhaar",
                    id_proof_number: "",
                    address: "",
                    student_id: 1,
                    purpose: "Family Visit",
                    expected_exit_time: "",
                    immediate_checkin: true
                };
                await this.loadActiveVisitors();
                await this.loadVisitorLogs();
            } catch (err) {
                this.showToast(`Registration failed: ${err.message}`, "error");
            }
        },

        async openVisitorDetails(id) {
            try {
                this.selectedVisitor = await window.API.getVisitorLog(id);
                this.visitorDetailModalOpen = true;
            } catch (err) {
                this.showToast(`Failed to load details: ${err.message}`, "error");
            }
        },

        async handleApproveVisitor(id) {
            this.openConfirmModal(
                "Approve Visitor Pass",
                "Do you authorize this visitor entry onto the hostel campus?",
                async () => {
                    try {
                        const res = await window.API.approveVisitor(id, "Approved by Warden");
                        this.showToast(`Pass #${res.pass_number} approved!`, "success");
                        await this.loadVisitorLogs();
                        await this.loadActiveVisitors();
                        if (this.selectedVisitor && this.selectedVisitor.id === id) {
                            this.selectedVisitor = res;
                        }
                    } catch (err) {
                        this.showToast(`Approval failed: ${err.message}`, "error");
                    }
                },
                "Approve Entry",
                "primary"
            );
        },

        openVisitorRejectModal(id) {
            this.visitorRejectModalOpen = true;
            this.visitorRejectReason = "";
            if (this.selectedVisitor && this.selectedVisitor.id === id) {
                // already selected
            } else {
                this.openVisitorDetails(id);
            }
        },

        async submitVisitorReject() {
            if (!this.visitorRejectReason || this.visitorRejectReason.trim().length < 5) {
                this.showToast("Mandatory reason required to reject visitor (min 5 characters).", "error");
                return;
            }
            try {
                const res = await window.API.rejectVisitor(this.selectedVisitor.id, this.visitorRejectReason.trim());
                this.showToast(`Visitor pass #${res.pass_number} denied.`, "warning");
                this.visitorRejectModalOpen = false;
                await this.loadVisitorLogs();
                if (this.selectedVisitor) this.selectedVisitor = res;
            } catch (err) {
                this.showToast(`Rejection failed: ${err.message}`, "error");
            }
        },

        async handleVisitorCheckIn(id) {
            try {
                const res = await window.API.checkInVisitor(id, "Gate check-in recorded");
                this.showToast(`Visitor checked in: Pass #${res.pass_number}`, "success");
                await this.loadActiveVisitors();
                await this.loadVisitorLogs();
                if (this.selectedVisitor) this.selectedVisitor = res;
            } catch (err) {
                this.showToast(`Check-in failed: ${err.message}`, "error");
            }
        },

        async handleVisitorCheckOut(id) {
            try {
                const res = await window.API.checkOutVisitor(id, "Gate check-out recorded");
                this.showToast(`Visitor checked out successfully.`, "success");
                await this.loadActiveVisitors();
                await this.loadVisitorLogs();
                if (this.selectedVisitor) this.selectedVisitor = res;
            } catch (err) {
                this.showToast(`Check-out failed: ${err.message}`, "error");
            }
        },

        // ==================== FEE & FINANCIAL MANAGEMENT METHODS ====================
        async loadFeeStructures() {
            try {
                this.feeStructures = await window.API.getFeeStructures();
            } catch (err) {
                console.error("Failed to load fee structures:", err);
            }
        },

        async loadInvoicesList() {
            try {
                const params = {};
                if (this.invoiceFilterStatus && this.invoiceFilterStatus !== 'all') {
                    params.status = this.invoiceFilterStatus;
                }
                if (this.invoiceSearch && this.invoiceSearch.trim()) {
                    params.invoice_number = this.invoiceSearch.trim();
                }
                const res = await window.API.getInvoices(params);
                this.invoicesList = res.records || [];
                this.invoicesTotal = res.total || 0;
            } catch (err) {
                console.error("Failed to load invoices:", err);
            }
        },

        async handleCreateFeeStructure() {
            try {
                const payload = {
                    ...this.newFeeStructure,
                    amount: parseFloat(this.newFeeStructure.amount),
                    late_fine_amount: parseFloat(this.newFeeStructure.late_fine_amount || 0),
                    hostel_id: this.newFeeStructure.hostel_id ? parseInt(this.newFeeStructure.hostel_id) : null
                };
                const res = await window.API.createFeeStructure(payload);
                this.showToast(`Fee structure '${res.name}' created successfully!`, "success");
                this.feeStructureModalOpen = false;
                await this.loadFeeStructures();
            } catch (err) {
                this.showToast(`Error: ${err.message}`, "error");
            }
        },

        async handleDeleteFeeStructure(id) {
            if (!confirm("Are you sure you want to deactivate this fee structure?")) return;
            try {
                const res = await window.API.deleteFeeStructure(id);
                this.showToast(res.message, "success");
                await this.loadFeeStructures();
            } catch (err) {
                this.showToast(`Error: ${err.message}`, "error");
            }
        },

        async handleCreateInvoice() {
            try {
                const payload = {
                    ...this.newInvoice,
                    student_id: parseInt(this.newInvoice.student_id),
                    fee_structure_id: this.newInvoice.fee_structure_id ? parseInt(this.newInvoice.fee_structure_id) : null,
                    total_amount: parseFloat(this.newInvoice.total_amount),
                    discount_amount: parseFloat(this.newInvoice.discount_amount || 0)
                };
                const res = await window.API.createInvoice(payload);
                this.showToast(`Invoice ${res.invoice_number} generated for student #${res.student_id}!`, "success");
                this.newInvoiceModalOpen = false;
                await this.loadInvoicesList();
            } catch (err) {
                this.showToast(`Error: ${err.message}`, "error");
            }
        },

        async handleCreateBulkInvoices() {
            try {
                if (!this.bulkInvoiceForm.fee_structure_id) {
                    this.showToast("Please select a fee structure.", "warning");
                    return;
                }
                const payload = {
                    ...this.bulkInvoiceForm,
                    fee_structure_id: parseInt(this.bulkInvoiceForm.fee_structure_id),
                    hostel_id: this.bulkInvoiceForm.hostel_id ? parseInt(this.bulkInvoiceForm.hostel_id) : null
                };
                const res = await window.API.createBulkInvoices(payload);
                this.showToast(`Bulk invoicing complete: ${res.invoices_created} invoices generated (${res.skipped_duplicates} skipped).`, "success");
                this.bulkInvoiceModalOpen = false;
                await this.loadInvoicesList();
            } catch (err) {
                this.showToast(`Error: ${err.message}`, "error");
            }
        },

        openDiscountModal(inv) {
            this.discountForm = {
                invoice_id: inv.id,
                amount: "",
                reason: ""
            };
            this.discountModalOpen = true;
        },

        async handleApplyDiscount() {
            try {
                const res = await window.API.applyInvoiceDiscount(
                    this.discountForm.invoice_id,
                    parseFloat(this.discountForm.amount),
                    this.discountForm.reason
                );
                this.showToast(`Discount of ₹${this.discountForm.amount} applied to ${res.invoice_number}`, "success");
                this.discountModalOpen = false;
                await this.loadInvoicesList();
                if (this.selectedInvoice && this.selectedInvoice.id === res.id) {
                    this.selectedInvoice = res;
                }
            } catch (err) {
                this.showToast(`Discount error: ${err.message}`, "error");
            }
        },

        openCancelModal(inv) {
            this.cancelForm = {
                invoice_id: inv.id,
                reason: ""
            };
            this.cancelInvoiceModalOpen = true;
        },

        async handleCancelInvoice() {
            try {
                const res = await window.API.cancelInvoice(this.cancelForm.invoice_id, this.cancelForm.reason);
                this.showToast(res.message, "success");
                this.cancelInvoiceModalOpen = false;
                await this.loadInvoicesList();
            } catch (err) {
                this.showToast(`Cancel error: ${err.message}`, "error");
            }
        },

        async viewInvoiceDetails(id) {
            try {
                this.selectedInvoice = await window.API.getInvoice(id);
                this.invoiceDetailModalOpen = true;
            } catch (err) {
                this.showToast(`Failed to load invoice: ${err.message}`, "error");
            }
        },

        async viewInvoiceReceipt(id) {
            try {
                this.activeReceipt = await window.API.getInvoiceReceipt(id);
                this.receiptModalOpen = true;
            } catch (err) {
                this.showToast(`Failed to load receipt: ${err.message}`, "error");
            }
        }
    }));
});
