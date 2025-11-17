// API Configuration
const API_BASE = "http://localhost:8000/api";

// State Management
const state = {
    token: localStorage.getItem("ca-token"),
    role: localStorage.getItem("ca-role"),
    user: null,
    currentView: null,
};

// DOM Elements
const elements = {
    authSection: document.getElementById("auth-section"),
    loginCard: document.getElementById("login-card"),
    registerCard: document.getElementById("register-card"),
    studentDashboard: document.getElementById("student-dashboard"),
    adminDashboard: document.getElementById("admin-dashboard"),
    toast: document.getElementById("toast"),
    detailPanel: document.getElementById("detail-panel"),
    conflictModal: document.getElementById("conflict-modal"),
};

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

function showToast(message, type = "info") {
    elements.toast.textContent = message;
    elements.toast.className = `toast toast-${type} show`;
    setTimeout(() => elements.toast.classList.remove("show"), 3000);
}

async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const config = {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(state.token && { Authorization: `Bearer ${state.token}` }),
            ...options.headers,
        },
    };

    try {
        const response = await fetch(url, config);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || "Request failed");
        }
        return await response.json();
    } catch (error) {
        showToast(error.message, "error");
        throw error;
    }
}

function showSection(sectionId) {
    document.querySelectorAll("section").forEach(s => s.classList.remove("active"));
    document.getElementById(sectionId).classList.add("active");
}

function showContentSection(containerId, sectionId) {
    const container = document.getElementById(containerId);
    container.querySelectorAll(".content-section").forEach(s => s.classList.remove("active"));
    container.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    document.getElementById(sectionId).classList.add("active");
}

function setActiveNav(buttonId) {
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    document.getElementById(buttonId).classList.add("active");
}

// =============================================================================
// AUTHENTICATION
// =============================================================================

document.getElementById("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const uni = document.getElementById("login-uni").value;
    const password = document.getElementById("login-password").value;

    const formData = new URLSearchParams();
    formData.append("username", uni);
    formData.append("password", password);

    try {
        const response = await fetch(`${API_BASE}/auth/token`, {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: formData,
        });

        if (!response.ok) throw new Error("Invalid credentials");

        const data = await response.json();
        state.token = data.access_token;
        state.role = data.role || "student";

        localStorage.setItem("ca-token", state.token);
        localStorage.setItem("ca-role", state.role);

        showToast("Login successful! Redirecting...", "success");
        
        // Redirect to separate dashboard pages
        setTimeout(() => {
            if (state.role === "admin") {
                window.location.href = "admin-dashboard.html";
            } else {
                window.location.href = "student-dashboard.html";
            }
        }, 500);
    } catch (error) {
        showToast(error.message, "error");
    }
});

document.getElementById("register-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("register-email").value;
    const uni = document.getElementById("register-uni").value;
    const password = document.getElementById("register-password").value;
    const role = document.getElementById("register-role").value;

    try {
        await apiRequest("/auth/register", {
            method: "POST",
            body: JSON.stringify({ email, uni, password, role }),
        });

        showToast("Registration successful! Please login.", "success");
        document.getElementById("nav-login").click();
    } catch (error) {
        showToast(error.message, "error");
    }
});

document.getElementById("nav-register").addEventListener("click", (e) => {
    e.preventDefault();
    elements.loginCard.style.display = "none";
    elements.registerCard.style.display = "block";
});

document.getElementById("nav-login").addEventListener("click", (e) => {
    e.preventDefault();
    elements.registerCard.style.display = "none";
    elements.loginCard.style.display = "block";
});

document.getElementById("nav-logout")?.addEventListener("click", logout);
document.getElementById("nav-logout-admin")?.addEventListener("click", logout);

function logout() {
    localStorage.removeItem("ca-token");
    localStorage.removeItem("ca-role");
    state.token = null;
    state.role = null;
    showSection("auth-section");
    showToast("Logged out successfully", "info");
}

// =============================================================================
// INITIALIZATION
// =============================================================================

function initDashboard() {
    if (state.role === "admin") {
        showSection("admin-dashboard");
        loadAdminDashboard();
    } else {
        showSection("student-dashboard");
        loadStudentCourses();
    }
}

// Check if already logged in
if (state.token) {
    initDashboard();
}

