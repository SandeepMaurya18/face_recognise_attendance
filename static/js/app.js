/**
 * AegisFace - Global Application & Audio Controller
 */

// Global App State
window.AppState = {
    activeTab: 'kiosk',
    soundEnabled: true,
    audioCtx: null,
    punchMode: 'AUTO',
    settings: {}
};

// -------------------------------------------------------------
// Web Audio API Synthesizer
// -------------------------------------------------------------
function getAudioContext() {
    if (!window.AppState.audioCtx) {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (AudioContext) {
            window.AppState.audioCtx = new AudioContext();
        }
    }
    if (window.AppState.audioCtx && window.AppState.audioCtx.state === 'suspended') {
        window.AppState.audioCtx.resume();
    }
    return window.AppState.audioCtx;
}

window.playSound = function(type = 'success') {
    if (!window.AppState.soundEnabled) return;
    try {
        const ctx = getAudioContext();
        if (!ctx) return;

        if (type === 'success') {
            // Futuristic pleasant biometric chime: D5 (587.33Hz) -> A5 (880Hz)
            const osc1 = ctx.createOscillator();
            const osc2 = ctx.createOscillator();
            const gainNode = ctx.createGain();

            osc1.type = 'sine';
            osc2.type = 'triangle';

            const now = ctx.currentTime;
            osc1.frequency.setValueAtTime(587.33, now);
            osc1.frequency.exponentialRampToValueAtTime(880.00, now + 0.12);

            osc2.frequency.setValueAtTime(880.00, now + 0.08);
            osc2.frequency.exponentialRampToValueAtTime(1174.66, now + 0.22);

            gainNode.gain.setValueAtTime(0.2, now);
            gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.35);

            osc1.connect(gainNode);
            osc2.connect(gainNode);
            gainNode.connect(ctx.destination);

            osc1.start(now);
            osc2.start(now + 0.08);
            osc1.stop(now + 0.35);
            osc2.stop(now + 0.35);

        } else if (type === 'alert') {
            // Rejection buzzer: low saw wave
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            const now = ctx.currentTime;

            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(220, now);
            osc.frequency.linearRampToValueAtTime(140, now + 0.25);

            gain.gain.setValueAtTime(0.3, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.28);

            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(now);
            osc.stop(now + 0.28);

        } else if (type === 'click') {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            const now = ctx.currentTime;

            osc.type = 'sine';
            osc.frequency.setValueAtTime(1200, now);
            gain.gain.setValueAtTime(0.05, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.04);

            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(now);
            osc.stop(now + 0.04);
        }
    } catch (e) {
        console.warn("Web Audio error:", e);
    }
};

// -------------------------------------------------------------
// Toast Notifications
// -------------------------------------------------------------
window.showToast = function(title, message, type = 'success', duration = 3500) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    let iconClass = 'fa-circle-check';
    if (type === 'warning') iconClass = 'fa-triangle-exclamation';
    if (type === 'danger') iconClass = 'fa-circle-xmark';

    toast.innerHTML = `
        <i class="fa-solid ${iconClass} toast-icon"></i>
        <div class="toast-content">
            <h5>${title}</h5>
            <p>${message}</p>
        </div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, duration);
};

// -------------------------------------------------------------
// Tab Router & Titles
// -------------------------------------------------------------
const TAB_TITLES = {
    kiosk: { title: "Live Attendance Kiosk", subtitle: "Real-time deep learning facial detection and punch verification" },
    enroll: { title: "Member Enrollment", subtitle: "Register new employee with face biometric embeddings" },
    logs: { title: "Attendance History & Logs", subtitle: "Filter, search, and export official attendance records" },
    analytics: { title: "Analytics & Insights", subtitle: "Real-time key performance indicators and turnout trends" },
    users: { title: "Registered User Directory", subtitle: "Manage active members and biometric profiles" },
    settings: { title: "System Settings", subtitle: "Configure recognition threshold, cooldown, and working schedules" }
};

window.switchTab = function(tabId) {
    window.AppState.activeTab = tabId;

    // Update nav items
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
    });

    // Update tab panes
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.remove('active');
    });
    const targetPane = document.getElementById(`tab-${tabId}`);
    if (targetPane) targetPane.classList.add('active');

    // Update page header
    const info = TAB_TITLES[tabId] || { title: "Attendance System", subtitle: "" };
    document.getElementById('page-title').textContent = info.title;
    document.getElementById('page-subtitle').textContent = info.subtitle;

    window.playSound('click');

    // Trigger tab-specific loaders
    if (tabId === 'logs' && window.fetchAttendanceLogs) {
        window.fetchAttendanceLogs(1);
    } else if (tabId === 'analytics' && window.loadAnalytics) {
        window.loadAnalytics();
    } else if (tabId === 'users' && window.loadUserDirectory) {
        window.loadUserDirectory();
    } else if (tabId === 'settings' && window.loadSettings) {
        window.loadSettings();
    }
};

// -------------------------------------------------------------
// Modal Dialog Controller
// -------------------------------------------------------------
window.openModal = function(imgUrl, metaHtml) {
    const modal = document.getElementById('snapshot-modal');
    const modalImg = document.getElementById('modal-img');
    const modalMeta = document.getElementById('modal-meta');

    if (modal && modalImg) {
        modalImg.src = imgUrl;
        if (modalMeta) modalMeta.innerHTML = metaHtml || '';
        modal.classList.add('active');
    }
};

window.closeModal = function() {
    const modal = document.getElementById('snapshot-modal');
    if (modal) modal.classList.remove('active');
};

// -------------------------------------------------------------
// App Initialization
// -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    // 1. Setup Navigation Clicks
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            if (tab) window.switchTab(tab);
        });
    });

    // 2. Sound Toggle Button
    const btnSound = document.getElementById('btn-toggle-sound');
    if (btnSound) {
        btnSound.addEventListener('click', () => {
            window.AppState.soundEnabled = !window.AppState.soundEnabled;
            btnSound.innerHTML = window.AppState.soundEnabled
                ? '<i class="fa-solid fa-volume-high"></i>'
                : '<i class="fa-solid fa-volume-xmark" style="color:var(--rose)"></i>';
            window.showToast("Sound Settings", `Audio cues ${window.AppState.soundEnabled ? 'Enabled' : 'Muted'}`);
        });
    }

    // 3. Punch mode buttons
    document.querySelectorAll('[data-punch-mode]').forEach(button => {
        button.addEventListener('click', () => {
            window.AppState.punchMode = button.dataset.punchMode;
            document.querySelectorAll('[data-punch-mode]').forEach(item => {
                item.classList.toggle('active', item === button);
            });
            window.showToast("Punch Mode Updated", `${button.textContent.trim()} selected`);
        });
    });

    // 4. Live Clock
    const clockEl = document.getElementById('live-clock');
    const dateEl = document.getElementById('live-date');
    function updateClock() {
        const now = new Date();
        if (clockEl) clockEl.textContent = now.toTimeString().split(' ')[0];
        if (dateEl) dateEl.textContent = now.toISOString().split('T')[0];
    }
    updateClock();
    setInterval(updateClock, 1000);

    // 5. Fullscreen Kiosk
    const btnFullscreen = document.getElementById('btn-fullscreen-kiosk');
    if (btnFullscreen) {
        btnFullscreen.addEventListener('click', () => {
            const kiosk = document.getElementById('kiosk-container');
            if (!document.fullscreenElement) {
                if (kiosk.requestFullscreen) kiosk.requestFullscreen();
            } else {
                if (document.exitFullscreen) document.exitFullscreen();
            }
        });
    }
});
