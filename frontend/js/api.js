/**
 * Lightweight API Client for Hostel Management System Web App
 * Course: BBAT104 Fundamentals of TQM
 * Quality Goal: Q05 - Reduce Response Time
 */

const API = {
    baseUrl: window.location.origin,
    accessToken: localStorage.getItem("hms_access_token") || null,

    setToken(token) {
        this.accessToken = token;
        if (token) {
            localStorage.setItem("hms_access_token", token);
        } else {
            localStorage.removeItem("hms_access_token");
        }
    },

    getToken() {
        return this.accessToken || localStorage.getItem("hms_access_token");
    },

    getHeaders(extraHeaders = {}) {
        const headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            ...extraHeaders
        };
        const token = this.getToken();
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }
        return headers;
    },

    /**
     * Fetch system health and latency telemetry from backend.
     */
    async checkHealth() {
        const t0 = performance.now();
        try {
            const response = await fetch(`${this.baseUrl}/api/health`, {
                headers: { "Accept": "application/json" }
            });
            const clientLatency = performance.now() - t0;
            const serverLatency = response.headers.get("X-Response-Time-Ms");

            if (!response.ok) {
                return {
                    status: "error",
                    clientLatencyMs: parseFloat(clientLatency.toFixed(2)),
                    serverLatencyMs: serverLatency ? parseFloat(parseFloat(serverLatency).toFixed(2)) : parseFloat(clientLatency.toFixed(2)),
                    detail: `HTTP ${response.status}`
                };
            }

            const data = await response.json();
            return {
                ...data,
                clientLatencyMs: parseFloat(clientLatency.toFixed(2)),
                serverLatencyMs: serverLatency ? parseFloat(parseFloat(serverLatency).toFixed(2)) : parseFloat(clientLatency.toFixed(2))
            };
        } catch (err) {
            return {
                status: "disconnected",
                clientLatencyMs: parseFloat((performance.now() - t0).toFixed(2)),
                error: err.message
            };
        }
    },

    /**
     * Authenticate user with credentials.
     */
    async login(usernameOrEmail, password) {
        const response = await fetch(`${this.baseUrl}/api/v1/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json", "Accept": "application/json" },
            credentials: "include",
            body: JSON.stringify({
                username_or_email: usernameOrEmail,
                password: password,
                device_info: "Web Browser - Desktop Client"
            })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Authentication failed.");
        }

        this.setToken(data.access_token);
        return data;
    },

    /**
     * Rotate refresh token and update access token.
     */
    async refreshToken() {
        try {
            const response = await fetch(`${this.baseUrl}/api/v1/auth/refresh`, {
                method: "POST",
                headers: this.getHeaders(),
                credentials: "include",
                body: JSON.stringify({})
            });

            if (!response.ok) {
                this.setToken(null);
                return null;
            }

            const data = await response.json();
            this.setToken(data.access_token);
            return data;
        } catch (err) {
            this.setToken(null);
            return null;
        }
    },

    /**
     * Revoke tokens and logout session.
     */
    async logout() {
        try {
            await fetch(`${this.baseUrl}/api/v1/auth/logout`, {
                method: "POST",
                headers: this.getHeaders(),
                credentials: "include",
                body: JSON.stringify({})
            });
        } finally {
            this.setToken(null);
        }
    },

    /**
     * Fetch current user identity.
     */
    async getMe() {
        const response = await fetch(`${this.baseUrl}/api/v1/auth/me`, {
            headers: this.getHeaders(),
            credentials: "include"
        });

        if (response.status === 401) {
            // Attempt token refresh once
            const refreshed = await this.refreshToken();
            if (refreshed) {
                return this.getMe();
            }
            this.setToken(null);
            return null;
        }

        if (!response.ok) {
            return null;
        }

        return await response.json();
    },

    /**
     * List all 12 system roles.
     */
    async getRoles() {
        const response = await fetch(`${this.baseUrl}/api/v1/roles`, {
            headers: this.getHeaders()
        });
        if (!response.ok) return [];
        return await response.json();
    },

    _pendingRequests: new Map(),

    /**
     * Deduplicate identical in-flight GET requests to prevent redundant network traffic.
     */
    async deduplicatedFetch(url, options = {}) {
        const method = (options.method || "GET").toUpperCase();
        if (method !== "GET") {
            return fetch(url, options);
        }
        if (this._pendingRequests.has(url)) {
            return this._pendingRequests.get(url).then(res => res.clone());
        }
        const promise = fetch(url, options).finally(() => {
            this._pendingRequests.delete(url);
        });
        this._pendingRequests.set(url, promise);
        return promise.then(res => res.clone());
    },

    /**
     * Fetch live or cached dashboard aggregation metrics with Q05 sub-10ms acceleration.
     */
    async getDashboardStats(hostelId = null, bypassCache = false) {
        const params = new URLSearchParams();
        if (hostelId) params.append("hostel_id", hostelId);
        if (bypassCache) params.append("bypass_cache", "true");
        const qs = params.toString();
        const url = `${this.baseUrl}/api/v1/metrics/dashboard${qs ? '?' + qs : ''}`;

        try {
            const response = await this.deduplicatedFetch(url, {
                headers: this.getHeaders()
            });
            if (response.ok) return await response.json();
        } catch (e) {
            // Fallback to legacy endpoint if metrics router unavailable
        }

        const legacyResp = await fetch(`${this.baseUrl}/api/v1/dashboard/stats`, {
            headers: this.getHeaders()
        });
        if (!legacyResp.ok) return null;
        return await legacyResp.json();
    },

    /**
     * Retrieve cache operational statistics.
     */
    async getCacheStats() {
        const response = await fetch(`${this.baseUrl}/api/v1/metrics/cache/stats`, {
            headers: this.getHeaders()
        });
        if (!response.ok) return null;
        return await response.json();
    },

    /**
     * Flush in-memory cache.
     */
    async clearCache() {
        const response = await fetch(`${this.baseUrl}/api/v1/metrics/cache/clear`, {
            method: "POST",
            headers: this.getHeaders()
        });
        return await response.json();
    },

    /**
     * Fetch user list (Super Admin & Hostel Admin only).
     */
    async getUsers() {
        const response = await fetch(`${this.baseUrl}/api/v1/users`, {
            headers: this.getHeaders()
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Failed to load user directory.");
        }
        return await response.json();
    },

    /**
     * Fetch student profile with strict isolation.
     */
    async getStudentProfile(studentId) {
        const response = await fetch(`${this.baseUrl}/api/v1/students/${studentId}/profile`, {
            headers: this.getHeaders()
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || `Access Denied: HTTP ${response.status}`);
        }
        return data;
    },

    /**
     * Change current user's password.
     */
    async changePassword(currentPassword, newPassword) {
        const response = await fetch(`${this.baseUrl}/api/v1/auth/change-password`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword
            })
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Failed to change password.");
        }
        return data;
    },

    // ==================== HOSTEL & ALLOCATION APIS ====================

    async getHostels(params = {}) {
        const qs = new URLSearchParams(params).toString();
        const response = await fetch(`${this.baseUrl}/api/v1/hostels${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load hostels.");
        return await response.json();
    },

    async getAllocations(params = {}) {
        const qs = new URLSearchParams(params).toString();
        const response = await fetch(`${this.baseUrl}/api/v1/allocations${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load allocations.");
        return await response.json();
    },

    async getAllocation(id) {
        const response = await fetch(`${this.baseUrl}/api/v1/allocations/${id}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to fetch allocation.");
        return await response.json();
    },

    async createAllocation(data) {
        const response = await fetch(`${this.baseUrl}/api/v1/allocations`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(data)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Allocation failed.");
        return res;
    },

    async getAvailableBeds(params = {}) {
        const qs = new URLSearchParams(params).toString();
        const response = await fetch(`${this.baseUrl}/api/v1/allocations/available-beds${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to fetch available beds.");
        return await response.json();
    },

    async getAllocationSuggestions(studentId, preferredHostelId = null, preferredRoomType = null, floorPreference = null) {
        const params = new URLSearchParams({ student_id: studentId });
        if (preferredHostelId) params.append("preferred_hostel_id", preferredHostelId);
        if (preferredRoomType) params.append("preferred_room_type", preferredRoomType);
        if (floorPreference !== null && floorPreference !== undefined) params.append("floor_preference", floorPreference);

        const response = await fetch(`${this.baseUrl}/api/v1/allocations/suggestions?${params.toString()}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to fetch allocation suggestions.");
        return await response.json();
    },

    async checkinAllocation(allocationId, checkinDate = null) {
        const response = await fetch(`${this.baseUrl}/api/v1/allocations/${allocationId}/checkin`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ checkin_date: checkinDate })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Check-in failed.");
        return res;
    },

    async checkoutAllocation(allocationId, checkoutDate = null, reason = "Academic Term Completion") {
        const response = await fetch(`${this.baseUrl}/api/v1/allocations/${allocationId}/checkout`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ checkout_date: checkoutDate, reason })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Check-out failed.");
        return res;
    },

    async requestTransfer(allocationId, toBedId, reason) {
        const response = await fetch(`${this.baseUrl}/api/v1/allocations/${allocationId}/transfer`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ to_bed_id: toBedId, reason })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Transfer request failed.");
        return res;
    },

    async getTransfers(statusFilter = null, studentId = null) {
        const params = new URLSearchParams();
        if (statusFilter) params.append("status_filter", statusFilter);
        if (studentId) params.append("student_id", studentId);
        const qs = params.toString();

        const response = await fetch(`${this.baseUrl}/api/v1/transfers${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load transfer requests.");
        return await response.json();
    },

    async reviewTransfer(transferId, action, remarks = "") {
        const response = await fetch(`${this.baseUrl}/api/v1/transfers/${transferId}/review`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ action, remarks })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Review action failed.");
        return res;
    },

    async getStudentAllocationHistory(studentId) {
        const response = await fetch(`${this.baseUrl}/api/v1/students/${studentId}/allocation-history`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load student history.");
        return await response.json();
    },

    async getRoomOccupants(roomId) {
        const response = await fetch(`${this.baseUrl}/api/v1/rooms/${roomId}/occupants`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load room occupants.");
        return await response.json();
    },

    /**
     * Q05 Fast Search across students, hostels, rooms, allocations, complaints, maintenance, payments.
     */
    async search(query, category = "all", limit = 20, offset = 0) {
        const params = new URLSearchParams({
            q: query,
            category: category,
            limit: limit.toString(),
            offset: offset.toString()
        });
        const response = await fetch(`${this.baseUrl}/api/v1/search?${params.toString()}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Search request failed.");
        }
        return await response.json();
    },

    async rebuildSearchIndex() {
        const response = await fetch(`${this.baseUrl}/api/v1/search/rebuild-index`, {
            method: "POST",
            headers: this.getHeaders()
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Index rebuild failed.");
        }
        return await response.json();
    },

    // ==================== COMPLAINTS ====================

    async submitComplaint(data) {
        const response = await fetch(`${this.baseUrl}/api/v1/complaints`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(data)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to submit complaint.");
        return res;
    },

    async getMyComplaints(statusFilter = null, category = null) {
        const params = new URLSearchParams();
        if (statusFilter) params.append("status_filter", statusFilter);
        if (category) params.append("category", category);
        const qs = params.toString();

        const response = await this.deduplicatedFetch(`${this.baseUrl}/api/v1/complaints/my${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error("Failed to load my complaints.");
        return await response.json();
    },

    async getComplaintDetails(complaintId) {
        const response = await fetch(`${this.baseUrl}/api/v1/complaints/${complaintId}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error("Failed to load complaint details.");
        return await response.json();
    },

    async addComplaintComment(complaintId, comment) {
        const response = await fetch(`${this.baseUrl}/api/v1/complaints/${complaintId}/comments`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ comment })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to add comment.");
        return res;
    },

    async reopenComplaint(complaintId, reason) {
        const response = await fetch(`${this.baseUrl}/api/v1/complaints/${complaintId}/reopen`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ reason })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to reopen complaint.");
        return res;
    },

    async submitComplaintFeedback(complaintId, rating, comment = "") {
        const response = await fetch(`${this.baseUrl}/api/v1/complaints/${complaintId}/feedback`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ rating, comment })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to submit feedback.");
        return res;
    },

    async getComplaints(hostelId = null, statusFilter = null, category = null, severity = null, search = null, page = 1, pageSize = 20) {
        const params = new URLSearchParams();
        if (hostelId) params.append("hostel_id", hostelId);
        if (statusFilter && statusFilter !== 'all') params.append("status_filter", statusFilter);
        if (category && category !== 'all') params.append("category", category);
        if (severity && severity !== 'all') params.append("severity", severity);
        if (search) params.append("search", search);
        params.append("page", page);
        params.append("page_size", pageSize);

        const qs = params.toString();
        const response = await this.deduplicatedFetch(`${this.baseUrl}/api/v1/complaints${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error("Failed to load complaints list.");
        return await response.json();
    },

    async getComplaintAnalytics(hostelId = null) {
        const qs = hostelId ? `?hostel_id=${hostelId}` : "";
        const response = await fetch(`${this.baseUrl}/api/v1/complaints/analytics${qs}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error("Failed to load complaint analytics.");
        return await response.json();
    },

    async assignComplaint(complaintId, assignedTo, priority = null, deadline = null, internalRemarks = "", affectsOccupancy = false) {
        const response = await fetch(`${this.baseUrl}/api/v1/complaints/${complaintId}/assign`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({
                assigned_to: assignedTo,
                priority,
                deadline,
                internal_remarks: internalRemarks,
                affects_occupancy: affectsOccupancy
            })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to assign complaint.");
        return res;
    },

    async escalateComplaint(complaintId, reason) {
        const response = await fetch(`${this.baseUrl}/api/v1/complaints/${complaintId}/escalate`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ reason })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to escalate complaint.");
        return res;
    },

    async rejectComplaint(complaintId, reason) {
        const response = await fetch(`${this.baseUrl}/api/v1/complaints/${complaintId}/reject`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ reason })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to reject complaint.");
        return res;
    },

    async closeComplaint(complaintId, notes = "") {
        const response = await fetch(`${this.baseUrl}/api/v1/complaints/${complaintId}/close`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ notes })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to close complaint.");
        return res;
    },

    // ==================== MAINTENANCE WORK-ORDERS ====================
    async getMaintenanceTasks(statusFilter = null, priorityFilter = null, assignedTo = null, hostelId = null) {
        const params = new URLSearchParams();
        if (statusFilter && statusFilter !== 'all') params.append('status_filter', statusFilter);
        if (priorityFilter && priorityFilter !== 'all') params.append('priority_filter', priorityFilter);
        if (assignedTo) params.append('assigned_to', assignedTo);
        if (hostelId) params.append('hostel_id', hostelId);

        const qs = params.toString();
        const response = await fetch(`${this.baseUrl}/api/v1/maintenance/tasks${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error("Failed to load maintenance tasks.");
        return await response.json();
    },

    async getMaintenanceTask(taskId) {
        const response = await fetch(`${this.baseUrl}/api/v1/maintenance/tasks/${taskId}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error("Failed to load maintenance task details.");
        return await response.json();
    },

    async createMaintenanceTask(data) {
        const response = await fetch(`${this.baseUrl}/api/v1/maintenance/tasks`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(data)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to create maintenance task.");
        return res;
    },

    async acceptMaintenanceTask(taskId) {
        const response = await fetch(`${this.baseUrl}/api/v1/maintenance/tasks/${taskId}/accept`, {
            method: "POST",
            headers: this.getHeaders()
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to accept task.");
        return res;
    },

    async startMaintenanceTask(taskId) {
        const response = await fetch(`${this.baseUrl}/api/v1/maintenance/tasks/${taskId}/start`, {
            method: "POST",
            headers: this.getHeaders()
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to start task.");
        return res;
    },

    async updateMaintenanceTaskProgress(taskId, notes) {
        const response = await fetch(`${this.baseUrl}/api/v1/maintenance/tasks/${taskId}/progress`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ notes })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to update progress.");
        return res;
    },

    async holdMaintenanceTask(taskId, holdReason, notes = "") {
        const response = await fetch(`${this.baseUrl}/api/v1/maintenance/tasks/${taskId}/hold`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ hold_reason: holdReason, notes })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to place task on hold.");
        return res;
    },

    async completeMaintenanceTask(taskId, resolutionNotes, actualCost = 0.0, completionPhotoUrl = null) {
        const response = await fetch(`${this.baseUrl}/api/v1/maintenance/tasks/${taskId}/complete`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({
                resolution_notes: resolutionNotes,
                actual_cost: parseFloat(actualCost) || 0.0,
                completion_photo_url: completionPhotoUrl
            })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to complete task.");
        return res;
    },

    async verifyMaintenanceTask(taskId, approved = true, verificationNotes = "") {
        const response = await fetch(`${this.baseUrl}/api/v1/maintenance/tasks/${taskId}/verify`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({
                approved,
                verification_notes: verificationNotes
            })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to verify task.");
        return res;
    },

    async getStaffAvailability() {
        const response = await fetch(`${this.baseUrl}/api/v1/maintenance/staff-availability`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error("Failed to load staff availability.");
        return await response.json();
    },

    // ==================== ATTENDANCE MANAGEMENT ====================
    async getAttendanceRecords(filters = {}) {
        const params = new URLSearchParams();
        if (filters.date) params.append('date', filters.date);
        if (filters.start_date) params.append('start_date', filters.start_date);
        if (filters.end_date) params.append('end_date', filters.end_date);
        if (filters.student_id) params.append('student_id', filters.student_id);
        if (filters.hostel_id) params.append('hostel_id', filters.hostel_id);
        if (filters.building_id) params.append('building_id', filters.building_id);
        if (filters.room_id) params.append('room_id', filters.room_id);
        if (filters.status) params.append('status', filters.status);
        if (filters.limit) params.append('limit', filters.limit);
        if (filters.offset) params.append('offset', filters.offset);

        const qs = params.toString();
        const response = await fetch(`${this.baseUrl}/api/v1/attendance${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error("Failed to load attendance records.");
        return await response.json();
    },

    async markAttendance(data) {
        const response = await fetch(`${this.baseUrl}/api/v1/attendance`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(data)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to mark attendance.");
        return res;
    },

    async bulkMarkAttendance(data) {
        const response = await fetch(`${this.baseUrl}/api/v1/attendance/bulk`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(data)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to submit batch attendance.");
        return res;
    },

    async correctAttendance(attendanceId, data) {
        const response = await fetch(`${this.baseUrl}/api/v1/attendance/${attendanceId}`, {
            method: "PUT",
            headers: this.getHeaders(),
            body: JSON.stringify(data)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to correct attendance.");
        return res;
    },

    async getDailyAttendanceSummary(date = null, hostelId = null) {
        const params = new URLSearchParams();
        if (date) params.append('date', date);
        if (hostelId) params.append('hostel_id', hostelId);
        const qs = params.toString();

        const response = await fetch(`${this.baseUrl}/api/v1/attendance/summary${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error("Failed to load attendance daily summary.");
        return await response.json();
    },

    async getAttendanceReports(startDate, endDate, hostelId = null) {
        const params = new URLSearchParams({ start_date: startDate, end_date: endDate });
        if (hostelId) params.append('hostel_id', hostelId);

        const response = await fetch(`${this.baseUrl}/api/v1/attendance/reports?${params.toString()}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error("Failed to generate attendance report.");
        return await response.json();
    },

    async getStudentAttendanceHistory(studentId) {
        const response = await fetch(`${this.baseUrl}/api/v1/attendance/student/${studentId}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error("Failed to load student attendance history.");
        return await response.json();
    },

    async getStudentsForMarking(date, hostelId = null, buildingId = null, floorId = null, roomId = null) {
        const params = new URLSearchParams({ date });
        if (hostelId) params.append('hostel_id', hostelId);
        if (buildingId) params.append('building_id', buildingId);
        if (floorId) params.append('floor_id', floorId);
        if (roomId) params.append('room_id', roomId);

        const response = await fetch(`${this.baseUrl}/api/v1/attendance/students-for-marking?${params.toString()}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error("Failed to load resident students for marking.");
        return await response.json();
    },

    // ==================== LEAVE & OUTPASS MANAGEMENT ====================
    async getLeaveApplications(filters = {}) {
        const params = new URLSearchParams();
        if (filters.status && filters.status !== 'all') params.append('status', filters.status);
        if (filters.leave_type && filters.leave_type !== 'all') params.append('leave_type', filters.leave_type);
        if (filters.hostel_id) params.append('hostel_id', filters.hostel_id);
        if (filters.start_date) params.append('start_date', filters.start_date);
        if (filters.end_date) params.append('end_date', filters.end_date);
        if (filters.limit) params.append('limit', filters.limit);
        if (filters.offset) params.append('offset', filters.offset);

        const qs = params.toString();
        const response = await fetch(`${this.baseUrl}/api/v1/leave${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error("Failed to load leave applications.");
        return await response.json();
    },

    async submitLeaveApplication(data) {
        const response = await fetch(`${this.baseUrl}/api/v1/leave`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(data)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to submit leave application.");
        return res;
    },

    async getLeaveApplication(id) {
        const response = await fetch(`${this.baseUrl}/api/v1/leave/${id}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error("Failed to load leave application details.");
        return await response.json();
    },

    async updateLeaveApplication(id, data) {
        const response = await fetch(`${this.baseUrl}/api/v1/leave/${id}`, {
            method: "PUT",
            headers: this.getHeaders(),
            body: JSON.stringify(data)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to update leave application.");
        return res;
    },

    async approveLeaveApplication(id, remarks = "") {
        const response = await fetch(`${this.baseUrl}/api/v1/leave/${id}/approve`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ remarks })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to approve leave request.");
        return res;
    },

    async rejectLeaveApplication(id, reason) {
        const response = await fetch(`${this.baseUrl}/api/v1/leave/${id}/reject`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ reason })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to reject leave request.");
        return res;
    },

    async getOutpasses(filters = {}) {
        const params = new URLSearchParams();
        if (filters.status && filters.status !== 'all') params.append('status', filters.status);
        if (filters.outpass_number) params.append('outpass_number', filters.outpass_number);
        if (filters.limit) params.append('limit', filters.limit);
        if (filters.offset) params.append('offset', filters.offset);

        const qs = params.toString();
        const response = await fetch(`${this.baseUrl}/api/v1/outpasses${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error("Failed to load outpasses.");
        return await response.json();
    },

    async getOverdueOutpasses(hostelId = null) {
        const qs = hostelId ? `?hostel_id=${hostelId}` : "";
        const response = await fetch(`${this.baseUrl}/api/v1/outpasses/overdue${qs}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error("Failed to load overdue outpasses.");
        return await response.json();
    },

    async verifyOutpassExit(ref, remarks = "") {
        const response = await fetch(`${this.baseUrl}/api/v1/outpasses/${ref}/verify-exit`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ remarks })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to verify gate exit.");
        return res;
    },

    async verifyOutpassReturn(ref, remarks = "") {
        const response = await fetch(`${this.baseUrl}/api/v1/outpasses/${ref}/verify-return`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ remarks })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to verify gate return.");
        return res;
    },

    // ==================== VISITOR MANAGEMENT ====================
    async getVisitorLogs(filters = {}) {
        const params = new URLSearchParams();
        if (filters.status && filters.status !== 'all') params.append('status', filters.status);
        if (filters.hostel_id) params.append('hostel_id', filters.hostel_id);
        if (filters.date) params.append('date', filters.date);
        if (filters.search) params.append('search', filters.search);
        if (filters.limit) params.append('limit', filters.limit);
        if (filters.offset) params.append('offset', filters.offset);

        const qs = params.toString();
        const response = await fetch(`${this.baseUrl}/api/v1/visitors${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error("Failed to load visitor logs.");
        return await response.json();
    },

    async registerVisitor(data) {
        const response = await fetch(`${this.baseUrl}/api/v1/visitors`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(data)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to register visitor.");
        return res;
    },

    async getVisitorLog(id) {
        const response = await fetch(`${this.baseUrl}/api/v1/visitors/${id}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error("Failed to load visitor details.");
        return await response.json();
    },

    async approveVisitor(id, remarks = "") {
        const response = await fetch(`${this.baseUrl}/api/v1/visitors/${id}/approve`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ remarks })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to approve visitor.");
        return res;
    },

    async rejectVisitor(id, reason) {
        const response = await fetch(`${this.baseUrl}/api/v1/visitors/${id}/reject`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ reason })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to reject visitor.");
        return res;
    },

    async checkInVisitor(id, remarks = "", expectedExitTime = null) {
        const response = await fetch(`${this.baseUrl}/api/v1/visitors/${id}/check-in`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ remarks, expected_exit_time: expectedExitTime })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to check in visitor.");
        return res;
    },

    async checkOutVisitor(id, remarks = "") {
        const response = await fetch(`${this.baseUrl}/api/v1/visitors/${id}/check-out`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ remarks })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to check out visitor.");
        return res;
    },

    async getActiveVisitors(hostelId = null) {
        const qs = hostelId ? `?hostel_id=${hostelId}` : "";
        const response = await fetch(`${this.baseUrl}/api/v1/visitors/active${qs}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error("Failed to load active visitors.");
        return await response.json();
    },

    async getVisitorReports(startDate, endDate, hostelId = null) {
        const params = new URLSearchParams({ start_date: startDate, end_date: endDate });
        if (hostelId) params.append('hostel_id', hostelId);

        const response = await fetch(`${this.baseUrl}/api/v1/visitors/reports?${params.toString()}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error("Failed to load visitor reports.");
        return await response.json();
    },

    // ==================== FINANCIAL & FEE MANAGEMENT APIS ====================

    async getFeeStructures(params = {}) {
        const qs = new URLSearchParams(params).toString();
        const response = await fetch(`${this.baseUrl}/api/v1/fees/structures${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load fee structures.");
        return await response.json();
    },

    async createFeeStructure(payload) {
        const response = await fetch(`${this.baseUrl}/api/v1/fees/structures`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to create fee structure.");
        return res;
    },

    async getFeeStructure(id) {
        const response = await fetch(`${this.baseUrl}/api/v1/fees/structures/${id}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load fee structure.");
        return await response.json();
    },

    async updateFeeStructure(id, payload) {
        const response = await fetch(`${this.baseUrl}/api/v1/fees/structures/${id}`, {
            method: "PUT",
            headers: this.getHeaders(),
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to update fee structure.");
        return res;
    },

    async deleteFeeStructure(id) {
        const response = await fetch(`${this.baseUrl}/api/v1/fees/structures/${id}`, {
            method: "DELETE",
            headers: this.getHeaders()
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to delete fee structure.");
        return res;
    },

    async getInvoices(params = {}) {
        const qs = new URLSearchParams(params).toString();
        const response = await fetch(`${this.baseUrl}/api/v1/fees/invoices${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load invoices.");
        return await response.json();
    },

    async createInvoice(payload) {
        const response = await fetch(`${this.baseUrl}/api/v1/fees/invoices`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to create invoice.");
        return res;
    },

    async createBulkInvoices(payload) {
        const response = await fetch(`${this.baseUrl}/api/v1/fees/invoices/bulk`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to generate bulk invoices.");
        return res;
    },

    async getInvoice(id) {
        const response = await fetch(`${this.baseUrl}/api/v1/fees/invoices/${id}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load invoice details.");
        return await response.json();
    },

    async applyInvoiceDiscount(id, discountAmount, discountReason) {
        const response = await fetch(`${this.baseUrl}/api/v1/fees/invoices/${id}/discount`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ discount_amount: discountAmount, discount_reason: discountReason })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to apply discount.");
        return res;
    },

    async cancelInvoice(id, cancellationReason) {
        const response = await fetch(`${this.baseUrl}/api/v1/fees/invoices/${id}/cancel`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ cancellation_reason: cancellationReason })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to cancel invoice.");
        return res;
    },

    async getStudentInvoices(studentId, params = {}) {
        const qs = new URLSearchParams(params).toString();
        const response = await fetch(`${this.baseUrl}/api/v1/fees/invoices/student/${studentId}${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load student invoices.");
        return await response.json();
    },

    async getInvoiceReceipt(id) {
        const response = await fetch(`${this.baseUrl}/api/v1/fees/invoices/${id}/receipt`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load invoice receipt.");
        return await response.json();
    },

    async getPayments(params = {}) {
        const qs = new URLSearchParams(params).toString();
        const response = await fetch(`${this.baseUrl}/api/v1/fees/payments${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load payments.");
        return await response.json();
    },

    async recordPayment(payload) {
        const response = await fetch(`${this.baseUrl}/api/v1/fees/payments`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to record payment.");
        return res;
    },

    async getPayment(id) {
        const response = await fetch(`${this.baseUrl}/api/v1/fees/payments/${id}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load payment details.");
        return await response.json();
    },

    async reversePayment(id, reason) {
        const response = await fetch(`${this.baseUrl}/api/v1/fees/payments/${id}/reverse`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ reversal_reason: reason })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to reverse payment.");
        return res;
    },

    async getRefunds(params = {}) {
        const qs = new URLSearchParams(params).toString();
        const response = await fetch(`${this.baseUrl}/api/v1/fees/refunds${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load refunds.");
        return await response.json();
    },

    async requestRefund(payload) {
        const response = await fetch(`${this.baseUrl}/api/v1/fees/refunds`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to create refund request.");
        return res;
    },

    async reviewRefund(id, action, reason = "", transactionRef = "") {
        const endpoint = action.toLowerCase();
        const response = await fetch(`${this.baseUrl}/api/v1/fees/refunds/${id}/${endpoint}`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify({ action, reason, transaction_reference: transactionRef })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || `Failed to ${action} refund.`);
        return res;
    },

    async getFinancialDashboard(hostelId = null) {
        const qs = hostelId ? `?hostel_id=${hostelId}` : "";
        const response = await fetch(`${this.baseUrl}/api/v1/fees/dashboard${qs}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load financial dashboard.");
        return await response.json();
    },

    async getFinancialReports(reportType, params = {}) {
        const qs = new URLSearchParams(params).toString();
        const response = await fetch(`${this.baseUrl}/api/v1/fees/reports/${reportType}${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to generate financial report.");
        return await response.json();
    },

    async exportFinancialCsv(reportType, params = {}) {
        const allParams = { report_type: reportType, ...params };
        const qs = new URLSearchParams(allParams).toString();
        const response = await fetch(`${this.baseUrl}/api/v1/fees/reports/export?${qs}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error("Failed to export financial CSV.");
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `finance_${reportType}_${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        return true;
    },

    // ==================== MESS MANAGEMENT API ====================
    async getMessMenus(params = {}) {
        const qs = new URLSearchParams(params).toString();
        const response = await fetch(`${this.baseUrl}/api/v1/mess/menus${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load mess menus.");
        return await response.json();
    },

    async createMessMenu(payload) {
        const response = await fetch(`${this.baseUrl}/api/v1/mess/menus`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to create mess menu.");
        return res;
    },

    async updateMessMenu(id, payload) {
        const response = await fetch(`${this.baseUrl}/api/v1/mess/menus/${id}`, {
            method: "PUT",
            headers: this.getHeaders(),
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to update mess menu.");
        return res;
    },

    async deleteMessMenu(id) {
        const response = await fetch(`${this.baseUrl}/api/v1/mess/menus/${id}`, {
            method: "DELETE",
            headers: this.getHeaders()
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to delete mess menu.");
        return res;
    },

    async getMessSubscriptions(params = {}) {
        const qs = new URLSearchParams(params).toString();
        const response = await fetch(`${this.baseUrl}/api/v1/mess/subscriptions${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load mess subscriptions.");
        return await response.json();
    },

    async createMessSubscription(payload) {
        const response = await fetch(`${this.baseUrl}/api/v1/mess/subscriptions`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to create mess subscription.");
        return res;
    },

    async updateMessSubscriptionStatus(id, action, reason = "") {
        const qs = new URLSearchParams({ reason }).toString();
        const response = await fetch(`${this.baseUrl}/api/v1/mess/subscriptions/${id}/${action}?${qs}`, {
            method: "POST",
            headers: this.getHeaders()
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || `Failed to ${action} subscription.`);
        return res;
    },

    async getMealAttendance(params = {}) {
        const qs = new URLSearchParams(params).toString();
        const response = await fetch(`${this.baseUrl}/api/v1/mess/attendance${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load meal attendance.");
        return await response.json();
    },

    async recordMealAttendance(payload) {
        const response = await fetch(`${this.baseUrl}/api/v1/mess/attendance`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to record meal attendance.");
        return res;
    },

    async verifyMealAttendanceQR(payload) {
        const response = await fetch(`${this.baseUrl}/api/v1/mess/attendance/qr-verify`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "QR verification failed.");
        return res;
    },

    async correctMealAttendance(id, payload) {
        const response = await fetch(`${this.baseUrl}/api/v1/mess/attendance/${id}`, {
            method: "PUT",
            headers: this.getHeaders(),
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to correct attendance.");
        return res;
    },

    async getMessDashboard(hostelId = null) {
        const qs = hostelId ? `?hostel_id=${hostelId}` : "";
        const response = await fetch(`${this.baseUrl}/api/v1/mess/dashboard${qs}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load mess dashboard.");
        return await response.json();
    },

    // ==================== INVENTORY & STOCK API ====================
    async getInventoryCategories() {
        const response = await fetch(`${this.baseUrl}/api/v1/inventory/categories`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load categories.");
        return await response.json();
    },

    async createInventoryCategory(payload) {
        const response = await fetch(`${this.baseUrl}/api/v1/inventory/categories`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to create category.");
        return res;
    },

    async getSuppliers(activeOnly = false) {
        const qs = activeOnly ? "?active_only=true" : "";
        const response = await fetch(`${this.baseUrl}/api/v1/inventory/suppliers${qs}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load suppliers.");
        return await response.json();
    },

    async createSupplier(payload) {
        const response = await fetch(`${this.baseUrl}/api/v1/inventory/suppliers`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to create supplier.");
        return res;
    },

    async updateSupplier(id, payload) {
        const response = await fetch(`${this.baseUrl}/api/v1/inventory/suppliers/${id}`, {
            method: "PUT",
            headers: this.getHeaders(),
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to update supplier.");
        return res;
    },

    async getInventoryItems(params = {}) {
        const qs = new URLSearchParams(params).toString();
        const response = await fetch(`${this.baseUrl}/api/v1/inventory/items${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load items.");
        return await response.json();
    },

    async createInventoryItem(payload) {
        const response = await fetch(`${this.baseUrl}/api/v1/inventory/items`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to create item.");
        return res;
    },

    async updateInventoryItem(id, payload) {
        const response = await fetch(`${this.baseUrl}/api/v1/inventory/items/${id}`, {
            method: "PUT",
            headers: this.getHeaders(),
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to update item.");
        return res;
    },

    async recordStockInward(payload) {
        const response = await fetch(`${this.baseUrl}/api/v1/inventory/stock/inward`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to record stock inward.");
        return res;
    },

    async recordStockOutward(payload) {
        const response = await fetch(`${this.baseUrl}/api/v1/inventory/stock/outward`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to record stock outward.");
        return res;
    },

    async recordStockAdjustment(payload) {
        const response = await fetch(`${this.baseUrl}/api/v1/inventory/stock/adjustment`, {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || "Failed to record stock adjustment.");
        return res;
    },

    async getInventoryTransactions(params = {}) {
        const qs = new URLSearchParams(params).toString();
        const response = await fetch(`${this.baseUrl}/api/v1/inventory/transactions${qs ? '?' + qs : ''}`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load transactions.");
        return await response.json();
    },

    async getInventoryDashboard() {
        const response = await fetch(`${this.baseUrl}/api/v1/inventory/dashboard`, {
            headers: this.getHeaders()
        });
        if (!response.ok) throw new Error((await response.json()).detail || "Failed to load inventory dashboard.");
        return await response.json();
    }
};

window.API = API;
