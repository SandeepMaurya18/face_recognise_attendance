/**
 * AegisFace - Live Attendance Kiosk & Biometric HUD Controller
 */

(function() {
    let videoStream = null;
    let isProcessing = false;
    let recognitionInterval = null;
    let currentSource = 'browser'; // 'browser' or 'usb'

    let lastFpsTime = performance.now();
    let frameCount = 0;
    let currentFps = 0;

    const videoEl = document.getElementById('kiosk-video');
    const mjpegEl = document.getElementById('kiosk-mjpeg');
    const overlayCanvas = document.getElementById('kiosk-overlay');
    const overlayCtx = overlayCanvas ? overlayCanvas.getContext('2d') : null;
    const fpsDisplay = document.getElementById('fps-display');
    const recStatus = document.getElementById('recognition-status');

    // Offscreen canvas for frame capture
    const captureCanvas = document.createElement('canvas');
    const captureCtx = captureCanvas.getContext('2d');

    // -------------------------------------------------------------
    // Camera Stream Management
    // -------------------------------------------------------------
    async function startBrowserCamera() {
        try {
            stopCamera();
            currentSource = 'browser';
            if (videoEl) videoEl.style.display = 'block';
            if (mjpegEl) mjpegEl.style.display = 'none';

            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                throw new Error('Camera access is unavailable in this browser context.');
            }

            videoStream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    facingMode: 'user'
                },
                audio: false
            });

            videoEl.srcObject = videoStream;
            await videoEl.play();

            updateCameraStatus(true, "Camera Live & Scanning");
            startRecognitionLoop();

        } catch (err) {
            console.error("Webcam access error:", err);
            let errMsg = "Could not access browser webcam.";
            let errDetail = "Please grant camera permission in your browser.";

            if (!window.isSecureContext && location.hostname !== "localhost" && location.hostname !== "127.0.0.1") {
                errMsg = "Insecure Context Block";
                errDetail = "Browsers require HTTPS or http://localhost to access cameras. Use http://localhost:8000";
            } else if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
                errMsg = "Camera Permission Blocked";
                errDetail = "Click the camera/lock icon in your browser address bar and set Camera to 'Allow', then refresh.";
            } else if (err.message && err.message.includes("unavailable")) {
                errMsg = "Camera Unavailable";
                errDetail = "Open this site through http://localhost or HTTPS, and use a browser that supports webcam access.";
            } else if (err.name === "NotReadableError" || err.name === "TrackStartError") {
                errMsg = "Camera In Use";
                errDetail = "Webcam is currently locked by another application (Zoom, Teams, Skype, etc.). Please close other apps.";
            } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
                errMsg = "No Camera Detected";
                errDetail = "No webcam hardware found. Connect a camera or switch to 'USB Server Cam' mode.";
            }

            updateCameraStatus(false, errMsg);
            window.showToast(errMsg, errDetail, "danger");
        }
    }

    function startUsbCamera() {
        stopCamera();
        currentSource = 'usb';
        if (videoEl) videoEl.style.display = 'none';
        if (mjpegEl) {
            mjpegEl.style.display = 'block';
            mjpegEl.src = "/video_feed?" + new Date().getTime();
        }
        updateCameraStatus(true, "Server USB Camera Connected");
        startRecognitionLoop();
    }

    function stopCamera() {
        if (recognitionInterval) {
            clearInterval(recognitionInterval);
            recognitionInterval = null;
        }
        if (videoStream) {
            videoStream.getTracks().forEach(track => track.stop());
            videoStream = null;
        }
        if (videoEl) videoEl.srcObject = null;
        if (mjpegEl) mjpegEl.src = "";
        clearOverlay();
        updateCameraStatus(false, "Scanner Paused");
    }

    function updateCameraStatus(active, text) {
        if (!recStatus) return;
        const dotClass = active ? 'green' : 'amber';
        recStatus.innerHTML = `<span class="pulse-dot ${dotClass}"></span> ${text}`;
        const btnToggle = document.getElementById('btn-camera-toggle');
        if (btnToggle) {
            btnToggle.innerHTML = active 
                ? '<i class="fa-solid fa-power-off"></i> <span>Stop Camera</span>'
                : '<i class="fa-solid fa-play"></i> <span>Start Camera</span>';
        }
    }

    function clearOverlay() {
        if (overlayCtx && overlayCanvas) {
            overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
        }
    }

    // -------------------------------------------------------------
    // Biometric HUD Drawing on Overlay Canvas
    // -------------------------------------------------------------
    function resizeOverlay() {
        if (!overlayCanvas) return;
        const sourceEl = currentSource === 'usb' ? mjpegEl : videoEl;
        if (!sourceEl) return;
        const rect = sourceEl.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
            overlayCanvas.width = rect.width;
            overlayCanvas.height = rect.height;
        }
    }

    function drawBiometricHUD(faces, frameW, frameH) {
        if (!overlayCtx || !overlayCanvas) return;
        overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

        const canvasW = overlayCanvas.width;
        const canvasH = overlayCanvas.height;

        const scaleX = canvasW / frameW;
        const scaleY = canvasH / frameH;

        faces.forEach(face => {
            const [rx, ry, rw, rh] = face.bbox;

            // Note: Since video is mirrored with scaleX(-1) in CSS, we adjust X for mirror coordinates
            const x = canvasW - (rx + rw) * scaleX;
            const y = ry * scaleY;
            const w = rw * scaleX;
            const h = rh * scaleY;

            const status = face.status;
            const user = face.user;
            const conf = face.confidence_percent || 0;
            const isLive = face.liveness ? face.liveness.is_live : true;

            let color = '#94a3b8'; // default unknown slate
            let label = 'Unknown Face';
            let subtitle = 'Not Enrolled';

            if (status === 'IDENTIFIED' && user) {
                color = '#10b981'; // emerald
                label = user.name;
                subtitle = `${user.department} • ${conf}% Match`;
            } else if (status === 'SPOOF_REJECTED') {
                color = '#f43f5e'; // rose
                label = 'SPOOF REJECTED';
                subtitle = face.liveness.reason || 'Static Image Detected';
            }

            // 1. Draw glowing corner brackets
            const cornerLen = Math.min(22, w * 0.25);
            overlayCtx.lineWidth = 3;
            overlayCtx.strokeStyle = color;
            overlayCtx.shadowColor = color;
            overlayCtx.shadowBlur = 10;

            // Top-Left
            overlayCtx.beginPath();
            overlayCtx.moveTo(x, y + cornerLen);
            overlayCtx.lineTo(x, y);
            overlayCtx.lineTo(x + cornerLen, y);
            overlayCtx.stroke();

            // Top-Right
            overlayCtx.beginPath();
            overlayCtx.moveTo(x + w - cornerLen, y);
            overlayCtx.lineTo(x + w, y);
            overlayCtx.lineTo(x + w, y + cornerLen);
            overlayCtx.stroke();

            // Bottom-Left
            overlayCtx.beginPath();
            overlayCtx.moveTo(x, y + h - cornerLen);
            overlayCtx.lineTo(x, y + h);
            overlayCtx.lineTo(x + cornerLen, y + h);
            overlayCtx.stroke();

            // Bottom-Right
            overlayCtx.beginPath();
            overlayCtx.moveTo(x + w - cornerLen, y + h);
            overlayCtx.lineTo(x + w, y + h);
            overlayCtx.lineTo(x + w, y + h - cornerLen);
            overlayCtx.stroke();

            // Subtle bounding box
            overlayCtx.lineWidth = 1;
            overlayCtx.shadowBlur = 0;
            overlayCtx.strokeRect(x, y, w, h);

            // 2. Info Pill Badge Above Face
            const tagW = Math.max(130, w * 1.05);
            const tagH = 36;
            const tagY = Math.max(tagH + 8, y - 8);

            overlayCtx.fillStyle = 'rgba(15, 23, 42, 0.9)';
            overlayCtx.strokeStyle = color;
            overlayCtx.lineWidth = 1;
            overlayCtx.beginPath();
            overlayCtx.roundRect(x, tagY - tagH, tagW, tagH, 6);
            overlayCtx.fill();
            overlayCtx.stroke();

            // Name
            overlayCtx.fillStyle = '#ffffff';
            overlayCtx.font = '600 12px Inter, sans-serif';
            overlayCtx.fillText(label, x + 8, tagY - 20);

            // Subtitle / Dept
            overlayCtx.fillStyle = color;
            overlayCtx.font = '500 10px Inter, sans-serif';
            overlayCtx.fillText(subtitle, x + 8, tagY - 7);
        });
    }

    // -------------------------------------------------------------
    // Live Recognition Cycle
    // -------------------------------------------------------------
    async function captureAndRecognize() {
        const sourceReady = currentSource === 'usb'
            ? mjpegEl && mjpegEl.complete && mjpegEl.naturalWidth > 0
            : videoStream && videoEl.readyState >= 2;
        if (isProcessing || !sourceReady) return;
        isProcessing = true;

        try {
            resizeOverlay();

            const vW = currentSource === 'usb'
                ? (mjpegEl.naturalWidth || 640)
                : (videoEl.videoWidth || 640);
            const vH = currentSource === 'usb'
                ? (mjpegEl.naturalHeight || 480)
                : (videoEl.videoHeight || 480);

            captureCanvas.width = vW;
            captureCanvas.height = vH;
            captureCtx.drawImage(currentSource === 'usb' ? mjpegEl : videoEl, 0, 0, vW, vH);

            // Convert to JPEG data URL
            const frameBase64 = captureCanvas.toDataURL('image/jpeg', 0.72);

            const payload = {
                image: frameBase64,
                force_punch_type: window.AppState.punchMode === 'AUTO' ? null : window.AppState.punchMode
            };

            const response = await fetch('/api/recognize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                const data = await response.json();
                if (data.success && data.faces) {
                    drawBiometricHUD(data.faces, data.frame_size[0], data.frame_size[1]);

                    // Handle Punches
                    if (data.punches && data.punches.length > 0) {
                        data.punches.forEach(p => handlePunchEvent(p));
                    }
                }
            } else {
                console.warn("Recognition request failed:", response.status);
            }

            // Calculate FPS
            frameCount++;
            const now = performance.now();
            if (now - lastFpsTime >= 1000) {
                currentFps = Math.round((frameCount * 1000) / (now - lastFpsTime));
                frameCount = 0;
                lastFpsTime = now;
                if (fpsDisplay) fpsDisplay.textContent = `FPS: ${currentFps}`;
            }

        } catch (err) {
            console.warn("Recognition loop exception:", err);
        } finally {
            isProcessing = false;
        }
    }

    function startRecognitionLoop() {
        if (recognitionInterval) clearInterval(recognitionInterval);
        // Process a frame every 240ms (~4 FPS for deep neural network, perfectly responsive)
        recognitionInterval = setInterval(captureAndRecognize, 240);
    }

    // -------------------------------------------------------------
    // Punch Notification & Feed Updating
    // -------------------------------------------------------------
    function handlePunchEvent(punch) {
        if (!punch) return;

        if (punch.success) {
            window.playSound('success');
            const user = punch.user;
            const record = punch.record;

            window.showToast(
                `Punch Recorded (${record.punch_type.replace('_', ' ')})`,
                `${user.name} - ${record.status.replace('_', ' ')} at ${record.time}`,
                'success'
            );

            updateLatestAttendance(record, user);
            prependPunchFeed(record, user);
            updateTodayCounts();

        } else if (punch.action === 'COOLDOWN_ACTIVE') {
            // Already logged within cooldown period, no sound spam
            console.log(punch.message);
        } else if (punch.action === 'ALREADY_CHECKED_IN' || punch.action === 'NOT_CHECKED_IN') {
            window.showToast("Punch Not Recorded", punch.message, "warning");
        } else if (punch.action === 'SPOOF_REJECTED') {
            window.playSound('alert');
            window.showToast("Anti-Spoof Warning", punch.message || "Potential photo spoof rejected", "danger");
        }
    }

    function updateLatestAttendance(record, user) {
        const nameEl = document.getElementById('latest-attendance-name');
        const detailsEl = document.getElementById('latest-attendance-details');
        const panel = document.getElementById('latest-attendance');
        if (!nameEl || !detailsEl) return;

        const action = record.punch_type === 'CHECK_IN' ? 'CHECKED IN' : 'CHECKED OUT';
        const status = (record.status || 'NORMAL').replace('_', ' ');
        nameEl.textContent = `${action}: ${user.name}`;
        detailsEl.textContent = `${user.user_id} • ${user.department} • ${record.date} ${record.time} • ${status}`;
        if (panel) {
            panel.classList.remove('latest-attendance-flash');
            void panel.offsetWidth;
            panel.classList.add('latest-attendance-flash');
        }
    }

    function prependPunchFeed(record, user) {
        const feedList = document.getElementById('recent-punches-list');
        if (!feedList) return;

        // Remove empty state if present
        const empty = feedList.querySelector('.empty-state');
        if (empty) empty.remove();

        const item = document.createElement('div');
        item.className = 'punch-feed-item';

        const statusLower = (record.status || 'NORMAL').toLowerCase().replace('_', '');
        const punchTypeLabel = record.punch_type === 'CHECK_IN' ? 'CHECKED IN' : 'CHECKED OUT';

        const avatarHtml = user.photo_path
            ? `<img src="${user.photo_path}" class="punch-avatar" alt="${user.name}" onerror="this.outerHTML='<div class=\\'punch-avatar-fallback\\'>${user.name[0]}</div>'">`
            : `<div class="punch-avatar-fallback">${user.name[0]}</div>`;

        item.innerHTML = `
            ${avatarHtml}
            <div class="punch-details">
                <h4>${user.name}</h4>
                <p>${user.department} • <span style="font-family:var(--font-mono); color:var(--cyan);">${user.user_id}</span></p>
            </div>
            <div class="punch-meta">
                <span class="punch-time">${record.time}</span>
                <span class="status-pill ${statusLower}">${punchTypeLabel} - ${record.status.replace('_', ' ')}</span>
            </div>
        `;

        feedList.insertBefore(item, feedList.firstChild);

        // Keep at most 15 items in live feed
        if (feedList.children.length > 15) {
            feedList.removeChild(feedList.lastChild);
        }
    }

    async function loadRecentPunches() {
        try {
            const response = await fetch('/api/attendance?limit=15&offset=0');
            if (!response.ok) return;

            const data = await response.json();
            const logs = data.logs || [];
            const feedList = document.getElementById('recent-punches-list');
            if (!feedList || logs.length === 0) return;

            feedList.innerHTML = '';
            logs.slice().reverse().forEach(record => {
                prependPunchFeed(record, {
                    name: record.name,
                    user_id: record.user_id,
                    department: record.department,
                    photo_path: null
                });
            });

            const latest = logs[0];
            updateLatestAttendance(latest, {
                name: latest.name,
                user_id: latest.user_id,
                department: latest.department
            });
        } catch (error) {
            console.warn("Recent punch feed error:", error);
        }
    }

    async function updateTodayCounts() {
        try {
            const res = await fetch('/api/analytics');
            if (res.ok) {
                const data = await res.json();
                const m = data.metrics;
                const todayBadge = document.getElementById('live-today-count');
                const ontimeEl = document.getElementById('mini-ontime');
                const lateEl = document.getElementById('mini-late');
                const totalEl = document.getElementById('mini-total');

                if (todayBadge) todayBadge.textContent = `${m.present_today} Today`;
                if (ontimeEl) ontimeEl.textContent = m.on_time_today;
                if (lateEl) lateEl.textContent = m.late_today;
                if (totalEl) totalEl.textContent = m.total_users;
            }
        } catch (e) {
            console.warn("Error updating counts:", e);
        }
    }

    // -------------------------------------------------------------
    // Event Listeners
    // -------------------------------------------------------------
    document.addEventListener('DOMContentLoaded', () => {
        // Start the default Browser Cam as soon as the kiosk is opened.
        stopCamera();
        updateTodayCounts();
        loadRecentPunches();

        // Cam Switchers
        const browserTab = document.getElementById('cam-browser-btn');
        const usbTab = document.getElementById('cam-usb-btn');
        const btnCamToggle = document.getElementById('btn-camera-toggle');

        if (browserTab && usbTab) {
            browserTab.addEventListener('click', () => {
                browserTab.classList.add('active');
                usbTab.classList.remove('active');
                startBrowserCamera();
            });
            usbTab.addEventListener('click', () => {
                usbTab.classList.add('active');
                browserTab.classList.remove('active');
                startUsbCamera();
            });
        }

        if (btnCamToggle) {
            btnCamToggle.addEventListener('click', () => {
                if (recognitionInterval || videoStream) {
                    stopCamera();
                } else {
                    if (currentSource === 'browser') startBrowserCamera();
                    else startUsbCamera();
                }
            });
        }

        if (currentSource === 'browser') startBrowserCamera();

        window.addEventListener('resize', resizeOverlay);
    });

})();
