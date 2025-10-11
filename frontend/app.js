const API_BASE = "http://localhost:8000/api";

const state = {
  token: localStorage.getItem("ca_token"),
  role: localStorage.getItem("ca_role"),
  user: null,
};

const elements = {
  authSection: document.getElementById("auth-section"),
  loginCard: document.getElementById("login-card"),
  registerCard: document.getElementById("register-card"),
  loginForm: document.getElementById("login-form"),
  registerForm: document.getElementById("register-form"),
  navLogin: document.getElementById("nav-login"),
  navRegister: document.getElementById("nav-register"),
  navLogout: document.getElementById("nav-logout"),
  studentDashboard: document.getElementById("student-dashboard"),
  adminDashboard: document.getElementById("admin-dashboard"),
  toast: document.getElementById("toast"),
  profileForm: document.getElementById("profile-form"),
  refreshProfile: document.getElementById("refresh-profile"),
  preferencesForm: document.getElementById("preferences-form"),
  addPreference: document.getElementById("add-preference"),
  savePreferences: document.getElementById("save-preferences"),
  coursesTable: document.querySelector("#courses-table tbody"),
  adminCoursesTable: document.querySelector("#admin-courses-table tbody"),
  courseForm: document.getElementById("course-form"),
  importCourses: document.getElementById("import-courses"),
  runMatch: document.getElementById("run-match"),
  matchStatus: document.getElementById("match-status"),
  assignmentsTable: document.querySelector("#assignments-table tbody"),
  emailForm: document.getElementById("email-form"),
  emailPreview: document.getElementById("email-preview"),
};

function showToast(message, type = "info") {
  if (!elements.toast) return;
  elements.toast.textContent = message;
  elements.toast.className = `toast show ${type}`;
  setTimeout(() => {
    elements.toast.classList.remove("show");
  }, 3500);
}

function setAuth(token, role) {
  state.token = token;
  state.role = role;
  if (token) {
    localStorage.setItem("ca_token", token);
    if (role) {
      localStorage.setItem("ca_role", role);
    }
  } else {
    localStorage.removeItem("ca_token");
    localStorage.removeItem("ca_role");
  }
  updateNav();
}

function updateNav() {
  const isAuthenticated = Boolean(state.token);
  toggleVisibility(elements.navLogout, isAuthenticated);
  toggleVisibility(elements.navLogin, !isAuthenticated);
  toggleVisibility(elements.navRegister, !isAuthenticated);
}

function toggleVisibility(element, shouldShow) {
  if (!element) return;
  element.classList.toggle("hidden", !shouldShow);
}

function toggleDashboard(role) {
  const showStudent = role === "student";
  const showAdmin = role === "admin";
  toggleVisibility(elements.authSection, false);
  toggleVisibility(elements.studentDashboard, showStudent);
  toggleVisibility(elements.adminDashboard, showAdmin);
}

function showAuthView() {
  toggleVisibility(elements.authSection, true);
  toggleVisibility(elements.studentDashboard, false);
  toggleVisibility(elements.adminDashboard, false);
}

