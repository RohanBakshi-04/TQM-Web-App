/**
 * Alpine.js Application Controller with RBAC Multi-Stakeholder Support
 * Unified Platform for Intelligent Hostel Administration and Management
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
            { id: 2, title: "High Performance Active", message: "Database query response time running under 10ms target.", time: "5m ago", unread: true, type: "success" },
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

        // Registration State
        authTab: 'login', // 'login' or 'register'
        registerLoading: false,
        registerError: '',
        registerForm: {
            first_name: '',
            last_name: '',
            email: '',
            phone: '',
            username: '',
            password: '',
            confirmPassword: '',
            role: 'student', // student, staff, parent_guardian
            gender: 'Male', // Male, Female, Other
            enrollment_no: '',
            branch: 'CSE',
            specialization: 'warden',
            child_identifier: '',
            relationship: 'Father',
            hostel_id: ''
        },
        authorizedHostelsList: [],
        pendingRegistrations: [],
        pendingRegistrationsLoading: false,

        // Personal Student Attendance State
        myAttendanceData: null,
        myAttendanceLoading: false,
        myAttendanceTodayStatus: 'Not Marked',
        myAttendanceFilter: 'all',

        // System Health & Telemetry State
        systemHealth: {
            status: "connecting",
            database: { status: "checking", engine: "--", journal_mode: "--", ping_latency_ms: 0 },
            q05_telemetry: { meets_sla: false, sla_target_ms: 10.0 },
            serverLatencyMs: 0
        },
        healthCheckInterval: null,

        // Primary Core Stakeholders (Simplified for clear operational governance)
        rolePresets: [
            { role: "super_admin", username: "superadmin", label: "Administrator", icon: "fa-shield-halved", badge: "Governance", desc: "Institutional oversight, room allocations, student admissions, finance & system settings" },
            { role: "warden", username: "warden", label: "Hostel Warden", icon: "fa-user-tie", badge: "Welfare & Discipline", desc: "Student welfare, daily roll-calls, leaves, digital gate outpasses & discipline" },
            { role: "maintenance_staff", username: "maintenance", label: "Staff Member", icon: "fa-user-gear", badge: "Operations", desc: "Maintenance tasks (electrician, plumber, carpentry), mess operations & gate check-ins" },
            { role: "student", username: "rohan", label: "Student Resident", icon: "fa-graduation-cap", badge: "Resident Portal", desc: "Personal room details, daily attendance [Present/Absent], leave requests & grievances" },
            { role: "parent_guardian", username: "parent", label: "Parent / Guardian", icon: "fa-people-roof", badge: "Family Portal", desc: "Ward daily attendance status, fee dues, payment receipts & warden communication" }
        ],
        // Role-Specific Navigation Mappings
        roleNavigationMap: {
            super_admin: [
                { id: "dashboard", label: "System Overview", icon: "fa-gauge-high" },
                { id: "registrations", label: "Registration Approvals", icon: "fa-user-check" },
                { id: "allocations", label: "Room Allocations", icon: "fa-bed" },
                { id: "attendance", label: "Attendance Control", icon: "fa-clipboard-user" },
                { id: "leaves", label: "Leaves & Outpasses", icon: "fa-id-badge" },
                { id: "visitors", label: "Visitor Management", icon: "fa-user-clock" },
                { id: "finance", label: "Fee & Finance", icon: "fa-file-invoice-dollar" },
                { id: "mess", label: "Mess & Dining", icon: "fa-utensils" },
                { id: "inventory", label: "Inventory & Stock", icon: "fa-boxes-stacked" },
                { id: "announcements", label: "Announcements", icon: "fa-bullhorn" },
                { id: "admin", label: "System Admin", icon: "fa-sliders" }
            ],
            hostel_admin: [
                { id: "dashboard", label: "Hostel Dashboard", icon: "fa-gauge-high" },
                { id: "registrations", label: "Registration Approvals", icon: "fa-user-check" },
                { id: "allocations", label: "Rooms & Allocations", icon: "fa-bed" },
                { id: "attendance", label: "Student Attendance", icon: "fa-clipboard-user" },
                { id: "leaves", label: "Leaves & Outpass", icon: "fa-id-badge" },
                { id: "visitors", label: "Hostel Visitors", icon: "fa-user-clock" },
                { id: "mess", label: "Hostel Mess", icon: "fa-utensils" },
                { id: "inventory", label: "Hostel Supplies", icon: "fa-boxes-stacked" },
                { id: "announcements", label: "Announcements", icon: "fa-bullhorn" }
            ],
            warden: [
                { id: "dashboard", label: "Warden Dashboard", icon: "fa-gauge-high" },
                { id: "registrations", label: "Registration Approvals", icon: "fa-user-check" },
                { id: "attendance", label: "Daily Roll-Call", icon: "fa-clipboard-user" },
                { id: "leaves", label: "Leave Approvals", icon: "fa-id-badge" },
                { id: "visitors", label: "Visitor Management", icon: "fa-user-clock" },
                { id: "allocations", label: "Resident Directory", icon: "fa-bed" },
                { id: "announcements", label: "Broadcast Notices", icon: "fa-bullhorn" }
            ],
            assistant_warden: [
                { id: "dashboard", label: "Floor Dashboard", icon: "fa-gauge-high" },
                { id: "registrations", label: "Registration Approvals", icon: "fa-user-check" },
                { id: "attendance", label: "Block Roll-Call", icon: "fa-clipboard-user" },
                { id: "leaves", label: "Leave Review Queue", icon: "fa-id-badge" },
                { id: "allocations", label: "Room Checks", icon: "fa-bed" },
                { id: "announcements", label: "Hostel Notices", icon: "fa-bullhorn" }
            ],
            student: [
                { id: "dashboard", label: "My Dashboard", icon: "fa-gauge-high" },
                { id: "allocations", label: "My Room & Bed", icon: "fa-bed" },
                { id: "attendance", label: "My Attendance", icon: "fa-clipboard-user" },
                { id: "leaves", label: "My Leaves & Outpasses", icon: "fa-id-badge" },
                { id: "finance", label: "My Fees & Receipts", icon: "fa-file-invoice-dollar" },
                { id: "mess", label: "Mess Menu", icon: "fa-utensils" },
                { id: "announcements", label: "Announcements", icon: "fa-bullhorn" }
            ],
            accountant: [
                { id: "dashboard", label: "Finance Dashboard", icon: "fa-gauge-high" },
                { id: "finance", label: "Invoices & Billing", icon: "fa-file-invoice-dollar" },
                { id: "announcements", label: "Fee Circulars", icon: "fa-bullhorn" }
            ],
            mess_manager: [
                { id: "dashboard", label: "Mess Dashboard", icon: "fa-gauge-high" },
                { id: "mess", label: "Weekly Menu & Meals", icon: "fa-utensils" },
                { id: "inventory", label: "Pantry & Stock", icon: "fa-boxes-stacked" },
                { id: "announcements", label: "Mess Notices", icon: "fa-bullhorn" }
            ],
            maintenance_staff: [
                { id: "dashboard", label: "Maintenance Console", icon: "fa-gauge-high" },
                { id: "inventory", label: "Tools & Spares", icon: "fa-boxes-stacked" },
                { id: "announcements", label: "Announcements", icon: "fa-bullhorn" }
            ],
            security_guard: [
                { id: "dashboard", label: "Gate Security Console", icon: "fa-gauge-high" },
                { id: "leaves", label: "Gate Outpass Check", icon: "fa-id-badge" },
                { id: "visitors", label: "Visitor Passes", icon: "fa-user-clock" },
                { id: "announcements", label: "Announcements", icon: "fa-bullhorn" }
            ],
            admission_officer: [
                { id: "dashboard", label: "Admissions Dashboard", icon: "fa-gauge-high" },
                { id: "allocations", label: "Room Availability", icon: "fa-bed" },
                { id: "announcements", label: "Admissions Notices", icon: "fa-bullhorn" }
            ],
            parent_guardian: [
                { id: "dashboard", label: "Ward Dashboard", icon: "fa-gauge-high" },
                { id: "attendance", label: "Ward Attendance", icon: "fa-clipboard-user" },
                { id: "leaves", label: "Ward Leaves", icon: "fa-id-badge" },
                { id: "finance", label: "Fee Dues & Receipts", icon: "fa-file-invoice-dollar" },
                { id: "announcements", label: "Announcements", icon: "fa-bullhorn" }
            ],
            auditor: [
                { id: "dashboard", label: "Compliance Dashboard", icon: "fa-gauge-high" },
                { id: "admin", label: "System Audit Logs", icon: "fa-sliders" },
                { id: "finance", label: "Financial Ledger Audit", icon: "fa-file-invoice-dollar" }
            ]
        },

        get authorizedNavItems() {
            if (!this.isAuthenticated) {
                return [
                    { id: "welcome", label: "Overview", icon: "fa-compass" },
                    { id: "login", label: "Sign In", icon: "fa-right-to-bracket" }
                ];
            }
            const roleKey = this.activeRoleView || (this.userRoles && this.userRoles[0]) || "student";
            return this.roleNavigationMap[roleKey] || this.roleNavigationMap["student"];
        },


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

        registrationFilterRole: "all",

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

        // Payments & Refunds State
        paymentsList: [],
        paymentsTotal: 0,
        paymentSearch: "",
        paymentMethodFilter: "all",
        refundsList: [],
        refundsTotal: 0,
        recordPaymentModalOpen: false,
        reversePaymentModalOpen: false,
        requestRefundModalOpen: false,
        paymentReceiptModalOpen: false,
        activePaymentReceipt: null,
        newPayment: {
            invoice_id: null,
            amount: "",
            payment_method: "UPI",
            transaction_id: "",
            notes: ""
        },
        reversePaymentForm: {
            payment_id: null,
            reason: ""
        },
        newRefund: {
            payment_id: null,
            amount: "",
            reason: "",
            refund_method: "Bank_Transfer"
        },
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

        // Financial Dashboard & Reports State
        financialDashboard: null,
        financialReportType: "collections",
        financialReportFilters: {
            start_date: "",
            end_date: "",
            payment_method: "",
            hostel_id: "",
            status: ""
        },
        financialReportData: null,
        financialReportLoading: false,

        dashboardStats: {
            hostels: { total: 1, rooms: 3, beds: 6, occupied_beds: 2, available_beds: 4, occupancy_rate: 33.3 },
            students: { total: 3, active: 3 },
            users: { total: 12 },
            finance: { total_invoices: 0, total_invoiced: 0, total_collected: 0, outstanding_dues: 0 },
            operations: { pending_complaints: 0, pending_leaves: 0, active_visitors: 0, pending_admissions: 0, pending_maintenance: 0 },
            recent_activity: []
        },

        // Mess Management State
        messSubTab: "dashboard", // "dashboard" | "menus" | "subscriptions" | "attendance"
        messDashboardData: null,
        messMenusList: [],
        messSubscriptionsList: [],
        mealAttendanceList: [],
        messLoading: false,
        messFilterHostelId: null,
        messFilterDate: new Date().toISOString().split("T")[0],
        messFilterMealType: "Breakfast",
        messMenuModalOpen: false,
        messSubscriptionModalOpen: false,
        mealAttendanceModalOpen: false,
        qrAttendanceModalOpen: false,

        newMessMenu: {
            hostel_id: 1,
            meal_date: new Date().toISOString().split("T")[0],
            meal_type: "Breakfast",
            title: "",
            description: "",
            items: "",
            start_time: "07:30",
            end_time: "09:30",
            is_published: true,
            audit_reason: "Standard daily meal menu"
        },

        newMessSubscription: {
            student_id: null,
            plan_type: "Monthly",
            start_date: new Date().toISOString().split("T")[0],
            end_date: new Date(Date.now() + 30 * 86400000).toISOString().split("T")[0],
            dietary_preference: "Vegetarian",
            monthly_rate: 3500.0,
            auto_generate_invoice: true
        },

        newMealAttendance: {
            student_id: null,
            hostel_id: 1,
            meal_date: new Date().toISOString().split("T")[0],
            meal_type: "Breakfast",
            verification_method: "Manual",
            remarks: "Verified by mess staff"
        },

        qrMealAttendance: {
            qr_token: "",
            hostel_id: 1,
            meal_date: new Date().toISOString().split("T")[0],
            meal_type: "Breakfast"
        },

        // Inventory & Stock Management State
        inventorySubTab: "dashboard", // "dashboard" | "items" | "inward" | "outward" | "suppliers"
        inventoryDashboardData: null,
        inventoryCategoriesList: [],
        suppliersList: [],
        inventoryItemsList: [],
        inventoryTransactionsList: [],
        inventoryLoading: false,
        inventoryFilterCategory: null,
        inventoryFilterStatus: null,
        inventorySearchTerm: "",
        inventoryItemModalOpen: false,
        stockInwardModalOpen: false,
        stockOutwardModalOpen: false,
        stockAdjustmentModalOpen: false,
        supplierModalOpen: false,

        newInventoryItem: {
            item_code: "",
            name: "",
            category_id: 1,
            unit: "kg",
            quantity_in_stock: 0.0,
            min_reorder_level: 10.0,
            max_threshold: 100.0,
            unit_price: 0.0,
            supplier_id: null,
            location: "Main Store Room",
            expiry_date: "",
            status: "Active"
        },

        newStockInward: {
            item_id: null,
            quantity: 1.0,
            unit_price: 0.0,
            supplier_id: null,
            invoice_ref: "",
            location: "Main Store Room",
            remarks: "Routine stock procurement inward"
        },

        newStockOutward: {
            item_id: null,
            quantity: 1.0,
            department: "Mess Kitchen",
            issued_to: "Head Chef",
            remarks: "Daily meal prep consumption"
        },

        newStockAdjustment: {
            item_id: null,
            adjustment_type: "Wastage",
            quantity_change: -1.0,
            reason: "Audit discrepancy adjustment",
            from_location: "Main Store Room",
            to_location: ""
        },

        newSupplier: {
            name: "",
            code: "",
            contact_person: "",
            phone: "",
            email: "",
            address: "",
            tax_id: "",
            category: "Food & Groceries",
            is_active: true
        },

        async init() {
            // Load authorized hostels for warden registrations and room allocations
            this.loadAuthorizedHostels();

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

            // Real-Time Cross-Tab Registration Approvals Synchronization
            if (window.BroadcastChannel) {
                try {
                    this.regSyncChannel = new BroadcastChannel('hms_registrations_sync');
                    this.regSyncChannel.onmessage = (event) => {
                        if (this.isAuthenticated) {
                            this.loadPendingRegistrations(true);
                            if (this.activeRoleView === 'warden' || this.activeRoleView === 'super_admin') {
                                this.loadDashboardStats();
                            }
                        }
                    };
                } catch (_) {}
            }
            window.addEventListener('storage', (e) => {
                if (e.key === 'hms_last_reg_sync' && this.isAuthenticated) {
                    this.loadPendingRegistrations(true);
                    if (this.activeRoleView === 'warden' || this.activeRoleView === 'super_admin') {
                        this.loadDashboardStats();
                    }
                }
            });

            // Active Queue Auto-Sync: Poll every 3 seconds without refreshing the whole page
            setInterval(() => {
                if (this.isAuthenticated && (this.activeSection === 'registrations' || this.activeSection === 'dashboard')) {
                    this.loadPendingRegistrations(true);
                }
            }, 3000);
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
            } else if (this.activeSection === "dashboard") {
                const currentPreset = this.rolePresets.find(p => p.role === this.activeRoleView);
                crumbs.push({ label: "Stakeholder Portal", section: "dashboard" });
                crumbs.push({ label: currentPreset ? currentPreset.label : "Dashboard", section: "dashboard" });
            } else if (this.activeSection === "allocations") {
                crumbs.push({ label: "Room Allocations", section: "allocations" });
            } else if (this.activeSection === "attendance") {
                crumbs.push({ label: "Attendance Management", section: "attendance" });
            } else if (this.activeSection === "leaves") {
                crumbs.push({ label: "Leaves & Outpass", section: "leaves" });
            } else if (this.activeSection === "visitors") {
                crumbs.push({ label: "Visitor Management", section: "visitors" });
            } else if (this.activeSection === "finance") {
                crumbs.push({ label: "Fee & Financials", section: "finance" });
            } else if (this.activeSection === "mess") {
                crumbs.push({ label: "Mess & Dining", section: "mess" });
            } else if (this.activeSection === "inventory") {
                crumbs.push({ label: "Inventory & Stock", section: "inventory" });
            } else if (this.activeSection === "announcements") {
                crumbs.push({ label: "Announcements", section: "announcements" });
            } else if (this.activeSection === "registrations") {
                crumbs.push({ label: "Registration Approvals", section: "registrations" });
            } else if (this.activeSection === "admin") {
                crumbs.push({ label: "System Administration", section: "admin" });
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

        
        async quickDemoLogin(roleKey) {
            const preset = this.rolePresets.find(p => p.role === roleKey);
            if (!preset) return;
            this.loginCredentials.username = preset.username;
            this.loginCredentials.password = "Password123!";
            try {
                this.loginLoading = true;
                const authData = await window.API.login(this.loginCredentials.username, this.loginCredentials.password);
                this.onAuthenticated(authData.user);
                this.activeRoleView = roleKey;
                this.activeSection = "dashboard";
                this.showToast(`Logged in as ${preset.label}`, "success");
            } catch (err) {
                this.showToast(err.message || "Login failed", "error");
            } finally {
                this.loginLoading = false;
            }
        },
selectPreset(preset) {
            this.loginCredentials.username = preset.username;
            this.loginCredentials.password = "Password123!";
            this.loginError = "";
            this.loginNotice = `Loaded credentials for ${preset.label} (${preset.username})`;
        },

        async loadAuthorizedHostels() {
            try {
                this.authorizedHostelsList = await window.API.getAuthorizedHostels();
            } catch (err) {
                console.warn("Could not load authorized hostels:", err);
            }
        },

        openChangePasswordModal() {
            this.changePasswordForm = {
                current_password: '',
                new_password: '',
                confirm_password: '',
                show_current: false,
                show_new: false,
                show_confirm: false
            };
            this.changePasswordModalOpen = true;
        },

        async submitChangePassword() {
            const cur = (this.changePasswordForm.current_password || '').trim();
            const np = (this.changePasswordForm.new_password || '').trim();
            const cp = (this.changePasswordForm.confirm_password || '').trim();

            if (!cur) {
                this.showToast("Please enter your current password.", "warning");
                return;
            }
            if (np.length < 8) {
                this.showToast("New password must be at least 8 characters long.", "warning");
                return;
            }
            if (np !== cp) {
                this.showToast("New password and confirmation do not match.", "warning");
                return;
            }

            this.changePasswordLoading = true;
            try {
                const res = await window.API.changePassword(cur, np);
                this.showToast(res.message || "Password updated successfully! Your credentials have been saved.", "success");
                this.changePasswordModalOpen = false;
                this.changePasswordForm = {
                    current_password: '',
                    new_password: '',
                    confirm_password: '',
                    show_current: false,
                    show_new: false,
                    show_confirm: false
                };
            } catch (err) {
                this.showToast(err.message || "Failed to change password. Please verify your current password.", "error");
            } finally {
                this.changePasswordLoading = false;
            }
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

            this.loadPendingRegistrations();
            if (this.activeRoleView === "student") {
                this.loadMyStudentProfile();
                this.loadMyComplaints();
                this.loadMyAttendance();
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

        async handleRegister() {
            this.registerError = '';

            // 1. Password validation
            if (this.registerForm.password !== this.registerForm.confirmPassword) {
                this.registerError = 'Passwords do not match. Please re-enter.';
                this.showToast(this.registerError, 'error');
                return;
            }
            if (this.registerForm.password.length < 6) {
                this.registerError = 'Password must be at least 6 characters.';
                this.showToast(this.registerError, 'error');
                return;
            }

            // 2. Name validation (alphabetic only)
            const nameRegex = /^[a-zA-Z\s'-]{1,50}$/;
            const firstName = (this.registerForm.first_name || '').trim();
            const lastName = (this.registerForm.last_name || '').trim();
            if (!firstName || !nameRegex.test(firstName)) {
                this.registerError = 'First name must contain only alphabetic letters (no numbers or symbols).';
                this.showToast(this.registerError, 'error');
                return;
            }
            if (!lastName || !nameRegex.test(lastName)) {
                this.registerError = 'Last name must contain only alphabetic letters (no numbers or symbols).';
                this.showToast(this.registerError, 'error');
                return;
            }

            // 3. Email validation (must contain @ and valid domain)
            const emailVal = (this.registerForm.email || '').trim();
            const emailRegex = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
            if (!emailVal || !emailVal.includes('@') || !emailRegex.test(emailVal)) {
                this.registerError = "Invalid email: must contain '@' and a valid domain (e.g. name@univ.edu).";
                this.showToast(this.registerError, 'error');
                return;
            }

            // 4. Phone number validation (strictly digits 0-9, up to 10 digits)
            const rawPhone = (this.registerForm.phone || '').trim();
            if (!rawPhone) {
                this.registerError = 'Phone number is required. Please provide a 10-digit mobile number.';
                this.showToast(this.registerError, 'error');
                return;
            }
            if (!/^\d+$/.test(rawPhone)) {
                this.registerError = "Invalid phone number: only digits (0-9) are allowed. Characters like letters or '@' are not allowed.";
                this.showToast(this.registerError, 'error');
                return;
            }
            if (rawPhone.length !== 10) {
                this.registerError = `Phone number must be exactly 10 digits. Provided: ${rawPhone.length} digits.`;
                this.showToast(this.registerError, 'error');
                return;
            }

            // 5. Username validation
            const usernameVal = (this.registerForm.username || '').trim();
            if (!/^[a-zA-Z0-9_.-]{3,30}$/.test(usernameVal)) {
                this.registerError = 'Username must be 3-30 characters containing only letters, numbers, hyphens, or underscores.';
                this.showToast(this.registerError, 'error');
                return;
            }

            // 6. Role-specific validation
            if (this.registerForm.role === 'student' && this.registerForm.enrollment_no) {
                const enrollVal = this.registerForm.enrollment_no.trim();
                if (enrollVal && !/^[a-zA-Z0-9_-]{2,30}$/.test(enrollVal)) {
                    this.registerError = 'Enrollment / Roll number must be alphanumeric.';
                    this.showToast(this.registerError, 'error');
                    return;
                }
            }

            if (this.registerForm.role === 'staff' && (this.registerForm.specialization === 'warden' || this.registerForm.specialization === 'hostel_warden')) {
                if (!this.registerForm.hostel_id) {
                    this.registerError = "Please select an authorized campus hostel for the Hostel Warden assignment.";
                    this.showToast(this.registerError, 'error');
                    return;
                }
                const chosenHostel = (this.authorizedHostelsList || []).find(h => String(h.id) === String(this.registerForm.hostel_id));
                if (chosenHostel && chosenHostel.is_full) {
                    this.registerError = `Not Required: ${chosenHostel.name} has already reached maximum warden capacity (${chosenHostel.warden_count}/${chosenHostel.max_wardens || 2}). Warden capacity is full. Please select another authorized hostel.`;
                    this.showToast(this.registerError, 'error');
                    return;
                }
            }

            if (this.registerForm.role === 'parent_guardian' && !this.registerForm.child_identifier) {
                this.registerError = "Please specify your child's Student Roll Number or University Email.";
                this.showToast(this.registerError, 'error');
                return;
            }
            this.registerLoading = true;
            try {
                const payload = {
                    username: this.registerForm.username,
                    email: this.registerForm.email,
                    password: this.registerForm.password,
                    first_name: this.registerForm.first_name,
                    last_name: this.registerForm.last_name,
                    phone: this.registerForm.phone || null,
                    gender: this.registerForm.gender || 'Male',
                    role: this.registerForm.role,
                    enrollment_no: this.registerForm.role === 'student' ? (this.registerForm.enrollment_no || null) : null,
                    branch: this.registerForm.role === 'student' ? this.registerForm.branch : null,
                    specialization: this.registerForm.role === 'staff' ? this.registerForm.specialization : null,
                    hostel_id: (this.registerForm.role === 'staff' && this.registerForm.hostel_id) ? parseInt(this.registerForm.hostel_id) : null,
                    child_identifier: this.registerForm.role === 'parent_guardian' ? this.registerForm.child_identifier : null,
                    relationship: this.registerForm.role === 'parent_guardian' ? this.registerForm.relationship : null
                };
                const authData = await window.API.register(payload);
                if (authData.access_token && authData.status !== 'Pending_Approval') {
                    this.onAuthenticated(authData.user);
                    this.activeSection = 'dashboard';
                    this.showToast(`Account created successfully! Welcome, ${authData.user.first_name}!`, 'success');
                } else {
                    this.authTab = 'login';
                    this.loginNotice = authData.message || 'Registration submitted! Awaiting required authorization.';
                    this.showToast(authData.message || 'Registration submitted for authorization!', 'info');
                }
                // Notify open Admin and Warden tabs instantly
                if (window.BroadcastChannel) {
                    try {
                        const channel = new BroadcastChannel('hms_registrations_sync');
                        channel.postMessage({ type: 'NEW_REGISTRATION_SUBMITTED', timestamp: Date.now() });
                        channel.close();
                    } catch (_) {}
                }
                localStorage.setItem('hms_last_reg_sync', Date.now().toString());
                // Reset passwords
                this.registerForm.password = '';
                this.registerForm.confirmPassword = '';
            } catch (err) {
                this.registerError = err.message || 'Registration failed.';
                this.showToast(this.registerError, 'error');
            } finally {
                this.registerLoading = false;
            }
        },

        async loadPendingRegistrations(silent = false, userTriggered = false) {
            if (!this.isAuthenticated) return;
            if (!silent) this.pendingRegistrationsLoading = true;
            try {
                const data = await window.API.getPendingRegistrations();
                this.pendingRegistrations = data || [];
                if (userTriggered) {
                    this.showToast(`Registration queue updated: ${this.pendingRegistrations.length} pending`, 'info');
                }
            } catch (e) {
                console.warn('Failed to load pending registrations:', e);
                if (!silent) this.pendingRegistrations = [];
            } finally {
                if (!silent) this.pendingRegistrationsLoading = false;
            }
        },

        async handleRegistrationAction(reqId, action, reason = '') {
            // Instant optimistic update: remove immediately from local view
            const removedItem = (this.pendingRegistrations || []).find(r => r.id === reqId);
            this.pendingRegistrations = (this.pendingRegistrations || []).filter(r => r.id !== reqId);

            try {
                const res = await window.API.processRegistrationAction(reqId, action, reason);
                this.showToast(res.message || `Registration request ${action}ed successfully.`, 'success');

                // Broadcast instantly to all other browser tabs (e.g. Warden & Admin simultaneously sync!)
                if (window.BroadcastChannel) {
                    try {
                        const channel = new BroadcastChannel('hms_registrations_sync');
                        channel.postMessage({ type: 'REGISTRATION_ACTION_COMPLETED', reqId, action, timestamp: Date.now() });
                        channel.close();
                    } catch (_) {}
                }
                localStorage.setItem('hms_last_reg_sync', Date.now().toString());

                await this.loadPendingRegistrations(true);
                if (this.userRoles.includes('super_admin') || this.userRoles.includes('hostel_admin') || this.userRoles.includes('warden')) {
                    this.loadDashboardStats();
                    if (typeof this.loadAdminUsers === 'function') this.loadAdminUsers();
                    if (typeof this.loadUsers === 'function') this.loadUsers();
                }
            } catch (err) {
                // Rollback optimistic update on error
                if (removedItem) {
                    this.pendingRegistrations.unshift(removedItem);
                }
                this.showToast(err.message || `Failed to ${action} registration.`, 'error');
            }
        },

        async loadMyAttendance() {
            this.myAttendanceLoading = true;
            try {
                const data = await window.API.getMyAttendance();
                this.myAttendanceData = data;
                if (data.today_status) {
                    this.myAttendanceTodayStatus = data.today_status;
                } else if (data.history && data.history.length > 0) {
                    const todayStr = new Date().toISOString().split('T')[0];
                    const todayRec = data.history.find(h => h.date === todayStr);
                    this.myAttendanceTodayStatus = todayRec ? todayRec.status : 'Not Marked';
                } else {
                    this.myAttendanceTodayStatus = 'Not Marked';
                }
            } catch (err) {
                console.warn('Could not load student personal attendance:', err.message);
            } finally {
                this.myAttendanceLoading = false;
            }
        },

        hasRole(roleName) {
            return this.userRoles.includes(roleName) || this.userRoles.includes("super_admin");
        },

        hasPermission(permName) {
            return this.userPermissions.includes(permName) || this.userRoles.includes("super_admin");
        },

        async handleSwitchRole(roleKey) {
            // Strictly reject if target role is not assigned to current authenticated user
            if (!this.userRoles || !this.userRoles.includes(roleKey)) {
                this.showToast(`Access Denied: Role '${roleKey}' is not assigned to your account.`, "error");
                return;
            }
            try {
                // Backend verification and session rotation
                const res = await window.API.switchRole(roleKey);
                if (res && res.success) {
                    this.activeRoleView = res.active_role;
                    if (res.permissions) {
                        this.userPermissions = res.permissions;
                    }
                    if (this.currentUser) {
                        this.currentUser.active_role = res.active_role;
                    }
                    this.activeSection = "dashboard";
                    this.loadDashboardStats();
                    this.loadPendingRegistrations();
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
                    this.showToast(`Active role switched to ${preset?.label || roleKey}`, "success");
                }
            } catch (err) {
                this.showToast(err.message || "Failed to switch active role", "error");
            }
        },

        switchRoleDashboard(roleKey) {
            return this.handleSwitchRole(roleKey);
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
            const sidInput = (this.allocationForm.student_id || "").toString().trim();
            if (!sidInput || !this.allocationForm.bed_id || !this.allocationForm.start_date) {
                this.showToast("Please provide Student ID, Bed ID, and Start Date.", "warning");
                return;
            }
            try {
                const payload = {
                    student_id: sidInput,
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
                this.showToast(`Validation Error: ${err.message}`, "error");
            }
        },

        async getSuggestionsForStudent(studentId) {
            const sid = (studentId || "").toString().trim();
            if (!sid) {
                this.showToast("Please enter a valid Student ID first (e.g. STU-202611-0089)", "warning");
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

            // Route guard: unauthenticated users cannot access operational sections
            if (!this.isAuthenticated) {
                if (section !== "welcome" && section !== "login") {
                    this.showToast("Please sign in to access operational modules.", "info");
                    this.activeSection = "login";
                    this.mobileMenuOpen = false;
                    return;
                }
            } else {
                // Route guard for authenticated users: verify permission for section
                if (section !== "welcome" && section !== "dashboard") {
                    const allowed = this.authorizedNavItems.some(item => item.id === section);
                    if (!allowed && !this.hasRole("super_admin")) {
                        this.showToast("Access Restricted: This section is not authorized for your role.", "error");
                        this.activeSection = "dashboard";
                        this.mobileMenuOpen = false;
                        return;
                    }
                }
            }

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
                if (this.activeRoleView === 'student' || this.activeRoleView === 'parent_guardian') {
                    this.loadMyAttendance();
                } else {
                    this.loadAttendanceSummary();
                    this.loadStudentsForMarking();
                }
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
            } else if (section === 'mess') {
                if (this.activeRoleView === 'student' || this.activeRoleView === 'parent_guardian') {
                    this.loadMessMenus();
                } else {
                    this.loadMessDashboard();
                    this.loadMessMenus();
                    this.loadMessSubscriptions();
                }
            } else if (section === 'inventory') {
                this.loadInventoryDashboard();
                this.loadInventoryItems();
                this.loadSuppliers();
            } else if (section === 'registrations') {
                this.loadPendingRegistrations();
            } else if (section === 'announcements') {
                this.loadAnnouncements();
            } else if (section === 'admin') {
                this.loadAdminSettings();
                this.loadAdminUsers();
                this.loadAdminRolesAndPermissions();
                this.loadAdminAuditLogs();
                this.loadAdminBackups();
            }
            this.navigationLatencyMs = parseFloat((performance.now() - t0).toFixed(2));
        },

        selectSearchResult(item) {
            this.searchModalOpen = false;
            if (item.category === 'allocations') {
                this.navigateTo('allocations');
            } else if (item.category === 'hostels' || item.category === 'rooms') {
                this.navigateTo('allocations');
            } else if (item.category === 'students') {
                this.navigateTo('allocations');
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
        get filteredMaintenanceTasks() {
            if (!this.maintenanceTasks) return [];
            if (this.maintenanceFilterCategory === 'all') return this.maintenanceTasks;
            const filter = (this.maintenanceFilterCategory || '').toLowerCase();
            return this.maintenanceTasks.filter(t => {
                const cat = (t.category || '').toLowerCase();
                const title = (t.title || '').toLowerCase();
                const desc = (t.description || '').toLowerCase();
                const combined = `${cat} ${title} ${desc}`;
                if (filter === 'electrician' || filter === 'electrical') return combined.includes('elect') || combined.includes('power') || combined.includes('light');
                if (filter === 'plumber' || filter === 'plumbing') return combined.includes('plumb') || combined.includes('water') || combined.includes('pipe') || combined.includes('tap') || combined.includes('drain');
                if (filter === 'chef' || filter === 'kitchen' || filter === 'mess') return combined.includes('mess') || combined.includes('kitchen') || combined.includes('cook') || combined.includes('food') || combined.includes('dining');
                if (filter === 'carpenter' || filter === 'carpentry') return combined.includes('carpent') || combined.includes('wood') || combined.includes('door') || combined.includes('lock') || combined.includes('bed') || combined.includes('chair');
                return combined.includes(filter);
            });
        },

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
            if (this.activeRoleView === 'student' || this.activeRoleView === 'parent_guardian') {
                return;
            }
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
            if (this.activeRoleView === 'student' || this.activeRoleView === 'parent_guardian') {
                return;
            }
            try {
                let d = (this.attendanceDate || "").trim();
                if (!d) {
                    d = new Date().toISOString().split("T")[0];
                    this.attendanceDate = d;
                }
                const students = await window.API.getStudentsForMarking(
                    d,
                    this.attendanceHostelId || null,
                    this.attendanceBuildingId || null,
                    this.attendanceFloorId || null,
                    this.attendanceRoomId || null
                );
                this.attendanceMarkingStudents = (students || []).map(s => {
                    let stStatus = s.marked_status || s.suggested_status || "Present";
                    if (stStatus === "On_Leave") stStatus = "On Leave";
                    return {
                        student_id: s.student_id,
                        student_name: s.student_name,
                        roll_no: s.roll_no,
                        room_number: s.room_number,
                        bed_code: s.bed_code,
                        hostel_name: s.hostel_name,
                        status: stStatus,
                        remarks: s.marked_remarks || "",
                        is_already_marked: !!s.marked_status,
                        is_on_leave: !!s.is_on_leave
                    };
                });
                if (this.attendanceMarkingStudents.length === 0) {
                    this.showToast("No active resident students found for the selected scope.", "info");
                } else {
                    this.showToast(`Loaded ${this.attendanceMarkingStudents.length} resident students for roll call.`, "success");
                }
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
                const activeToMark = this.attendanceMarkingStudents.filter(s => s.status && s.status !== "Not Marked");
                if (activeToMark.length === 0) {
                    this.showToast("All students are set to 'Not Marked'. Please mark at least one student before saving.", "warning");
                    return;
                }
                const records = activeToMark.map(s => ({
                    student_id: s.student_id,
                    status: s.status === "On Leave" ? "On_Leave" : s.status,
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
            const phoneDigits = (form.phone || '').replace(/\D/g, '');
            if (phoneDigits.length !== 10) {
                this.showToast("Contact phone number must be exactly 10 digits (0-9).", "error");
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
        },

        async loadPaymentsList() {
            try {
                const params = {};
                if (this.paymentMethodFilter && this.paymentMethodFilter !== 'all') {
                    params.payment_method = this.paymentMethodFilter;
                }
                if (this.paymentSearch && this.paymentSearch.trim()) {
                    params.payment_reference = this.paymentSearch.trim();
                }
                const res = await window.API.getPayments(params);
                this.paymentsList = res.records || [];
                this.paymentsTotal = res.total || 0;
            } catch (err) {
                console.error("Failed to load payments:", err);
            }
        },

        async loadRefundsList() {
            try {
                const res = await window.API.getRefunds();
                this.refundsList = res.records || [];
                this.refundsTotal = res.total || 0;
            } catch (err) {
                console.error("Failed to load refunds:", err);
            }
        },

        openRecordPaymentModal(inv) {
            const balance = inv ? inv.outstanding_balance : 0;
            this.newPayment = {
                invoice_id: inv ? inv.id : null,
                amount: balance > 0 ? balance : "",
                payment_method: "UPI",
                transaction_id: "",
                notes: `Payment for ${inv ? inv.invoice_number : ''}`
            };
            this.recordPaymentModalOpen = true;
        },

        async handleRecordPayment() {
            try {
                const payload = {
                    invoice_id: parseInt(this.newPayment.invoice_id),
                    amount: parseFloat(this.newPayment.amount),
                    payment_method: this.newPayment.payment_method,
                    transaction_id: this.newPayment.transaction_id,
                    notes: this.newPayment.notes
                };
                const res = await window.API.recordPayment(payload);
                this.showToast(`Payment ${res.payment_reference} of ₹${res.amount} recorded successfully!`, "success");
                this.recordPaymentModalOpen = false;
                await this.loadInvoicesList();
                await this.loadPaymentsList();
            } catch (err) {
                this.showToast(`Payment error: ${err.message}`, "error");
            }
        },

        openReversePaymentModal(pay) {
            this.reversePaymentForm = {
                payment_id: pay.id,
                reason: ""
            };
            this.reversePaymentModalOpen = true;
        },

        async handleReversePayment() {
            try {
                const res = await window.API.reversePayment(
                    this.reversePaymentForm.payment_id,
                    this.reversePaymentForm.reason
                );
                this.showToast(res.message, "success");
                this.reversePaymentModalOpen = false;
                await this.loadPaymentsList();
                await this.loadInvoicesList();
            } catch (err) {
                this.showToast(`Reversal error: ${err.message}`, "error");
            }
        },

        async viewPaymentReceipt(id) {
            try {
                this.activePaymentReceipt = await window.API.getPayment(id);
                this.paymentReceiptModalOpen = true;
            } catch (err) {
                this.showToast(`Failed to load payment receipt: ${err.message}`, "error");
            }
        },

        openRequestRefundModal(pay) {
            this.newRefund = {
                payment_id: pay.id,
                amount: pay.amount,
                reason: "",
                refund_method: "Bank_Transfer"
            };
            this.requestRefundModalOpen = true;
        },

        async handleRequestRefund() {
            try {
                const payload = {
                    payment_id: parseInt(this.newRefund.payment_id),
                    amount: parseFloat(this.newRefund.amount),
                    reason: this.newRefund.reason,
                    refund_method: this.newRefund.refund_method
                };
                const res = await window.API.requestRefund(payload);
                this.showToast(`Refund request #${res.refund_reference} submitted successfully!`, "success");
                this.requestRefundModalOpen = false;
                await this.loadRefundsList();
            } catch (err) {
                this.showToast(`Refund error: ${err.message}`, "error");
            }
        },

        async handleReviewRefund(id, action) {
            try {
                let reason = "";
                if (action === "Reject") {
                    reason = prompt("Please enter mandatory rejection reason:");
                    if (!reason || !reason.strip()) return;
                }
                const res = await window.API.reviewRefund(id, action, reason);
                this.showToast(`Refund #${id} ${action.toLowerCase()}ed successfully.`, "success");
                await this.loadRefundsList();
                await this.loadPaymentsList();
                await this.loadInvoicesList();
            } catch (err) {
                this.showToast(`Action error: ${err.message}`, "error");
            }
        },

        // ==================== FINANCIAL DASHBOARD & REPORTS ====================
        async loadFinancialDashboard(hostelId = null) {
            try {
                this.financialDashboard = await window.API.getFinancialDashboard(hostelId);
            } catch (err) {
                console.error("Failed to load financial dashboard:", err);
            }
        },

        async loadFinancialReport(type = null) {
            if (type) this.financialReportType = type;
            this.financialReportLoading = true;
            try {
                const params = {};
                if (this.financialReportFilters.start_date) params.start_date = this.financialReportFilters.start_date;
                if (this.financialReportFilters.end_date) params.end_date = this.financialReportFilters.end_date;
                if (this.financialReportFilters.payment_method && this.financialReportFilters.payment_method !== 'all') {
                    params.payment_method = this.financialReportFilters.payment_method;
                }
                if (this.financialReportFilters.hostel_id && this.financialReportFilters.hostel_id !== 'all') {
                    params.hostel_id = parseInt(this.financialReportFilters.hostel_id);
                }
                if (this.financialReportFilters.status && this.financialReportFilters.status !== 'all') {
                    params.status = this.financialReportFilters.status;
                }
                this.financialReportData = await window.API.getFinancialReports(this.financialReportType, params);
            } catch (err) {
                this.showToast(`Report error: ${err.message}`, "error");
            } finally {
                this.financialReportLoading = false;
            }
        },

        async handleExportFinancialCsv() {
            try {
                const params = {};
                if (this.financialReportFilters.start_date) params.start_date = this.financialReportFilters.start_date;
                if (this.financialReportFilters.end_date) params.end_date = this.financialReportFilters.end_date;
                if (this.financialReportFilters.payment_method && this.financialReportFilters.payment_method !== 'all') {
                    params.payment_method = this.financialReportFilters.payment_method;
                }
                if (this.financialReportFilters.hostel_id && this.financialReportFilters.hostel_id !== 'all') {
                    params.hostel_id = parseInt(this.financialReportFilters.hostel_id);
                }
                if (this.financialReportFilters.status && this.financialReportFilters.status !== 'all') {
                    params.status = this.financialReportFilters.status;
                }
                await window.API.exportFinancialCsv(this.financialReportType, params);
                this.showToast("Financial CSV report downloaded successfully!", "success");
            } catch (err) {
                this.showToast(`CSV export failed: ${err.message}`, "error");
            }
        },

        // ==================== MESS & DINING MANAGEMENT ====================
        async loadMessDashboard(hostelId = null) {
            if (this.activeRoleView === 'student' || this.activeRoleView === 'parent_guardian') {
                return;
            }
            this.messLoading = true;
            try {
                this.messDashboardData = await window.API.getMessDashboard(hostelId);
            } catch (err) {
                this.showToast(`Mess dashboard error: ${err.message}`, "error");
            } finally {
                this.messLoading = false;
            }
        },

        async loadMessMenus() {
            this.messLoading = true;
            try {
                const params = {};
                if (this.messFilterHostelId) params.hostel_id = this.messFilterHostelId;
                if (this.messFilterDate) params.start_date = this.messFilterDate;
                this.messMenusList = await window.API.getMessMenus(params);
            } catch (err) {
                this.showToast(`Failed to load menus: ${err.message}`, "error");
            } finally {
                this.messLoading = false;
            }
        },

        async handleCreateMessMenu() {
            try {
                const payload = {
                    hostel_id: parseInt(this.newMessMenu.hostel_id),
                    meal_date: this.newMessMenu.meal_date,
                    meal_type: this.newMessMenu.meal_type,
                    title: this.newMessMenu.title,
                    description: this.newMessMenu.description,
                    items: this.newMessMenu.items ? this.newMessMenu.items.split(",").map(i => i.trim()).filter(Boolean) : [],
                    start_time: this.newMessMenu.start_time,
                    end_time: this.newMessMenu.end_time,
                    is_published: this.newMessMenu.is_published,
                    audit_reason: this.newMessMenu.audit_reason || "Scheduled daily menu creation"
                };
                await window.API.createMessMenu(payload);
                this.showToast("Mess menu created successfully!", "success");
                this.messMenuModalOpen = false;
                await this.loadMessMenus();
                await this.loadMessDashboard();
            } catch (err) {
                this.showToast(`Menu creation failed: ${err.message}`, "error");
            }
        },

        async handlePublishMessMenu(menuId) {
            try {
                await window.API.updateMessMenu(menuId, { is_published: true, audit_reason: "Manual publish action" });
                this.showToast("Menu published successfully!", "success");
                await this.loadMessMenus();
            } catch (err) {
                this.showToast(`Publish failed: ${err.message}`, "error");
            }
        },

        async handleCancelMessMenu(menuId) {
            const reason = prompt("Enter audit cancellation reason:", "Administrative adjustment");
            if (!reason) return;
            try {
                await window.API.updateMessMenu(menuId, { status: "Cancelled", audit_reason: reason });
                this.showToast("Menu cancelled.", "info");
                await this.loadMessMenus();
            } catch (err) {
                this.showToast(`Cancel failed: ${err.message}`, "error");
            }
        },

        async loadMessSubscriptions() {
            if (this.activeRoleView === 'student' || this.activeRoleView === 'parent_guardian') {
                return;
            }
            this.messLoading = true;
            try {
                const params = {};
                this.messSubscriptionsList = await window.API.getMessSubscriptions(params);
            } catch (err) {
                this.showToast(`Failed to load subscriptions: ${err.message}`, "error");
            } finally {
                this.messLoading = false;
            }
        },

        async handleCreateMessSubscription() {
            try {
                const payload = {
                    student_id: parseInt(this.newMessSubscription.student_id),
                    plan_type: this.newMessSubscription.plan_type,
                    start_date: this.newMessSubscription.start_date,
                    end_date: this.newMessSubscription.end_date,
                    dietary_preference: this.newMessSubscription.dietary_preference,
                    monthly_rate: parseFloat(this.newMessSubscription.monthly_rate),
                    auto_generate_invoice: !!this.newMessSubscription.auto_generate_invoice
                };
                await window.API.createMessSubscription(payload);
                this.showToast("Mess subscription created successfully!", "success");
                this.messSubscriptionModalOpen = false;
                await this.loadMessSubscriptions();
                await this.loadMessDashboard();
            } catch (err) {
                this.showToast(`Subscription creation failed: ${err.message}`, "error");
            }
        },

        async handleUpdateMessSubscriptionStatus(id, action) {
            const reason = prompt(`Enter audit reason to ${action} subscription:`, `Routine ${action} request`);
            if (!reason) return;
            try {
                await window.API.updateMessSubscriptionStatus(id, action, reason);
                this.showToast(`Subscription status updated: ${action}`, "success");
                await this.loadMessSubscriptions();
                await this.loadMessDashboard();
            } catch (err) {
                this.showToast(`Action failed: ${err.message}`, "error");
            }
        },

        async loadMealAttendance() {
            this.messLoading = true;
            try {
                const params = {
                    meal_date: this.messFilterDate,
                    meal_type: this.messFilterMealType
                };
                if (this.messFilterHostelId) params.hostel_id = this.messFilterHostelId;
                this.mealAttendanceList = await window.API.getMealAttendance(params);
            } catch (err) {
                this.showToast(`Failed to load attendance: ${err.message}`, "error");
            } finally {
                this.messLoading = false;
            }
        },

        async handleRecordMealAttendance() {
            try {
                const payload = {
                    student_id: parseInt(this.newMealAttendance.student_id),
                    hostel_id: parseInt(this.newMealAttendance.hostel_id),
                    meal_date: this.newMealAttendance.meal_date,
                    meal_type: this.newMealAttendance.meal_type,
                    verification_method: this.newMealAttendance.verification_method,
                    remarks: this.newMealAttendance.remarks
                };
                await window.API.recordMealAttendance(payload);
                this.showToast("Meal attendance recorded successfully!", "success");
                this.mealAttendanceModalOpen = false;
                await this.loadMealAttendance();
                await this.loadMessDashboard();
            } catch (err) {
                this.showToast(`Attendance recording failed: ${err.message}`, "error");
            }
        },

        async handleVerifyQRMealAttendance() {
            try {
                const payload = {
                    qr_token: this.qrMealAttendance.qr_token,
                    hostel_id: parseInt(this.qrMealAttendance.hostel_id),
                    meal_type: this.qrMealAttendance.meal_type,
                    meal_date: this.qrMealAttendance.meal_date
                };
                const res = await window.API.verifyQRMealAttendance(payload);
                this.showToast(`Meal verified: ${res.student_name} (${res.student_uid})!`, "success");
                this.qrAttendanceModalOpen = false;
                this.qrMealAttendance.qr_token = "";
                await this.loadMealAttendance();
                await this.loadMessDashboard();
            } catch (err) {
                this.showToast(`QR verification failed: ${err.message}`, "error");
            }
        },

        async handleCorrectMealAttendance(id, newStatus) {
            const reason = prompt("Enter audit correction reason:", "Accidental scan correction");
            if (!reason) return;
            try {
                await window.API.correctMealAttendance(id, { status: newStatus, reason: reason });
                this.showToast("Attendance record corrected.", "info");
                await this.loadMealAttendance();
            } catch (err) {
                this.showToast(`Correction failed: ${err.message}`, "error");
            }
        },

        // ==================== INVENTORY & STOCK MANAGEMENT ====================
        async loadInventoryDashboard() {
            this.inventoryLoading = true;
            try {
                this.inventoryDashboardData = await window.API.getInventoryDashboard();
            } catch (err) {
                this.showToast(`Inventory dashboard error: ${err.message}`, "error");
            } finally {
                this.inventoryLoading = false;
            }
        },

        async loadInventoryCategories() {
            try {
                this.inventoryCategoriesList = await window.API.getInventoryCategories();
            } catch (err) {
                this.showToast(`Failed to load categories: ${err.message}`, "error");
            }
        },

        async loadSuppliers() {
            try {
                this.suppliersList = await window.API.getSuppliers();
            } catch (err) {
                this.showToast(`Failed to load suppliers: ${err.message}`, "error");
            }
        },

        async handleCreateSupplier() {
            try {
                const payload = {
                    name: this.newSupplier.name,
                    code: this.newSupplier.code || null,
                    contact_person: this.newSupplier.contact_person || null,
                    phone: this.newSupplier.phone || null,
                    email: this.newSupplier.email || null,
                    address: this.newSupplier.address || null,
                    tax_id: this.newSupplier.tax_id || null,
                    category: this.newSupplier.category || null,
                    is_active: !!this.newSupplier.is_active
                };
                await window.API.createSupplier(payload);
                this.showToast("Supplier registered successfully!", "success");
                this.supplierModalOpen = false;
                await this.loadSuppliers();
                await this.loadInventoryDashboard();
            } catch (err) {
                this.showToast(`Supplier creation failed: ${err.message}`, "error");
            }
        },

        async loadInventoryItems() {
            this.inventoryLoading = true;
            try {
                const params = {};
                if (this.inventoryFilterCategory) params.category_id = this.inventoryFilterCategory;
                if (this.inventoryFilterStatus) params.status = this.inventoryFilterStatus;
                if (this.inventorySearchTerm) params.search = this.inventorySearchTerm;
                this.inventoryItemsList = await window.API.getInventoryItems(params);
            } catch (err) {
                this.showToast(`Failed to load items: ${err.message}`, "error");
            } finally {
                this.inventoryLoading = false;
            }
        },

        async handleCreateInventoryItem() {
            try {
                const payload = {
                    item_code: this.newInventoryItem.item_code,
                    name: this.newInventoryItem.name,
                    category_id: parseInt(this.newInventoryItem.category_id),
                    unit: this.newInventoryItem.unit,
                    quantity_in_stock: parseFloat(this.newInventoryItem.quantity_in_stock || 0),
                    min_reorder_level: parseFloat(this.newInventoryItem.min_reorder_level || 10),
                    max_threshold: this.newInventoryItem.max_threshold ? parseFloat(this.newInventoryItem.max_threshold) : null,
                    unit_price: parseFloat(this.newInventoryItem.unit_price || 0),
                    supplier_id: this.newInventoryItem.supplier_id ? parseInt(this.newInventoryItem.supplier_id) : null,
                    location: this.newInventoryItem.location || null,
                    expiry_date: this.newInventoryItem.expiry_date || null,
                    status: this.newInventoryItem.status || "Active"
                };
                await window.API.createInventoryItem(payload);
                this.showToast("Inventory item created successfully!", "success");
                this.inventoryItemModalOpen = false;
                await this.loadInventoryItems();
                await this.loadInventoryDashboard();
            } catch (err) {
                this.showToast(`Item creation failed: ${err.message}`, "error");
            }
        },

        async loadInventoryTransactions() {
            this.inventoryLoading = true;
            try {
                this.inventoryTransactionsList = await window.API.getInventoryTransactions();
            } catch (err) {
                this.showToast(`Failed to load transactions: ${err.message}`, "error");
            } finally {
                this.inventoryLoading = false;
            }
        },

        async handleRecordStockInward() {
            try {
                const payload = {
                    item_id: parseInt(this.newStockInward.item_id),
                    quantity: parseFloat(this.newStockInward.quantity),
                    unit_price: this.newStockInward.unit_price ? parseFloat(this.newStockInward.unit_price) : null,
                    supplier_id: this.newStockInward.supplier_id ? parseInt(this.newStockInward.supplier_id) : null,
                    invoice_ref: this.newStockInward.invoice_ref || null,
                    location: this.newStockInward.location || null,
                    remarks: this.newStockInward.remarks || "Procurement inward"
                };
                await window.API.recordStockInward(payload);
                this.showToast("Stock inward recorded and inventory updated!", "success");
                this.stockInwardModalOpen = false;
                await this.loadInventoryItems();
                await this.loadInventoryDashboard();
                if (this.inventorySubTab === 'inward') await this.loadInventoryTransactions();
            } catch (err) {
                this.showToast(`Stock inward failed: ${err.message}`, "error");
            }
        },

        async handleRecordStockOutward() {
            try {
                const payload = {
                    item_id: parseInt(this.newStockOutward.item_id),
                    quantity: parseFloat(this.newStockOutward.quantity),
                    department: this.newStockOutward.department,
                    issued_to: this.newStockOutward.issued_to || null,
                    remarks: this.newStockOutward.remarks || "Department consumption"
                };
                await window.API.recordStockOutward(payload);
                this.showToast("Stock outward recorded successfully!", "success");
                this.stockOutwardModalOpen = false;
                await this.loadInventoryItems();
                await this.loadInventoryDashboard();
                if (this.inventorySubTab === 'outward') await this.loadInventoryTransactions();
            } catch (err) {
                this.showToast(`Stock outward failed: ${err.message}`, "error");
            }
        },

        async handleRecordStockAdjustment() {
            try {
                const payload = {
                    item_id: parseInt(this.newStockAdjustment.item_id),
                    adjustment_type: this.newStockAdjustment.adjustment_type,
                    quantity_change: parseFloat(this.newStockAdjustment.quantity_change),
                    reason: this.newStockAdjustment.reason,
                    from_location: this.newStockAdjustment.from_location || null,
                    to_location: this.newStockAdjustment.to_location || null
                };
                await window.API.recordStockAdjustment(payload);
                this.showToast("Stock adjustment logged and inventory balance updated!", "success");
                this.stockAdjustmentModalOpen = false;
                await this.loadInventoryItems();
                await this.loadInventoryDashboard();
            } catch (err) {
                this.showToast(`Adjustment failed: ${err.message}`, "error");
            }
        },

        // ==========================================
        // PROMPT 14 & 15: NOTIFICATIONS, ANNOUNCEMENTS, ADMIN & BACKUP
        // ==========================================

        // --- NOTIFICATIONS STATE ---
        notificationsList: [],
        notificationUnreadCount: 0,
        notificationPreferencesModalOpen: false,
        notificationPreferences: { in_app_enabled: true, email_enabled: false, browser_enabled: false, disabled_categories: [] },

        async loadNotifications() {
            try {
                const res = await window.API.getNotifications({ page: 1, page_size: 50 });
                this.notificationsList = res.items || [];
                this.notificationUnreadCount = res.unread_count || 0;
            } catch (err) {
                console.error("Failed to load notifications:", err);
            }
        },

        async loadUnreadNotificationCount() {
            try {
                const res = await window.API.getUnreadNotificationCount();
                this.notificationUnreadCount = res.unread_count || 0;
            } catch (err) {
                console.error("Failed to load unread count:", err);
            }
        },

        async markNotificationAsRead(id) {
            try {
                await window.API.markNotificationRead(id);
                const n = this.notificationsList.find(item => item.id === id);
                if (n) n.is_read = true;
                if (this.notificationUnreadCount > 0) this.notificationUnreadCount--;
            } catch (err) {
                this.showToast(`Error: ${err.message}`, "error");
            }
        },

        async markAllNotificationsAsRead() {
            try {
                const res = await window.API.markAllNotificationsRead();
                this.notificationsList.forEach(n => n.is_read = true);
                this.notificationUnreadCount = 0;
                this.showToast(res.message || "All notifications marked as read.", "success");
            } catch (err) {
                this.showToast(`Error: ${err.message}`, "error");
            }
        },

        async openNotificationPreferencesModal() {
            try {
                const prefs = await window.API.getNotificationPreferences();
                this.notificationPreferences = prefs;
                this.notificationPreferencesModalOpen = true;
            } catch (err) {
                this.showToast(`Failed to load preferences: ${err.message}`, "error");
            }
        },

        async saveNotificationPreferences() {
            try {
                await window.API.updateNotificationPreferences(this.notificationPreferences);
                this.showToast("Notification preferences updated successfully!", "success");
                this.notificationPreferencesModalOpen = false;
            } catch (err) {
                this.showToast(`Error: ${err.message}`, "error");
            }
        },

        // --- ANNOUNCEMENTS STATE ---
        announcementsList: [],
        emergencyAnnouncement: null,
        announcementModalOpen: false,
        editingAnnouncementId: null,
        maintenanceFilterCategory: 'all',
        announcementDetailModalOpen: false,
        announcementViewsModalOpen: false,
        selectedAnnouncement: null,
        announcementViewsList: [],
        announcementTab: 'active',
        newAnnouncement: {
            title: '',
            content: '',
            category: 'General Notice',
            priority: 'Normal',
            target_audience: 'All Users',
            target_hostel_id: null,
            expires_at: ''
        },

        async loadAnnouncements() {
            try {
                const list = await window.API.getAnnouncements({ limit: 100 });
                this.announcementsList = list || [];
                // Check for high-priority emergency announcements
                this.emergencyAnnouncement = this.announcementsList.find(a => 
                    (a.priority === 'Critical' || a.priority === 'Emergency') && a.status === 'Published' && !a.is_acknowledged_by_me
                ) || null;
            } catch (err) {
                console.error("Failed to load announcements:", err);
            }
        },

        async openAnnouncementDetail(a) {
            try {
                const detailed = await window.API.getAnnouncement(a.id);
                this.selectedAnnouncement = detailed;
                this.announcementDetailModalOpen = true;
                // Update in local list
                const idx = this.announcementsList.findIndex(item => item.id === a.id);
                if (idx !== -1) this.announcementsList[idx].is_viewed_by_me = true;
            } catch (err) {
                this.showToast(`Failed to load notice: ${err.message}`, "error");
            }
        },

        openCreateAnnouncement() {
            this.editingAnnouncementId = null;
            this.newAnnouncement = {
                title: '',
                content: '',
                category: 'General Notice',
                priority: 'Normal',
                target_audience: 'All Users',
                target_hostel_id: null,
                expires_at: ''
            };
            this.announcementModalOpen = true;
        },

        openEditAnnouncement(a) {
            this.editingAnnouncementId = a.id;
            this.newAnnouncement = {
                title: a.title || '',
                content: a.content || '',
                category: a.category || 'General Notice',
                priority: a.priority || 'Normal',
                target_audience: a.target_audience || 'All Users',
                target_hostel_id: a.target_hostel_id || null,
                expires_at: a.expires_at ? a.expires_at.substring(0, 10) : ''
            };
            this.announcementDetailModalOpen = false;
            this.announcementModalOpen = true;
        },

        async saveAnnouncement() {
            if (!this.newAnnouncement.title || !this.newAnnouncement.content) {
                this.showToast("Title and content are required.", "warning");
                return;
            }
            try {
                const payload = {
                    title: this.newAnnouncement.title,
                    content: this.newAnnouncement.content,
                    category: this.newAnnouncement.category,
                    priority: this.newAnnouncement.priority,
                    target_audience: this.newAnnouncement.target_audience,
                    target_hostel_id: this.newAnnouncement.target_hostel_id ? parseInt(this.newAnnouncement.target_hostel_id) : null,
                    expires_at: this.newAnnouncement.expires_at || null,
                    status: 'Published'
                };
                if (this.editingAnnouncementId) {
                    await window.API.updateAnnouncement(this.editingAnnouncementId, payload);
                    this.showToast("Announcement updated successfully!", "success");
                } else {
                    await window.API.createAnnouncement(payload);
                    this.showToast("Announcement published successfully!", "success");
                }
                this.announcementModalOpen = false;
                this.editingAnnouncementId = null;
                this.newAnnouncement = { title: '', content: '', category: 'General Notice', priority: 'Normal', target_audience: 'All Users', target_hostel_id: null, expires_at: '' };
                await this.loadAnnouncements();
            } catch (err) {
                this.showToast(`Error: ${err.message}`, "error");
            }
        },

        async saveNewAnnouncement() {
            return await this.saveAnnouncement();
        },

        async publishAnnouncementAction(id) {
            try {
                await window.API.publishAnnouncement(id);
                this.showToast("Announcement published!", "success");
                await this.loadAnnouncements();
            } catch (err) {
                this.showToast(`Publish error: ${err.message}`, "error");
            }
        },

        async archiveAnnouncementAction(id) {
            try {
                await window.API.archiveAnnouncement(id);
                this.showToast("Announcement archived.", "info");
                await this.loadAnnouncements();
            } catch (err) {
                this.showToast(`Archive error: ${err.message}`, "error");
            }
        },

        async acknowledgeAnnouncementAction(id) {
            try {
                await window.API.acknowledgeAnnouncement(id);
                this.showToast("Notice acknowledged.", "success");
                if (this.selectedAnnouncement && this.selectedAnnouncement.id === id) {
                    this.selectedAnnouncement.is_acknowledged_by_me = true;
                }
                if (this.emergencyAnnouncement && this.emergencyAnnouncement.id === id) {
                    this.emergencyAnnouncement = null;
                }
                await this.loadAnnouncements();
            } catch (err) {
                this.showToast(`Error: ${err.message}`, "error");
            }
        },

        async viewAnnouncementAudience(id) {
            try {
                const views = await window.API.getAnnouncementViews(id);
                this.announcementViewsList = views || [];
                this.announcementViewsModalOpen = true;
            } catch (err) {
                this.showToast(`Failed to load reader logs: ${err.message}`, "error");
            }
        },

        // --- SYSTEM ADMINISTRATION STATE ---
        adminTab: 'settings',
        adminSettings: [],
        adminSettingsCategories: ['all', 'general', 'localization', 'finance', 'academic', 'admission', 'allocation', 'attendance', 'leave', 'visitor', 'notification', 'security'],
        selectedSettingsCategory: 'all',
        adminSettingsHistory: [],
        adminSettingsHistoryModalOpen: false,
        adminUsersList: [],
        adminUsersTotal: 0,
        adminUsersPage: 1,
        adminUsersSearch: '',
        adminUsersRoleFilter: '',
        selectedAdminUser: null,
        adminUserDetailModalOpen: false,
        adminUserRolesModalOpen: false,
        editingUserRoles: [],
        adminPasswordResetModalOpen: false,
        adminResetPasswordData: { temporary_password: '', reason: '' },
        adminRolesList: [],
        adminPermissionsList: [],
        selectedRoleForPermissions: null,
        editingRolePermissions: [],
        adminRolePermissionsModalOpen: false,
        adminAuditLogsList: [],
        adminAuditLogsTotal: 0,
        adminAuditLogsPage: 1,
        adminAuditLogsSearch: '',
        adminAuditLogsActionFilter: '',
        adminAuditLogsModuleFilter: '',
        adminAuditLogsStartDate: '',
        adminAuditLogsEndDate: '',
        selectedAuditLog: null,
        adminAuditLogDetailModalOpen: false,
        adminBackupsList: [],
        backupNote: '',

        async loadAdminSettings() {
            try {
                const cat = this.selectedSettingsCategory === 'all' ? null : this.selectedSettingsCategory;
                this.adminSettings = await window.API.getAdminSettings(cat);
            } catch (err) {
                this.showToast(`Settings load error: ${err.message}`, "error");
            }
        },

        async saveAdminSettings() {
            try {
                const map = {};
                this.adminSettings.forEach(s => map[s.setting_key] = s.setting_value);
                await window.API.updateAdminSettings({ settings: map, reason: "Administrative console update" });
                this.showToast("System settings saved and applied successfully!", "success");
                await this.loadAdminSettings();
            } catch (err) {
                this.showToast(`Save settings error: ${err.message}`, "error");
            }
        },

        async openSettingsHistory() {
            try {
                this.adminSettingsHistory = await window.API.getAdminSettingsHistory(50);
                this.adminSettingsHistoryModalOpen = true;
            } catch (err) {
                this.showToast(`Failed to load history: ${err.message}`, "error");
            }
        },

        async loadAdminUsers(page = 1) {
            try {
                this.adminUsersPage = page;
                const params = {
                    page: this.adminUsersPage,
                    page_size: 20
                };
                if (this.adminUsersSearch) params.search = this.adminUsersSearch;
                if (this.adminUsersRoleFilter) params.role = this.adminUsersRoleFilter;
                const res = await window.API.getAdminUsers(params);
                this.adminUsersList = res.items || [];
                this.adminUsersTotal = res.total || 0;
            } catch (err) {
                this.showToast(`Users load error: ${err.message}`, "error");
            }
        },

        async openAdminUserDetail(u) {
            try {
                this.selectedAdminUser = await window.API.getAdminUserDetail(u.id);
                this.adminUserDetailModalOpen = true;
            } catch (err) {
                this.showToast(`Failed to load user: ${err.message}`, "error");
            }
        },

        async toggleAdminUserStatus(u) {
            const nextStatus = !u.is_active;
            const actionText = nextStatus ? "activate" : "deactivate";
            if (!confirm(`Are you sure you want to ${actionText} user account '${u.username}'?`)) return;
            try {
                await window.API.updateAdminUserStatus(u.id, { is_active: nextStatus, reason: `Admin ${actionText}` });
                this.showToast(`User '${u.username}' ${actionText}d successfully.`, "success");
                await this.loadAdminUsers(this.adminUsersPage);
            } catch (err) {
                this.showToast(`Status update failed: ${err.message}`, "error");
            }
        },

        openAdminUserRoles(u) {
            this.selectedAdminUser = u;
            this.editingUserRoles = [...(u.roles || [])];
            this.adminUserRolesModalOpen = true;
        },

        async saveAdminUserRoles() {
            if (!this.selectedAdminUser) return;
            if (this.editingUserRoles.length === 0) {
                this.showToast("User must have at least one assigned role.", "warning");
                return;
            }
            try {
                await window.API.updateAdminUserRoles(this.selectedAdminUser.id, {
                    roles: this.editingUserRoles,
                    reason: "Admin role adjustment"
                });
                this.showToast("Roles updated successfully!", "success");
                this.adminUserRolesModalOpen = false;
                await this.loadAdminUsers(this.adminUsersPage);
            } catch (err) {
                this.showToast(`Role assignment error: ${err.message}`, "error");
            }
        },

        openAdminPasswordReset(u) {
            this.selectedAdminUser = u;
            this.adminResetPasswordData = { temporary_password: '', reason: 'Administrative password reset' };
            this.adminPasswordResetModalOpen = true;
        },

        async executeAdminPasswordReset() {
            if (!this.selectedAdminUser) return;
            try {
                const res = await window.API.adminResetPassword(this.selectedAdminUser.id, this.adminResetPasswordData);
                this.showToast(`Password reset! New password: ${res.temporary_password}`, "success");
                this.adminPasswordResetModalOpen = false;
            } catch (err) {
                this.showToast(`Password reset error: ${err.message}`, "error");
            }
        },

        async loadAdminRolesAndPermissions() {
            try {
                this.adminRolesList = await window.API.getAdminRoles();
                this.adminPermissionsList = await window.API.getAdminPermissions();
            } catch (err) {
                console.error("Failed to load roles and permissions:", err);
            }
        },

        openRolePermissionsModal(r) {
            this.selectedRoleForPermissions = r;
            this.editingRolePermissions = [...(r.permissions || [])];
            this.adminRolePermissionsModalOpen = true;
        },

        async saveRolePermissions() {
            if (!this.selectedRoleForPermissions) return;
            try {
                await window.API.updateRolePermissions(this.selectedRoleForPermissions.id, {
                    permission_names: this.editingRolePermissions,
                    reason: "Permissions reconfigured via Admin Portal"
                });
                this.showToast("Role permissions updated successfully!", "success");
                this.adminRolePermissionsModalOpen = false;
                await this.loadAdminRolesAndPermissions();
            } catch (err) {
                this.showToast(`Error: ${err.message}`, "error");
            }
        },

        async loadAdminAuditLogs(page = 1) {
            try {
                this.adminAuditLogsPage = page;
                const params = {
                    page: this.adminAuditLogsPage,
                    page_size: 25
                };
                if (this.adminAuditLogsSearch) params.search = this.adminAuditLogsSearch;
                if (this.adminAuditLogsActionFilter) params.action = this.adminAuditLogsActionFilter;
                if (this.adminAuditLogsModuleFilter) params.module = this.adminAuditLogsModuleFilter;
                if (this.adminAuditLogsStartDate) params.start_date = this.adminAuditLogsStartDate;
                if (this.adminAuditLogsEndDate) params.end_date = this.adminAuditLogsEndDate;
                const res = await window.API.getAdminAuditLogs(params);
                this.adminAuditLogsList = res.items || [];
                this.adminAuditLogsTotal = res.total || 0;
            } catch (err) {
                this.showToast(`Audit log load error: ${err.message}`, "error");
            }
        },

        openAuditLogDetail(l) {
            this.selectedAuditLog = l;
            this.adminAuditLogDetailModalOpen = true;
        },

        exportAuditLogsCsv() {
            const params = {};
            if (this.adminAuditLogsSearch) params.search = this.adminAuditLogsSearch;
            if (this.adminAuditLogsActionFilter) params.action = this.adminAuditLogsActionFilter;
            if (this.adminAuditLogsModuleFilter) params.module = this.adminAuditLogsModuleFilter;
            if (this.adminAuditLogsStartDate) params.start_date = this.adminAuditLogsStartDate;
            if (this.adminAuditLogsEndDate) params.end_date = this.adminAuditLogsEndDate;
            const url = window.API.getAdminAuditLogsExportUrl(params);
            window.open(url, "_blank");
            this.showToast("Audit logs RFC 4180 CSV export initiated.", "info");
        },

        async loadAdminBackups() {
            try {
                this.adminBackupsList = await window.API.listBackups();
            } catch (err) {
                console.error("Failed to load backups:", err);
            }
        },

        async createBackupAction() {
            try {
                const res = await window.API.createBackup(this.backupNote);
                this.showToast(`Database backup created: ${res.filename} (${(res.size_bytes / 1024).toFixed(1)} KB)`, "success");
                this.backupNote = '';
                await this.loadAdminBackups();
            } catch (err) {
                this.showToast(`Backup error: ${err.message}`, "error");
            }
        },

        async restoreBackupAction(filename) {
            if (!confirm(`CAUTION: Are you sure you want to restore database from snapshot '${filename}'? Current data will be replaced (a pre-restore snapshot will be saved automatically).`)) {
                return;
            }
            try {
                const res = await window.API.restoreBackup(filename);
                this.showToast(res.message || "Database restored successfully!", "success");
                await this.loadAdminBackups();
            } catch (err) {
                this.showToast(`Restore error: ${err.message}`, "error");
            }
        }
    }));
});

