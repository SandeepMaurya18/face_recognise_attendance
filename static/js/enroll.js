/**
 * AegisFace - Member Enrollment Controller
 */

(function() {
    let enrollStream = null;
    let capturedPhotoBase64 = null;
    let selectedFile = null;

    const enrollVideo = document.getElementById('enroll-video');
    const enrollCanvas = document.getElementById('enroll-canvas');
    const enrollPreview = document.getElementById('enroll-preview-img');
    const ovalGuide = document.querySelector('.enroll-oval-guide');
    const btnSnap = document.getElementById('btn-snap-enroll');
    const btnRetake = document.getElementById('btn-retake-enroll');
    const fileInput = document.getElementById('enroll-file-input');
    const enrollForm = document.getElementById('enroll-form');
    const statusBanner = document.getElementById('enroll-status-banner');
    const statusText = document.getElementById('enroll-status-text');

    async function initEnrollCamera() {
        if (enrollStream) return;
        try {
            enrollStream = await navigator.mediaDevices.getUserMedia({
                video: { width: 640, height: 480, facingMode: 'user' },
                audio: false
            });
            if (enrollVideo) {
                enrollVideo.srcObject = enrollStream;
                enrollVideo.style.display = 'block';
            }
            if (enrollPreview) enrollPreview.style.display = 'none';
            if (ovalGuide) ovalGuide.style.display = 'flex';
        } catch (e) {
            console.warn("Enroll camera not started:", e);
            if (window.showToast) {
                window.showToast("Camera Permission Needed", "Please allow camera access in browser to capture enrollment photo.", "warning");
            }
        }
    }

    function snapPhoto() {
        if (!enrollVideo || !enrollStream) {
            initEnrollCamera();
            return;
        }

        const w = enrollVideo.videoWidth || 640;
        const h = enrollVideo.videoHeight || 480;

        enrollCanvas.width = w;
        enrollCanvas.height = h;
        const ctx = enrollCanvas.getContext('2d');
        // Mirror the snap to match screen preview
        ctx.translate(w, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(enrollVideo, 0, 0, w, h);

        capturedPhotoBase64 = enrollCanvas.toDataURL('image/jpeg', 0.9);
        selectedFile = null;

        // Show preview
        if (enrollPreview) {
            enrollPreview.src = capturedPhotoBase64;
            enrollPreview.style.display = 'block';
        }
        if (enrollVideo) enrollVideo.style.display = 'none';
        if (ovalGuide) ovalGuide.style.display = 'none';

        if (btnSnap) btnSnap.style.display = 'none';
        if (btnRetake) btnRetake.style.display = 'inline-flex';

        window.playSound('click');
        window.showToast("Face Captured", "Photo ready for enrollment. Fill details to register.");
    }

    function retakePhoto() {
        capturedPhotoBase64 = null;
        selectedFile = null;
        if (fileInput) fileInput.value = '';

        if (enrollPreview) enrollPreview.style.display = 'none';
        if (enrollVideo) enrollVideo.style.display = 'block';
        if (ovalGuide) ovalGuide.style.display = 'flex';

        if (btnSnap) btnSnap.style.display = 'inline-flex';
        if (btnRetake) btnRetake.style.display = 'none';
    }

    function handleFileSelected(e) {
        const file = e.target.files[0];
        if (!file) return;

        selectedFile = file;
        capturedPhotoBase64 = null;

        const reader = new FileReader();
        reader.onload = (event) => {
            if (enrollPreview) {
                enrollPreview.src = event.target.result;
                enrollPreview.style.display = 'block';
            }
            if (enrollVideo) enrollVideo.style.display = 'none';
            if (ovalGuide) ovalGuide.style.display = 'none';

            if (btnSnap) btnSnap.style.display = 'none';
            if (btnRetake) btnRetake.style.display = 'inline-flex';

            window.showToast("Image Loaded", "Uploaded file selected for biometric enrollment.");
        };
        reader.readAsDataURL(file);
    }

    async function handleEnrollSubmit(e) {
        e.preventDefault();

        if (!capturedPhotoBase64 && !selectedFile) {
            window.showToast("Photo Required", "Please capture a photo or upload an image first.", "warning");
            return;
        }

        const userId = document.getElementById('enroll-user-id').value.trim();
        const name = document.getElementById('enroll-name').value.trim();
        const dept = document.getElementById('enroll-department').value.trim();
        const role = document.getElementById('enroll-role').value.trim();
        const email = document.getElementById('enroll-email').value.trim();
        const phone = document.getElementById('enroll-phone').value.trim();

        const submitBtn = document.getElementById('btn-submit-enroll');
        const originalBtnHtml = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Extracting Biometric Embeddings...';

        const formData = new FormData();
        formData.append('user_id', userId);
        formData.append('name', name);
        formData.append('department', dept);
        formData.append('role', role || 'Staff');
        if (email) formData.append('email', email);
        if (phone) formData.append('phone', phone);

        if (selectedFile) {
            formData.append('photo', selectedFile);
        } else if (capturedPhotoBase64) {
            formData.append('photo_base64', capturedPhotoBase64);
        }

        try {
            const res = await fetch('/api/users/enroll', {
                method: 'POST',
                body: formData
            });

            const contentType = res.headers.get('content-type') || '';
            const data = contentType.includes('application/json')
                ? await res.json()
                : { message: `Server returned HTTP ${res.status}.` };

            if (res.ok && data.success) {
                window.playSound('success');
                window.showToast("Enrollment Complete!", data.message, "success");

                if (statusBanner && statusText) {
                    statusText.textContent = `User '${name}' (${userId}) enrolled with 128D deep vector.`;
                    statusBanner.style.display = 'flex';
                }

                // Reset form
                enrollForm.reset();
                retakePhoto();

                // Switch to directory after short delay
                setTimeout(() => {
                    if (window.switchTab) window.switchTab('users');
                }, 1400);

            } else {
                window.playSound('alert');
                window.showToast("Enrollment Failed", data.message || "Face not detected. Ensure face is centered and lit.", "danger");
            }
        } catch (err) {
            console.error("Enrollment error:", err);
            window.showToast("Enrollment Error", err.message || "Could not complete enrollment. Please check server.", "danger");
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnHtml;
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        if (btnSnap) btnSnap.addEventListener('click', snapPhoto);
        if (btnRetake) btnRetake.addEventListener('click', retakePhoto);
        if (fileInput) fileInput.addEventListener('change', handleFileSelected);
        if (enrollForm) enrollForm.addEventListener('submit', handleEnrollSubmit);

        // Auto-start camera when navigating to enroll tab
        const enrollTabBtn = document.querySelector('.nav-item[data-tab="enroll"]');
        if (enrollTabBtn) {
            enrollTabBtn.addEventListener('click', initEnrollCamera);
        }
    });
})();
