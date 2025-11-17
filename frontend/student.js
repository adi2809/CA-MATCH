// API Configuration
const API_BASE = "http://localhost:8000/api";
const token = localStorage.getItem("ca-token");
const role = localStorage.getItem("ca-role");

// Check authentication
if (!token || role !== "student") {
    window.location.href = "index.html";
}

// Toast notification
function showToast(message, type = "info") {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.className = `toast toast-${type} show`;
    setTimeout(() => toast.classList.remove("show"), 3000);
}

// API Request helper
async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const config = {
        ...options,
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
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

// Navigation
document.getElementById("student-nav-courses").addEventListener("click", () => {
    setActiveNav("student-nav-courses");
    showContentSection("student-courses-view");
    loadStudentCourses();
});

document.getElementById("student-nav-applications").addEventListener("click", () => {
    setActiveNav("student-nav-applications");
    showContentSection("student-applications-view");
    loadStudentApplications();
});

document.getElementById("nav-logout").addEventListener("click", () => {
    localStorage.removeItem("ca-token");
    localStorage.removeItem("ca-role");
    window.location.href = "index.html";
});

function setActiveNav(buttonId) {
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    document.getElementById(buttonId).classList.add("active");
}

function showContentSection(sectionId) {
    document.querySelectorAll(".content-section").forEach(s => s.classList.remove("active"));
    document.getElementById(sectionId).classList.add("active");
}

// Load Courses
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

document.getElementById("student-track-filter").addEventListener("change", loadStudentCourses);

// Apply to Course
window.applyToCourse = async function(courseId) {
    const rankInput = prompt("Enter your preference rank (1 = highest priority):");
    
    if (!rankInput) return; // User cancelled
    
    const rank = parseInt(rankInput);
    if (isNaN(rank) || rank < 1) {
        showToast("Please enter a valid rank number (1 or higher)", "error");
        return;
    }

    try {
        // Simple single preference submission
        await apiRequest("/students/preferences", {
            method: "POST",
            body: JSON.stringify([{
                course_id: courseId,
                rank: rank
            }]),
        });
        
        showToast("Application submitted successfully!", "success");
        
        // Refresh the applications view
        setTimeout(() => {
            showContentSection("student-applications-view");
            setActiveNav("student-nav-applications");
            loadStudentApplications();
        }, 500);
        
    } catch (error) {
        console.error("Application error:", error);
        showToast("Failed to apply. Please try again.", "error");
    }
};


// Load Applications
async function loadStudentApplications() {
    try {
        const applications = await apiRequest("/students/preferences");
        const list = document.getElementById("student-applications-list");

        if (applications.length === 0) {
            list.innerHTML = '<p class="empty-state">No applications yet. Apply to courses to get started!</p>';
            return;
        }

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

        initDragAndDrop();
    } catch (error) {
        showToast("Failed to load applications", "error");
    }
}

// Drag and Drop
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
    items.forEach((item, index) => {
        const rank = index + 1;
        item.querySelector(".rank-badge").textContent = `#${rank}`;
    });
    showToast("Rankings updated!", "success");
}

// Delete Application
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

// Initial Load
loadStudentCourses();