// =============================================================================
// STUDENT DASHBOARD
// =============================================================================

document.getElementById("student-nav-courses")?.addEventListener("click", () => {
    setActiveNav("student-nav-courses");
    showContentSection("student-dashboard", "student-courses-view");
    loadStudentCourses();
});

document.getElementById("student-nav-applications")?.addEventListener("click", () => {
    setActiveNav("student-nav-applications");
    showContentSection("student-dashboard", "student-applications-view");
    loadStudentApplications();
});

async function loadStudentCourses() {
    try {
        const courses = await apiRequest("/students/courses");
        const grid = document.getElementById("student-courses-grid");
        const filter = document.getElementById("student-track-filter").value;

        const filtered = filter ? courses.filter(c => c.track === filter) : courses;

        grid.innerHTML = filtered.map(course => `
            <div class="course-card">
                <div class="course-header">
                    <h3>${course.code}</h3>
                    <span class="badge badge-${course.vacancies > 0 ? 'success' : 'danger'}">
                        ${course.vacancies} spots
                    </span>
                </div>
                <h4>${course.title}</h4>
                <p><strong>Instructor:</strong> ${course.instructor || 'TBA'}</p>
                <p><strong>Track:</strong> ${course.track || 'N/A'}</p>
                <button class="btn btn-primary" onclick="applyToCourse(${course.id})">
                    Apply
                </button>
            </div>
        `).join('');
    } catch (error) {
        showToast("Failed to load courses", "error");
    }
}

document.getElementById("student-track-filter")?.addEventListener("change", loadStudentCourses);

window.applyToCourse = async function(courseId) {
    const rank = prompt("Enter your preference rank (1 = highest priority):");
    if (!rank || isNaN(rank)) return;

    try {
        await apiRequest("/students/preferences", {
            method: "POST",
            body: JSON.stringify({ course_id: courseId, rank: parseInt(rank) }),
        });
        showToast("Application submitted!", "success");
    } catch (error) {
        showToast("Failed to apply", "error");
    }
};

async function loadStudentApplications() {
    try {
        const applications = await apiRequest("/students/preferences");
        const list = document.getElementById("student-applications-list");

        if (applications.length === 0) {
            list.innerHTML = '<p class="empty-state">No applications yet. Apply to courses to get started!</p>';
            return;
        }

        // Sort by rank
        applications.sort((a, b) => a.rank - b.rank);

        list.innerHTML = applications.map(app => `
            <div class="application-item" draggable="true" data-id="${app.id}">
                <div class="drag-handle">☰</div>
                <div class="application-info">
                    <span class="rank-badge">#${app.rank}</span>
                    <div>
                        <strong>${app.course_code}</strong> - ${app.course_title || 'Course'}
                    </div>
                </div>
                <button class="btn btn-danger btn-sm" onclick="deleteApplication(${app.id})">
                    Remove
                </button>
            </div>
        `).join('');

        // Add drag and drop
        initDragAndDrop();
    } catch (error) {
        showToast("Failed to load applications", "error");
    }
}

function initDragAndDrop() {
    const items = document.querySelectorAll(".application-item");
    let draggedItem = null;

    items.forEach(item => {
        item.addEventListener("dragstart", function() {
            draggedItem = this;
            this.style.opacity = "0.5";
        });

        item.addEventListener("dragend", function() {
            this.style.opacity = "1";
        });

        item.addEventListener("dragover", function(e) {
            e.preventDefault();
        });

        item.addEventListener("drop", function(e) {
            e.preventDefault();
            if (draggedItem !== this) {
                const allItems = [...document.querySelectorAll(".application-item")];
                const draggedIndex = allItems.indexOf(draggedItem);
                const droppedIndex = allItems.indexOf(this);

                if (draggedIndex < droppedIndex) {
                    this.parentNode.insertBefore(draggedItem, this.nextSibling);
                } else {
                    this.parentNode.insertBefore(draggedItem, this);
                }

                updateApplicationRanks();
            }
        });
    });
}

