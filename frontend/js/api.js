/**
 * Lightweight API Client for Hostel Management System Web App
 * Course: BBAT104 Fundamentals of TQM
 * Quality Goal: Q05 - Reduce Response Time
 */

const API = {
    baseUrl: window.location.origin,

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
                    clientLatencyMs: clientLatency,
                    serverLatencyMs: serverLatency ? parseFloat(serverLatency) : clientLatency,
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
                clientLatencyMs: performance.now() - t0,
                error: err.message
            };
        }
    }
};

window.API = API;
