// tracking-client-log.js — send JS logs to server file (data/logs/app.log)
// Usage: clientLog("msg") | clientLog("msg", data, "warn")
window.clientLog = function(msg, data, level) {
    const body = { msg: String(msg), level: level || "info" };
    if (data !== undefined) body.data = typeof data === "object" ? JSON.stringify(data) : String(data);
    fetch("/admin/api/client-log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    }).catch(() => {});  // fire-and-forget, never throw
};
