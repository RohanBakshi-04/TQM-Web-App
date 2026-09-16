/**
 * Alpine.js Application Controller
 * Course: BBAT104 Fundamentals of TQM
 * Quality Goal: Q05 - Reduce Response Time
 */

document.addEventListener("alpine:init", () => {
    Alpine.data("appRoot", () => ({
        activeSection: "welcome", // "welcome" | "login" | "architecture"
        selectedRole: "admin",
        systemHealth: {
            status: "connecting",
            database: { status: "checking", engine: "--", journal_mode: "--", ping_latency_ms: 0 },
            q05_telemetry: { meets_sla: false, sla_target_ms: 10.0 },
            serverLatencyMs: 0
        },
        healthCheckInterval: null,
        loginNotice: "",

        init() {
            this.fetchHealth();
            // Poll health every 8 seconds for continuous telemetry
            this.healthCheckInterval = setInterval(() => this.fetchHealth(), 8000);
        },

        async fetchHealth() {
            const result = await window.API.checkHealth();
            if (result && result.status) {
                this.systemHealth = result;
            }
        },

        selectRole(role) {
            this.selectedRole = role;
            this.loginNotice = "";
        },

        triggerLoginPlaceholder() {
            this.loginNotice = `Authentication for '${this.selectedRole.toUpperCase()}' is staged for Prompt 03 per project roadmap. Backend API and SQLite foundations are active.`;
        }
    }));
});
