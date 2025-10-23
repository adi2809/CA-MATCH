// API Configuration
const API_BASE = "http://localhost:8000/api";

// Toast notification function
function showToast(message, type = "info") {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.className = `toast toast-${type} show`;
    setTimeout(() => toast.classList.remove("show"), 3000);
}

// Login Form Handler
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

        // Store token and role in localStorage
        localStorage.setItem("ca-token", data.access_token);
        localStorage.setItem("ca-role", data.role || "student");

        showToast("Login successful! Redirecting...", "success");

        // Redirect to appropriate dashboard
        setTimeout(() => {
            if (data.role === "admin") {
                window.location.href = "admin-dashboard.html";
            } else {
                window.location.href = "student-dashboard.html";
            }
        }, 500);

    } catch (error) {
        showToast(error.message, "error");
    }
});

// Register Form Handler
document.getElementById("register-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("register-email").value;
    const uni = document.getElementById("register-uni").value;
    const password = document.getElementById("register-password").value;
    const role = document.getElementById("register-role").value;

    try {
        const response = await fetch(`${API_BASE}/auth/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, uni, password, role }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || "Registration failed");
        }

        showToast("Registration successful! Please login.", "success");
        document.getElementById("nav-login").click();
    } catch (error) {
        showToast(error.message, "error");
    }
});

// Toggle between login and register
document.getElementById("nav-register").addEventListener("click", (e) => {
    e.preventDefault();
    document.getElementById("login-card").style.display = "none";
    document.getElementById("register-card").style.display = "block";
});

document.getElementById("nav-login").addEventListener("click", (e) => {
    e.preventDefault();
    document.getElementById("register-card").style.display = "none";
    document.getElementById("login-card").style.display = "block";
});

// Check if already logged in
const token = localStorage.getItem("ca-token");
const role = localStorage.getItem("ca-role");

if (token && role) {
    // Already logged in, redirect to dashboard
    if (role === "admin") {
        window.location.href = "admin-dashboard.html";
    } else {
        window.location.href = "student-dashboard.html";
    }
}