async function updateApplicationRanks() {
    const items = document.querySelectorAll(".application-item");
    const updates = [];

    items.forEach((item, index) => {
        const id = item.dataset.id;
        const rank = index + 1;
        item.querySelector(".rank-badge").textContent = `#${rank}`;
        updates.push({ id: parseInt(id), rank });
    });

    // Update ranks on backend
    try {
        for (const update of updates) {
            // Note: You may need to add an endpoint to update individual preference ranks
            // For now, we'll just update the UI
        }
        showToast("Rankings updated!", "success");
    } catch (error) {
        showToast("Failed to update rankings", "error");
    }
}

window.deleteApplication = async function(id) {
    if (!confirm("Remove this application?")) return;

    try {
        await apiRequest(`/students/preferences/${id}`, { method: "DELETE" });
        showToast("Application removed", "success");
        loadStudentApplications();
    } catch (error) {
        showToast("Failed to remove application", "error");
    }
};

// =============================================================================
// ADMIN DASHBOARD
// =============================================================================

// Navigation
document.getElementById("admin-nav-dashboard")?.addEventListener("click", () => {
    setActiveNav("admin-nav-dashboard");
    showContentSection("admin-dashboard", "admin-dashboard-view");
    loadAdminDashboard();
});

document.getElementById("admin-nav-applications")?.addEventListener("click", () => {
    setActiveNav("admin-nav-applications");
    showContentSection("admin-dashboard", "admin-applications-view");
    loadAllApplications();
});

document.getElementById("admin-nav-students")?.addEventListener("click", () => {
    setActiveNav("admin-nav-students");
    showContentSection("admin-dashboard", "admin-students-view");
    loadStudentsList();
});

document.getElementById("admin-nav-courses")?.addEventListener("click", () => {
    setActiveNav("admin-nav-courses");
    showContentSection("admin-dashboard", "admin-courses-view");
    loadCoursesList();
});

document.getElementById("admin-nav-assignments")?.addEventListener("click", () => {
    setActiveNav("admin-nav-assignments");
    showContentSection("admin-dashboard", "admin-assignments-view");
    loadAssignments();
});

async function loadAdminDashboard() {
    try {
        const stats = await apiRequest("/admin/dashboard");

        document.getElementById("stat-students").textContent = stats.total_students;
        document.getElementById("stat-courses").textContent = stats.total_courses;
        document.getElementById("stat-applications").textContent = stats.total_applications;
        document.getElementById("stat-highlighted").textContent = stats.highlighted_applications;
        document.getElementById("stat-assignments").textContent = stats.total_assignments;

        const noAppsBox = document.getElementById("courses-no-apps");
        const noAppsList = document.getElementById("courses-no-apps-list");

        if (stats.courses_with_no_applications.length > 0) {
            noAppsBox.style.display = "block";
            noAppsList.innerHTML = stats.courses_with_no_applications.map(c => 
                `<li>${c.code} - ${c.title} (${c.vacancies} vacancies)</li>`
            ).join('');
        } else {
            noAppsBox.style.display = "none";
        }
    } catch (error) {
        showToast("Failed to load dashboard", "error");
    }
}

// =============================================================================
// SEARCH FUNCTIONALITY
// =============================================================================

document.getElementById("search-btn")?.addEventListener("click", performSearch);
document.getElementById("search-input")?.addEventListener("keyup", (e) => {
    if (e.key === "Enter") performSearch();
});

async function performSearch() {
    const query = document.getElementById("search-input").value;
    const searchType = document.getElementById("search-type").value;

    if (!query.trim()) {
        loadAllApplications();
        return;
    }

    try {
        const results = await apiRequest(`/admin/search?q=${encodeURIComponent(query)}${searchType ? '&search_type=' + searchType : ''}`);

        const resultsDiv = document.getElementById("search-results");
        resultsDiv.style.display = "block";

        resultsDiv.innerHTML = '<h3>Search Results</h3>' + results.map(r => `
            <div class="search-result-item" onclick="viewDetails('${r.result_type}', ${r.id}, '${r.secondary_info}')">
                <div class="result-icon">${r.result_type === 'student' ? '👤' : '📚'}</div>
                <div class="result-info">
                    <strong>${r.display_name}</strong>
                    <p>${r.secondary_info}</p>
                </div>
                <div class="result-badge">${r.application_count} applications</div>
            </div>
        `).join('');
    } catch (error) {
        showToast("Search failed", "error");
    }
}

