/**
 * AegisFace - Attendance Logs & Export Controller
 */

(function() {
    let currentPage = 1;
    const pageSize = 20;
    let totalRecords = 0;

    const tableBody = document.getElementById('attendance-table-body');
    const paginationInfo = document.getElementById('pagination-info');
    const currentPageNum = document.getElementById('current-page-num');
    const btnPrev = document.getElementById('btn-prev-page');
    const btnNext = document.getElementById('btn-next-page');

    const searchInput = document.getElementById('filter-search');
    const startDateInput = document.getElementById('filter-start-date');
    const endDateInput = document.getElementById('filter-end-date');
    const deptSelect = document.getElementById('filter-department');
    const punchTypeSelect = document.getElementById('filter-punch-type');
    const btnReset = document.getElementById('btn-reset-filters');
    const btnExcel = document.getElementById('btn-export-excel');
    const btnCsv = document.getElementById('btn-export-csv');

    function getFilterParams() {
        const params = new URLSearchParams();
        if (searchInput && searchInput.value.trim()) params.append('user_id', searchInput.value.trim());
        if (startDateInput && startDateInput.value) params.append('start_date', startDateInput.value);
        if (endDateInput && endDateInput.value) params.append('end_date', endDateInput.value);
        if (deptSelect && deptSelect.value) params.append('department', deptSelect.value);
        if (punchTypeSelect && punchTypeSelect.value) params.append('punch_type', punchTypeSelect.value);
        return params;
    }

    window.fetchAttendanceLogs = async function(page = 1) {
        currentPage = page;
        const params = getFilterParams();
        params.append('limit', pageSize);
        params.append('offset', (page - 1) * pageSize);

        if (!tableBody) return;
        tableBody.innerHTML = `
            <tr>
                <td colspan="9" style="text-align: center; padding: 40px; color: var(--text-muted);">
                    <i class="fa-solid fa-circle-notch fa-spin fa-2x"></i>
                    <p style="margin-top: 10px;">Loading attendance records...</p>
                </td>
            </tr>
        `;

        try {
            const res = await fetch(`/api/attendance?${params.toString()}`);
            if (!res.ok) throw new Error("Failed to fetch logs");

            const data = await res.json();
            totalRecords = data.total;
            renderTable(data.logs);
            updatePagination();
            populateDepartments(data.logs);

        } catch (err) {
            console.error("Fetch attendance error:", err);
            tableBody.innerHTML = `
                <tr>
                    <td colspan="9" style="text-align: center; padding: 40px; color: var(--rose);">
                        <i class="fa-solid fa-triangle-exclamation fa-2x"></i>
                        <p style="margin-top: 10px;">Error loading records. Please retry.</p>
                    </td>
                </tr>
            `;
        }
    };

    function renderTable(logs) {
        if (!logs || logs.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="9" style="text-align: center; padding: 40px; color: var(--text-muted);">
                        <i class="fa-solid fa-clipboard-question fa-2x"></i>
                        <p style="margin-top: 10px;">No attendance records found matching filters.</p>
                    </td>
                </tr>
            `;
            return;
        }

        let html = '';
        logs.forEach(log => {
            const statusClass = (log.status || 'NORMAL').toLowerCase().replace('_', '');
            const typeClass = log.punch_type === 'CHECK_IN' ? 'ontime' : 'normal';
            const typeLabel = log.punch_type === 'CHECK_IN' ? 'Check-In' : 'Check-Out';
            const confPct = Math.round(log.confidence * 100);

            const snapshotHtml = log.snapshot_path
                ? `<img src="${log.snapshot_path}" class="snap-thumb" alt="Audit Snapshot" onclick="window.openModal('${log.snapshot_path}', '<strong>${log.name}</strong> • ${log.date} ${log.time} • ${log.status}')">`
                : `<span style="color:var(--text-muted); font-size:11px;">Auto Log</span>`;

            html += `
                <tr>
                    <td style="font-family: var(--font-mono); color: var(--text-muted);">${log.id}</td>
                    <td>
                        <div class="table-member-cell">
                            <div class="punch-avatar-fallback" style="width:32px; height:32px; font-size:12px;">${log.name[0]}</div>
                            <div class="table-member-info">
                                <h5>${log.name}</h5>
                                <span>${log.user_id}</span>
                            </div>
                        </div>
                    </td>
                    <td><span style="color: var(--text-secondary);">${log.department}</span></td>
                    <td style="font-family: var(--font-mono);">${log.date}</td>
                    <td style="font-family: var(--font-mono); font-weight:600; color: #fff;">${log.time}</td>
                    <td><span class="status-pill ${typeClass}">${typeLabel}</span></td>
                    <td><span class="status-pill ${statusClass}">${log.status.replace('_', ' ')}</span></td>
                    <td>
                        <span style="font-family: var(--font-mono); color: var(--cyan); font-weight:600;">
                            ${confPct}%
                        </span>
                    </td>
                    <td>${snapshotHtml}</td>
                </tr>
            `;
        });

        tableBody.innerHTML = html;
    }

    function updatePagination() {
        const totalPages = Math.ceil(totalRecords / pageSize) || 1;
        if (currentPageNum) currentPageNum.textContent = `${currentPage} / ${totalPages}`;
        if (paginationInfo) {
            const start = totalRecords === 0 ? 0 : (currentPage - 1) * pageSize + 1;
            const end = Math.min(currentPage * pageSize, totalRecords);
            paginationInfo.textContent = `Showing ${start} to ${end} of ${totalRecords} entries`;
        }

        if (btnPrev) btnPrev.disabled = currentPage <= 1;
        if (btnNext) btnNext.disabled = currentPage >= totalPages;
    }

    function populateDepartments(logs) {
        if (!deptSelect || deptSelect.children.length > 1) return;
        const depts = new Set();
        logs.forEach(l => { if (l.department) depts.add(l.department); });
        depts.forEach(d => {
            const opt = document.createElement('option');
            opt.value = d;
            opt.textContent = d;
            deptSelect.appendChild(opt);
        });
    }

    function downloadExport(format) {
        const params = getFilterParams();
        params.append('format', format);
        window.location.href = `/api/attendance/export?${params.toString()}`;
        window.showToast("Report Export", `Preparing ${format.toUpperCase()} attendance download...`);
    }

    document.addEventListener('DOMContentLoaded', () => {
        // Debounced search
        let searchTimeout;
        if (searchInput) {
            searchInput.addEventListener('input', () => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => window.fetchAttendanceLogs(1), 350);
            });
        }

        [startDateInput, endDateInput, deptSelect, punchTypeSelect].forEach(el => {
            if (el) el.addEventListener('change', () => window.fetchAttendanceLogs(1));
        });

        if (btnReset) {
            btnReset.addEventListener('click', () => {
                if (searchInput) searchInput.value = '';
                if (startDateInput) startDateInput.value = '';
                if (endDateInput) endDateInput.value = '';
                if (deptSelect) deptSelect.value = '';
                if (punchTypeSelect) punchTypeSelect.value = '';
                window.fetchAttendanceLogs(1);
            });
        }

        if (btnPrev) btnPrev.addEventListener('click', () => { if (currentPage > 1) window.fetchAttendanceLogs(currentPage - 1); });
        if (btnNext) btnNext.addEventListener('click', () => { window.fetchAttendanceLogs(currentPage + 1); });

        if (btnExcel) btnExcel.addEventListener('click', () => downloadExport('excel'));
        if (btnCsv) btnCsv.addEventListener('click', () => downloadExport('csv'));
    });
})();
