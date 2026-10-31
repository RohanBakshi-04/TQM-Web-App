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

    /**
     * Fetch live dashboard aggregation metrics.
     */
    async getDashboardStats() {
        const response = await fetch(`${this.baseUrl}/api/v1/dashboard/stats`, {
            headers: this.getHeaders()
        });
        if (!response.ok) return null;
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
    }
};

window.API = API;