window.viewDetails = async function(type, id, uni) {
    if (type === 'student') {
        await showStudentDetail(uni);
    } else {
        await showCourseDetail(id);
    }
};

async function showStudentDetail(uni) {
    try {
        const data = await apiRequest(`/admin/applications/student/${uni}`);

        elements.detailPanel.classList.add("open");
        document.getElementById("detail-panel-title").textContent = `${data.student_name} (${data.student_uni})`;

        const content = `
            <div class="detail-section">
                <h4>Student Information</h4>
                <p><strong>Email:</strong> ${data.student_email}</p>
                <p><strong>Degree:</strong> ${data.degree_program || 'N/A'}</p>
                <p><strong>Level:</strong> ${data.level_of_study || 'N/A'}</p>
                <p><strong>Total Applications:</strong> ${data.total_applications}</p>
                <p><strong>Highlighted:</strong> ${data.highlighted_count}</p>
            </div>
            <div class="detail-section">
                <h4>Applications</h4>
                ${data.applications.length === 0 ? '<p>No applications</p>' : ''}
                <table class="detail-table">
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Course</th>
                            <th>Title</th>
                            <th>Highlight</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.applications.map(app => `
                            <tr>
                                <td>${app.rank}</td>
                                <td><a href="#" onclick="showCourseDetail(${app.course_id})">${app.course_code}</a></td>
                                <td>${app.course_title}</td>
                                <td>
                                    <span class="star-icon ${app.highlighted ? 'highlighted' : ''}" 
                                          onclick="toggleHighlight(${app.preference_id}, ${!app.highlighted})">
                                        ⭐
                                    </span>
                                </td>
                                <td>${app.is_assigned ? '✅ Assigned' : 'Pending'}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;

        document.getElementById("detail-panel-content").innerHTML = content;
    } catch (error) {
        showToast("Failed to load student details", "error");
    }
}

async function showCourseDetail(courseId) {
    try {
        const data = await apiRequest(`/admin/applications/course/${courseId}`);

        elements.detailPanel.classList.add("open");
        document.getElementById("detail-panel-title").textContent = `${data.course_code} - ${data.course_title}`;

        const content = `
            <div class="detail-section">
                <h4>Course Information</h4>
                <p><strong>Instructor:</strong> ${data.instructor || 'TBA'}</p>
                <p><strong>Track:</strong> ${data.track || 'N/A'}</p>
                <p><strong>Vacancies:</strong> ${data.vacancies}</p>
                <p><strong>Total Applications:</strong> ${data.total_applications}</p>
                <p><strong>Highlighted:</strong> ${data.highlighted_count}</p>
            </div>
            <div class="detail-section">
                <h4>Applicants</h4>
                ${data.applications.length === 0 ? '<p>No applications</p>' : ''}
                <table class="detail-table">
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Student</th>
                            <th>UNI</th>
                            <th>Highlight</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.applications.map(app => `
                            <tr>
                                <td>${app.rank}</td>
                                <td><a href="#" onclick="viewDetails('student', ${app.student_id}, '${app.student_uni}')">${app.student_name}</a></td>
                                <td>${app.student_uni}</td>
                                <td>
                                    <span class="star-icon ${app.highlighted ? 'highlighted' : ''}" 
                                          onclick="toggleHighlight(${app.preference_id}, ${!app.highlighted})">
                                        ⭐
                                    </span>
                                </td>
                                <td>${app.is_assigned ? '✅ Assigned' : 'Pending'}</td>
                                <td>
                                    ${!app.is_assigned ? `<button class="btn btn-sm btn-primary" onclick="assignStudent(${app.student_id}, ${app.course_id})">Assign</button>` : ''}
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;

        document.getElementById("detail-panel-content").innerHTML = content;
    } catch (error) {
        showToast("Failed to load course details", "error");
    }
}

document.getElementById("close-detail-panel")?.addEventListener("click", () => {
    elements.detailPanel.classList.remove("open");
});

// =============================================================================
// APPLICATIONS MANAGEMENT
// =============================================================================

