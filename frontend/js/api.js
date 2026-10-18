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
    }
};

window.API = API;
