/**
 * AegisFace - Analytics, User Directory & System Settings Controller
 */

(function() {
    let trendChartInstance = null;
    let deptChartInstance = null;
    let hourlyChartInstance = null;

    // -------------------------------------------------------------
    // Analytics & Charts
    // -------------------------------------------------------------
    window.loadAnalytics = async function() {
        try {
            const res = await fetch('/api/analytics');
            if (!res.ok) return;

            const data = await res.json();
            const m = data.metrics;

            // KPI Cards
            const totalEl = document.getElementById('kpi-total-users');
            const presentEl = document.getElementById('kpi-present-today');
            const rateEl = document.getElementById('kpi-rate-pct');
            const ontimeEl = document.getElementById('kpi-ontime-today');
            const lateEl = document.getElementById('kpi-late-today');

            if (totalEl) totalEl.textContent = m.total_users;
            if (presentEl) presentEl.textContent = m.present_today;
            if (rateEl) rateEl.textContent = `${m.attendance_rate}% Turnout`;
            if (ontimeEl) ontimeEl.textContent = m.on_time_today;
            if (lateEl) lateEl.textContent = m.late_today;

            // 1. 7-Day Trend Chart
            renderTrendChart(m.recent_trend || []);

            // 2. Department Share Chart
            renderDeptChart(m.department_breakdown || []);

            // 3. Hourly Arrival Chart
            renderHourlyChart(m.hourly_distribution || []);

        } catch (e) {
            console.error("Analytics load error:", e);
        }
    };

    function renderTrendChart(trendData) {
        const canvas = document.getElementById('trendChart');
        if (!canvas || typeof Chart === 'undefined') return;

        const ctx = canvas.getContext('2d');
        if (trendChartInstance) trendChartInstance.destroy();

        const labels = trendData.map(d => d.date);
        const counts = trendData.map(d => d.count);

        const gradient = ctx.createLinearGradient(0, 0, 0, 240);
        gradient.addColorStop(0, 'rgba(99, 102, 241, 0.45)');
        gradient.addColorStop(1, 'rgba(99, 102, 241, 0.0)');

        trendChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels.length > 0 ? labels : ['No Data'],
                datasets: [{
                    label: 'Present Members',
                    data: counts.length > 0 ? counts : [0],
                    borderColor: '#6366f1',
                    backgroundColor: gradient,
                    borderWidth: 3,
                    fill: true,
                    tension: 0.35,
                    pointBackgroundColor: '#06b6d4',
                    pointBorderColor: '#fff',
                    pointRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.04)' },
                        ticks: { color: '#94a3b8', font: { family: 'JetBrains Mono', size: 11 } }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255, 255, 255, 0.04)' },
                        ticks: { color: '#94a3b8', precision: 0 }
                    }
                }
            }
        });
    }

    function renderDeptChart(deptData) {
        const canvas = document.getElementById('deptChart');
        if (!canvas || typeof Chart === 'undefined') return;

        const ctx = canvas.getContext('2d');
        if (deptChartInstance) deptChartInstance.destroy();

        const labels = deptData.map(d => d.department);
        const counts = deptData.map(d => d.count);
        const colors = ['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6'];

        deptChartInstance = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels.length > 0 ? labels : ['No Data'],
                datasets: [{
                    data: counts.length > 0 ? counts : [1],
                    backgroundColor: colors,
                    borderColor: '#0f172a',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: { color: '#f8fafc', font: { family: 'Inter', size: 11 } }
                    }
                },
                cutout: '65%'
            }
        });
    }

    function renderHourlyChart(hourlyData) {
        const canvas = document.getElementById('hourlyChart');
        if (!canvas || typeof Chart === 'undefined') return;

        const ctx = canvas.getContext('2d');
        if (hourlyChartInstance) hourlyChartInstance.destroy();

        const labels = hourlyData.map(d => `${d.hour}:00`);
        const counts = hourlyData.map(d => d.count);

        hourlyChartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels.length > 0 ? labels : ['09:00'],
                datasets: [{
                    label: 'Arrivals',
                    data: counts.length > 0 ? counts : [0],
                    backgroundColor: 'rgba(6, 182, 212, 0.7)',
                    borderColor: '#06b6d4',
                    borderWidth: 1,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.04)' },
                        ticks: { color: '#94a3b8', font: { family: 'JetBrains Mono', size: 11 } }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255, 255, 255, 0.04)' },
                        ticks: { color: '#94a3b8', precision: 0 }
                    }
                }
            }
        });
    }

    // -------------------------------------------------------------
    // User Directory
    // -------------------------------------------------------------
    let allDirectoryUsers = [];

    window.loadUserDirectory = async function() {
        const grid = document.getElementById('user-cards-grid');
        if (!grid) return;

        grid.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-muted);">
                <i class="fa-solid fa-circle-notch fa-spin fa-2x"></i>
                <p style="margin-top: 10px;">Loading registered members...</p>
            </div>
        `;

        try {
            const res = await fetch('/api/users');
            if (!res.ok) throw new Error("Could not load users");

            const data = await res.json();
            allDirectoryUsers = data.users || [];
            renderUserCards(allDirectoryUsers);

        } catch (e) {
            console.error("Directory error:", e);
            grid.innerHTML = `
                <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--rose);">
                    <i class="fa-solid fa-triangle-exclamation fa-2x"></i>
                    <p style="margin-top: 10px;">Failed to load user directory.</p>
                </div>
            `;
        }
    };

    function renderUserCards(users) {
        const grid = document.getElementById('user-cards-grid');
        if (!grid) return;

        if (!users || users.length === 0) {
            grid.innerHTML = `
                <div style="grid-column: 1/-1; text-align: center; padding: 60px; color: var(--text-muted);">
                    <i class="fa-solid fa-user-slash fa-3x"></i>
                    <p style="margin-top: 14px;">No members found. Use "Enroll Member" to register faces.</p>
                </div>
            `;
            return;
        }

        let html = '';
        users.forEach(u => {
            const avatarHtml = u.photo_path
                ? `<img src="${u.photo_path}" class="user-card-avatar" alt="${u.name}" onerror="this.outerHTML='<div class=\\'user-card-avatar-fallback\\'>${u.name[0]}</div>'">`
                : `<div class="user-card-avatar-fallback">${u.name[0]}</div>`;

            html += `
                <div class="user-card">
                    ${avatarHtml}
                    <h4>${u.name}</h4>
                    <span class="user-card-id">${u.user_id}</span>
                    <span class="user-card-dept">${u.department} • ${u.role || 'Staff'}</span>
                    
                    <div class="user-card-footer">
                        <span style="font-size:11px; color:var(--text-muted);">${u.created_at ? u.created_at.split('T')[0] : 'Enrolled'}</span>
                        <button class="btn btn-sm btn-outline" style="color:var(--rose); border-color:rgba(244,63,94,0.3);" onclick="window.deleteUser('${u.user_id}', '${u.name}')">
                            <i class="fa-solid fa-trash-can"></i> Delete
                        </button>
                    </div>
                </div>
            `;
        });

        grid.innerHTML = html;
    }

    window.deleteUser = async function(userId, userName) {
        if (!confirm(`Are you sure you want to delete '${userName}' (${userId})? This will remove their biometric vector.`)) {
            return;
        }

        try {
            const res = await fetch(`/api/users/${userId}`, { method: 'DELETE' });
            if (res.ok) {
                window.playSound('click');
                window.showToast("User Removed", `Profile for '${userName}' deleted successfully.`);
                window.loadUserDirectory();
            } else {
                window.showToast("Error", "Could not delete user profile.", "danger");
            }
        } catch (e) {
            console.error("Delete error:", e);
        }
    };

    // -------------------------------------------------------------
    // Settings Management
    // -------------------------------------------------------------
    window.loadSettings = async function() {
        try {
            const res = await fetch('/api/settings');
            if (!res.ok) return;

            const data = await res.json();
            const s = data.settings || {};

            const simSlider = document.getElementById('cfg-similarity');
            const simVal = document.getElementById('val-similarity');
            const cooldownInput = document.getElementById('cfg-cooldown');
            const livenessSelect = document.getElementById('cfg-liveness');
            const camIdxInput = document.getElementById('cfg-cam-idx');
            const startInput = document.getElementById('cfg-work-start');
            const graceInput = document.getElementById('cfg-grace-mins');
            const endInput = document.getElementById('cfg-work-end');
            const manualTimeInput = document.getElementById('cfg-manual-time');

            if (simSlider && s.similarity_threshold) {
                simSlider.value = s.similarity_threshold;
                if (simVal) simVal.textContent = s.similarity_threshold;
            }
            if (cooldownInput && s.cooldown_seconds) cooldownInput.value = s.cooldown_seconds;
            if (livenessSelect && s.liveness_enabled) livenessSelect.value = s.liveness_enabled;
            if (camIdxInput && s.camera_index) camIdxInput.value = s.camera_index;
            if (startInput && s.work_start_time) startInput.value = s.work_start_time;
            if (graceInput && s.grace_minutes) graceInput.value = s.grace_minutes;
            if (endInput && s.work_end_time) endInput.value = s.work_end_time;
            if (manualTimeInput) manualTimeInput.value = s.manual_attendance_time || '';

        } catch (e) {
            console.error("Settings load error:", e);
        }
    };

    async function handleSettingsSave(e) {
        e.preventDefault();

        const simSlider = document.getElementById('cfg-similarity');
        const cooldownInput = document.getElementById('cfg-cooldown');
        const livenessSelect = document.getElementById('cfg-liveness');
        const camIdxInput = document.getElementById('cfg-cam-idx');
        const startInput = document.getElementById('cfg-work-start');
        const graceInput = document.getElementById('cfg-grace-mins');
        const endInput = document.getElementById('cfg-work-end');
        const manualTimeInput = document.getElementById('cfg-manual-time');

        const payload = {
            similarity_threshold: simSlider ? simSlider.value : "0.45",
            cooldown_seconds: cooldownInput ? cooldownInput.value : "60",
            liveness_enabled: livenessSelect ? livenessSelect.value : "true",
            camera_index: camIdxInput ? camIdxInput.value : "0",
            work_start_time: startInput ? startInput.value : "09:00",
            grace_minutes: graceInput ? graceInput.value : "15",
            work_end_time: endInput ? endInput.value : "17:00",
            manual_attendance_time: manualTimeInput ? manualTimeInput.value : ""
        };

        try {
            const res = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                window.playSound('success');
                window.showToast("Settings Saved", "System configuration updated successfully.", "success");
            }
        } catch (err) {
            console.error("Save settings error:", err);
            window.showToast("Error", "Could not save system settings.", "danger");
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        // Directory search filter
        const dirSearch = document.getElementById('user-directory-search');
        if (dirSearch) {
            dirSearch.addEventListener('input', (e) => {
                const term = e.target.value.toLowerCase().trim();
                const filtered = allDirectoryUsers.filter(u => 
                    u.name.toLowerCase().includes(term) ||
                    u.user_id.toLowerCase().includes(term) ||
                    u.department.toLowerCase().includes(term)
                );
                renderUserCards(filtered);
            });
        }

        // Settings similarity slider live feedback
        const simSlider = document.getElementById('cfg-similarity');
        const simVal = document.getElementById('val-similarity');
        if (simSlider && simVal) {
            simSlider.addEventListener('input', (e) => {
                simVal.textContent = e.target.value;
            });
        }

        const settingsForm = document.getElementById('settings-form');
        if (settingsForm) {
            settingsForm.addEventListener('submit', handleSettingsSave);
        }
    });

})();