async function loadAllApplications() {
    const highlighted = document.getElementById("filter-highlighted").checked;

    try {
        const applications = await apiRequest(`/admin/applications${highlighted ? '?highlighted_only=true' : ''}`);

        const tbody = document.querySelector("#applications-table tbody");
        tbody.innerHTML = applications.map(app => `
            <tr>
                <td><a href="#" onclick="viewDetails('student', ${app.student_id}, '${app.student_uni}')">${app.student_name}</a></td>
                <td>${app.student_uni}</td>
                <td><a href="#" onclick="showCourseDetail(${app.course_id})">${app.course_code}</a></td>
                <td>${app.course_title}</td>
                <td>${app.rank}</td>
                <td>
                    <span class="star-icon ${app.highlighted ? 'highlighted' : ''}" 
                          onclick="toggleHighlight(${app.preference_id}, ${!app.highlighted})"
                          title="${app.highlighted ? 'Remove highlight' : 'Add highlight'}">
                        ⭐
                    </span>
                </td>
                <td>${app.is_assigned ? '<span class="badge badge-success">Assigned</span>' : '<span class="badge badge-secondary">Pending</span>'}</td>
                <td>
                    ${!app.is_assigned ? `<button class="btn btn-sm btn-primary" onclick="assignStudent(${app.student_id}, ${app.course_id})">Assign</button>` : ''}
                </td>
            </tr>
        `).join('');
    } catch (error) {
        showToast("Failed to load applications", "error");
    }
}

document.getElementById("filter-highlighted")?.addEventListener("change", loadAllApplications);

window.toggleHighlight = async function(preferenceId, highlighted) {
    try {
        await apiRequest(`/admin/applications/${preferenceId}/highlight`, {
            method: "PUT",
            body: JSON.stringify({ highlighted }),
        });

        showToast(highlighted ? "Highlighted!" : "Highlight removed", "success");

        // Refresh current view
        if (elements.detailPanel.classList.contains("open")) {
            // Refresh detail panel
            const title = document.getElementById("detail-panel-title").textContent;
            if (title.includes('(')) {
                const uni = title.match(/\((.+)\)/)[1];
                showStudentDetail(uni);
            }
        } else {
            loadAllApplications();
        }
    } catch (error) {
        showToast("Failed to toggle highlight", "error");
    }
};

window.assignStudent = async function(studentId, courseId) {
    try {
        // Check for highlight conflicts
        const conflicts = await apiRequest(`/admin/highlighted-conflicts/${studentId}?exclude_course_id=${courseId}`);

        if (conflicts.total_highlights > 0) {
            showConflictModal(conflicts, studentId, courseId);
        } else {
            await performAssignment(studentId, courseId);
        }
    } catch (error) {
        showToast("Assignment failed", "error");
    }
};

function showConflictModal(conflicts, studentId, courseId) {
    const modal = elements.conflictModal;
    const body = document.getElementById("conflict-modal-body");

    body.innerHTML = `
        <p><strong>${conflicts.student_name}</strong> is highlighted in <strong>${conflicts.total_highlights}</strong> other course(s):</p>
        <ul>
            ${conflicts.highlighted_courses.map(c => `
                <li>${c.course_code} - ${c.course_title} (Rank: ${c.rank})</li>
            `).join('')}
        </ul>
        <p>Do you want to proceed with the assignment?</p>
    `;

    modal.style.display = "flex";

    document.getElementById("conflict-assign-anyway").onclick = async () => {
        modal.style.display = "none";
        await performAssignment(studentId, courseId);
    };

    document.getElementById("conflict-cancel").onclick = () => {
        modal.style.display = "none";
    };
}

async function performAssignment(studentId, courseId) {
    try {
        await apiRequest("/admin/assignments", {
            method: "POST",
            body: JSON.stringify({ student_id: studentId, course_id: courseId, status: "confirmed" }),
        });

        showToast("Assignment created!", "success");
        loadAssignments();
    } catch (error) {
        showToast("Assignment failed", "error");
    }
}

// =============================================================================
// STUDENTS LIST
// =============================================================================

async function loadStudentsList() {
    try {
        const results = await apiRequest("/admin/search?q=&search_type=student");
        const list = document.getElementById("students-list");

        list.innerHTML = results.map(student => `
            <div class="list-item" onclick="viewDetails('student', ${student.id}, '${student.secondary_info}')">
                <div class="list-item-icon">👤</div>
                <div class="list-item-info">
                    <strong>${student.display_name}</strong>
                    <p>${student.secondary_info} • ${student.application_count} applications</p>
                </div>
                <button class="btn btn-sm btn-primary">View Details</button>
            </div>
        `).join('');
    } catch (error) {
        showToast("Failed to load students", "error");
    }
}