async function apiFetch(path, options = {}) {
  const headers = options.headers ? { ...options.headers } : {};
  if (state.token) {
    headers.Authorization = `Bearer ${state.token}`;
  }
  const config = { ...options, headers };
  if (config.body && !(config.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    config.body = JSON.stringify(config.body);
  }
  const response = await fetch(`${API_BASE}${path}`, config);
  if (!response.ok) {
    const detail = await safeParse(response);
    throw new Error(detail?.detail || detail?.message || "Request failed");
  }
  if (response.status === 204) return null;
  const data = await safeParse(response);
  return data;
}

async function safeParse(response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch (err) {
    return { message: text };
  }
}

async function fetchCurrentUser() {
  if (!state.token) return null;
  try {
    const user = await apiFetch("/auth/me");
    state.user = user;
    setAuth(state.token, user.role);
    return user;
  } catch (error) {
    console.error(error);
    showToast("Session expired. Please sign in again.", "danger");
    setAuth(null, null);
    return null;
  }
}

async function handleLogin(event) {
  event.preventDefault();
  const formData = new FormData();
  formData.append("username", document.getElementById("login-uni").value.trim());
  formData.append("password", document.getElementById("login-password").value);

  try {
    const response = await fetch(`${API_BASE}/auth/token`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      throw new Error("Invalid credentials");
    }
    const data = await response.json();
    setAuth(data.access_token, null);
    await fetchCurrentUser();
    showToast("Logged in successfully", "success");
    await postLoginSetup();
  } catch (error) {
    console.error(error);
    showToast(error.message, "danger");
  }
}

async function handleRegister(event) {
  event.preventDefault();
  const payload = {
    email: document.getElementById("register-email").value.trim(),
    uni: document.getElementById("register-uni").value.trim(),
    password: document.getElementById("register-password").value,
    role: document.getElementById("register-role").value,
  };
  try {
    await apiFetch("/auth/register", {
      method: "POST",
      body: payload,
    });
    showToast("Account created! You can now log in.", "success");
  } catch (error) {
    showToast(error.message, "danger");
  }
}

async function postLoginSetup() {
  if (state.role === "student") {
    await loadStudentDashboard();
  } else if (state.role === "admin") {
    await loadAdminDashboard();
  }
}

async function loadStudentDashboard() {
  toggleDashboard("student");
  await Promise.all([refreshProfile(), loadCourses(elements.coursesTable), loadPreferences()]);
}

async function refreshProfile() {
  try {
    const profile = await apiFetch("/students/me");
    document.getElementById("profile-full-name").value = profile.full_name || "";
    document.getElementById("profile-degree").value = profile.degree_program || "";
    document.getElementById("profile-level").value = profile.level_of_study || "";
    const interestsElement = document.getElementById("profile-interests");
    Array.from(interestsElement.options).forEach((option) => {
      option.selected = profile.interests?.some((interest) => interest === option.value);
    });
    document.getElementById("profile-resume").value = profile.resume_path || "";
    document.getElementById("profile-transcript").value = profile.transcript_path || "";
    document.getElementById("profile-photo").value = profile.photo_url || "";
  } catch (error) {
    console.warn("Profile not available yet", error.message);
  }
}

async function saveProfile(event) {
  event.preventDefault();
  const interestsElement = document.getElementById("profile-interests");
  const selectedInterests = Array.from(interestsElement.selectedOptions).map(
    (option) => option.value
  );
  const payload = {
    full_name: document.getElementById("profile-full-name").value,
    degree_program: document.getElementById("profile-degree").value,
    level_of_study: document.getElementById("profile-level").value || null,
    interests: selectedInterests,
    resume_path: document.getElementById("profile-resume").value,
    transcript_path: document.getElementById("profile-transcript").value,
    photo_url: document.getElementById("profile-photo").value,
  };
  try {
    await apiFetch("/students/me", { method: "PUT", body: payload });
    showToast("Profile updated", "success");
  } catch (error) {
    showToast(error.message, "danger");
  }
}

function addPreferenceRow(pref = {}) {
  const container = elements.preferencesForm;
  const row = document.createElement("div");
  row.className = "grid-two preference-row";
  row.innerHTML = `
    <label>
      <span>Course ID</span>
      <input type="number" min="1" value="${pref.course_id || ""}" class="pref-course" required />
    </label>
    <label>
      <span>Rank</span>
      <input type="number" min="1" value="${pref.rank || ""}" class="pref-rank" required />
    </label>
    <label>
      <span>Track (optional)</span>
      <select class="pref-track">
        <option value="">Auto</option>
        <option value="Financial Engineering & Risk Management">Financial Engineering & Risk Management</option>
        <option value="Machine Learning & Analytics">Machine Learning & Analytics</option>
        <option value="Optimization">Optimization</option>
        <option value="Operations">Operations</option>
        <option value="Stochastic Modeling and Simulation">Stochastic Modeling and Simulation</option>
      </select>
    </label>
    <div class="profile-actions">
      <button type="button" class="ghost-button remove-preference">Remove</button>
    </div>
  `;
  row.querySelector(".pref-track").value = pref.track || "";
  row.querySelector(".remove-preference").addEventListener("click", () => {
    row.remove();
  });
  container.appendChild(row);
}

function clearPreferences() {
  elements.preferencesForm.innerHTML = "";
}

async function savePreferences() {
  const rows = Array.from(document.querySelectorAll(".preference-row"));
  const payload = rows
    .map((row) => {
      const courseId = Number(row.querySelector(".pref-course").value);
      const rank = Number(row.querySelector(".pref-rank").value);
      const track = row.querySelector(".pref-track").value;
      if (!courseId || !rank) return null;
      return {
        course_id: courseId,
        rank,
        track: track || null,
      };
    })
    .filter(Boolean);

  if (!payload.length) {
    showToast("Add at least one preference", "warning");
    return;
  }

  try {
    await apiFetch("/students/preferences", { method: "POST", body: payload });
    showToast("Preferences saved", "success");
  } catch (error) {
    showToast(error.message, "danger");
  }
}

async function loadPreferences() {
  try {
    const preferences = await apiFetch("/students/preferences");
    clearPreferences();
    if (!preferences.length) {
      addPreferenceRow();
      return;
    }
    preferences.forEach((preference) => addPreferenceRow(preference));
  } catch (error) {
    console.warn("Unable to load preferences", error.message);
    clearPreferences();
    addPreferenceRow();
  }
}

async function loadCourses(tableElement) {
  try {
    const courses = await apiFetch("/students/courses");
    tableElement.innerHTML = courses
      .map(
        (course) => `
        <tr>
          <td>${course.code}</td>
          <td>${course.title}</td>
          <td>${course.track || "—"}</td>
          <td>${course.vacancies}</td>
        </tr>
      `
      )
      .join("");
  } catch (error) {
    tableElement.innerHTML = `<tr><td colspan="4">Unable to load courses</td></tr>`;
  }
}

async function loadAdminDashboard() {
  toggleDashboard("admin");
  await Promise.all([loadAdminCourses(), loadAssignments()]);
}

async function loadAdminCourses() {
  try {
    const courses = await apiFetch("/admin/courses");
    elements.adminCoursesTable.innerHTML = courses
      .map(
        (course) => `
        <tr>
          <td>${course.code}</td>
          <td>${course.title}</td>
          <td>${course.track || "—"}</td>
          <td>${course.vacancies}</td>
        </tr>
      `
      )
      .join("");
  } catch (error) {
    elements.adminCoursesTable.innerHTML = `<tr><td colspan="4">${error.message}</td></tr>`;
  }
}

async function handleCourseSubmit(event) {
  event.preventDefault();
  const payload = {
    code: document.getElementById("course-code").value.trim(),
    title: document.getElementById("course-title").value.trim(),
    instructor: document.getElementById("course-instructor").value.trim(),
    instructor_email: document.getElementById("course-instructor-email").value.trim() || null,
    track: document.getElementById("course-track").value || null,
    vacancies: Number(document.getElementById("course-vacancies").value || 0),
    grade_threshold: document.getElementById("course-grade").value.trim() || null,
    similar_courses: document.getElementById("course-similar").value.trim() || null,
  };
  try {
    await apiFetch("/admin/courses", { method: "POST", body: payload });
    event.target.reset();
    showToast("Course saved", "success");
    await loadAdminCourses();
  } catch (error) {
    showToast(error.message, "danger");
  }
}

async function handleImportCourses(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const formData = new FormData();
  formData.append("file", file);
  try {
    await apiFetch("/admin/courses/import", { method: "POST", body: formData });
    showToast("Courses imported", "success");
    await loadAdminCourses();
  } catch (error) {
    showToast(error.message, "danger");
  } finally {
    event.target.value = "";
  }
}

async function runMatching() {
  try {
    const result = await apiFetch("/admin/match", { method: "POST", body: {} });
    elements.matchStatus.textContent = `Assigned ${result.assignments.length} students. Skipped: ${result.skipped_students.length}`;
    await loadAssignments();
  } catch (error) {
    elements.matchStatus.textContent = `Match failed: ${error.message}`;
  }
}

async function loadAssignments() {
  try {
    const assignments = await apiFetch("/admin/assignments");
    elements.assignmentsTable.innerHTML = assignments
      .map(
        (assignment) => `
        <tr>
          <td>${assignment.student_name || "—"}</td>
          <td>${assignment.student_uni || "—"}</td>
          <td>${assignment.course_code} – ${assignment.course_title || ""}</td>
          <td>${assignment.instructor || "—"}</td>
        </tr>
      `
      )
      .join("");
  } catch (error) {
    elements.assignmentsTable.innerHTML = `<tr><td colspan="4">${error.message}</td></tr>`;
  }
}

async function composeEmail(event) {
  event.preventDefault();
  const payload = {
    subject: document.getElementById("email-subject").value,
    message: document.getElementById("email-message").value,
    cc_instructors: document.getElementById("email-cc").checked,
  };
  try {
    const summary = await apiFetch("/admin/communications", { method: "POST", body: payload });
    elements.emailPreview.textContent = JSON.stringify(summary, null, 2);
    showToast("Email draft prepared", "success");
  } catch (error) {
    showToast(error.message, "danger");
  }
}

function logout() {
  setAuth(null, null);
  state.user = null;
  toggleVisibility(elements.authSection, true);
  toggleVisibility(elements.studentDashboard, false);
  toggleVisibility(elements.adminDashboard, false);
}

function initEventListeners() {
  elements.loginForm?.addEventListener("submit", handleLogin);
  elements.registerForm?.addEventListener("submit", handleRegister);
  elements.navLogin?.addEventListener("click", showAuthView);
  elements.navRegister?.addEventListener("click", showAuthView);
  elements.navLogout?.addEventListener("click", logout);
  elements.profileForm?.addEventListener("submit", saveProfile);
  elements.refreshProfile?.addEventListener("click", refreshProfile);
  elements.addPreference?.addEventListener("click", () => addPreferenceRow());
  elements.savePreferences?.addEventListener("click", savePreferences);
  elements.courseForm?.addEventListener("submit", handleCourseSubmit);
  elements.importCourses?.addEventListener("change", handleImportCourses);
  elements.runMatch?.addEventListener("click", runMatching);
  elements.emailForm?.addEventListener("submit", composeEmail);
}

async function bootstrap() {
  updateNav();
  initEventListeners();
  if (state.token) {
    const user = await fetchCurrentUser();
    if (user?.role === "student") {
      await loadStudentDashboard();
    } else if (user?.role === "admin") {
      await loadAdminDashboard();
    }
  }
}

bootstrap();