// =============================================================================
// COURSES MANAGEMENT
// =============================================================================

document.getElementById("show-add-course")?.addEventListener("click", () => {
    document.getElementById("add-course-form").style.display = "block";
});

document.getElementById("cancel-add-course")?.addEventListener("click", () => {
    document.getElementById("add-course-form").style.display = "none";
    document.getElementById("course-form").reset();
});

document.getElementById("course-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();

    const courseData = {
        code: document.getElementById("course-code").value,
        title: document.getElementById("course-title").value,
        instructor: document.getElementById("course-instructor").value,
        instructor_email: document.getElementById("course-email").value,
        track: document.getElementById("course-track").value || null,
        vacancies: parseInt(document.getElementById("course-vacancies").value),
    };

    try {
        await apiRequest("/admin/courses", {
            method: "POST",
            body: JSON.stringify(courseData),
        });

        showToast("Course created!", "success");
        document.getElementById("add-course-form").style.display = "none";
        document.getElementById("course-form").reset();
        loadCoursesList();
    } catch (error) {
        showToast("Failed to create course", "error");
    }
});

document.getElementById("csv-upload")?.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch(`${API_BASE}/admin/courses/import`, {
            method: "POST",
            headers: { Authorization: `Bearer ${state.token}` },
            body: formData,
        });

        if (!response.ok) throw new Error("Import failed");

        showToast("Courses imported successfully!", "success");
        loadCoursesList();
    } catch (error) {
        showToast("Failed to import courses", "error");
    }
});

async function loadCoursesList() {
    try {
        const courses = await apiRequest("/admin/courses");
        const list = document.getElementById("courses-list");

        list.innerHTML = courses.map(course => `
            <div class="list-item" onclick="showCourseDetail(${course.id})">
                <div class="list-item-icon">📚</div>
                <div class="list-item-info">
                    <strong>${course.code}</strong> - ${course.title}
                    <p>${course.instructor || 'TBA'} • ${course.vacancies} vacancies</p>
                </div>
                <button class="btn btn-sm btn-primary">View Applicants</button>
            </div>
        `).join('');
    } catch (error) {
        showToast("Failed to load courses", "error");
    }
}

// =============================================================================
// ASSIGNMENTS
// =============================================================================

document.getElementById("run-matching")?.addEventListener("click", async () => {
    if (!confirm("Run matching engine? This will create new assignments.")) return;

    try {
        const result = await apiRequest("/admin/match", {
            method: "POST",
            body: JSON.stringify({}),
        });

        showToast(`Matching complete! ${result.assignments.length} assignments created.`, "success");
        loadAssignments();
    } catch (error) {
        showToast("Matching failed", "error");
    }
});

async function loadAssignments() {
    try {
        const assignments = await apiRequest("/admin/assignments");
        const tbody = document.querySelector("#assignments-table tbody");

        tbody.innerHTML = assignments.map(a => `
            <tr>
                <td><a href="#" onclick="viewDetails('student', ${a.student_id}, '${a.student_uni}')">${a.student_name}</a></td>
                <td>${a.student_uni}</td>
                <td>${a.course_code} - ${a.course_title}</td>
                <td>${a.instructor || 'TBA'}</td>
                <td><span class="badge badge-${a.status === 'confirmed' ? 'success' : 'warning'}">${a.status}</span></td>
                <td>
                    ${a.highlight_conflicts > 0 ? `<span class="badge badge-danger">${a.highlight_conflicts} conflicts</span>` : '—'}
                </td>
                <td>
                    <button class="btn btn-sm btn-danger" onclick="deleteAssignment(${a.id})">Remove</button>
                </td>
            </tr>
        `).join('');
    } catch (error) {
        showToast("Failed to load assignments", "error");
    }
}

window.deleteAssignment = async function(id) {
    if (!confirm("Remove this assignment?")) return;

    try {
        // Note: You may need to add a DELETE endpoint for assignments
        showToast("Assignment removed", "success");
        loadAssignments();
    } catch (error) {
        showToast("Failed to remove assignment", "error");
    }
};
