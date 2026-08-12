/*
=========================================================
QRESERVE
Online Queue & Monitoring System
Bulacan State University - Bustos Campus

Login JavaScript
=========================================================
*/

document.addEventListener("DOMContentLoaded", () => {

    // ===========================================
    // Elements
    // ===========================================

    const loginForm = document.getElementById("loginForm");
    const email = document.getElementById("email");
    const password = document.getElementById("password");

    const loginBtn = document.getElementById("loginBtn");
    const spinner = document.getElementById("spinner");

    const togglePassword = document.getElementById("togglePassword");

    const confirmPassword = document.getElementById("confirmPassword");
const toggleConfirmPassword = document.getElementById("toggleConfirmPassword");

    const alertBox = document.getElementById("alertBox");

    // ===========================================
    // Show Bootstrap Alert
    // ===========================================

    function showAlert(message, type = "danger") {

        alertBox.innerHTML = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">

                ${message}

                <button
                    type="button"
                    class="btn-close"
                    data-bs-dismiss="alert">
                </button>

            </div>
        `;

    }

    // ===========================================
    // Toggle Password Visibility
    // ===========================================

    togglePassword.addEventListener("click", () => {

        if (password.type === "password") {

            password.type = "text";

            togglePassword.innerHTML =
                '<i class="bi bi-eye-slash"></i>';

        } else {

            password.type = "password";

            togglePassword.innerHTML =
                '<i class="bi bi-eye"></i>';

        }

    });

// ===========================================
// Toggle Confirm Password Visibility
// ===========================================

if (toggleConfirmPassword && confirmPassword) {

    toggleConfirmPassword.addEventListener("click", () => {

        if (confirmPassword.type === "password") {

            confirmPassword.type = "text";

            toggleConfirmPassword.innerHTML =
                '<i class="bi bi-eye-slash"></i>';

        } else {

            confirmPassword.type = "password";

            toggleConfirmPassword.innerHTML =
                '<i class="bi bi-eye"></i>';

        }

    });

}

    // ===========================================
    // Login Submit
    // ===========================================

    loginForm.addEventListener("submit", function (event) {

        event.preventDefault();

        alertBox.innerHTML = "";

        // -------------------------
        // Validation
        // -------------------------

        if (email.value.trim() === "") {

            showAlert("Please enter your email.");

            email.focus();

            return;

        }

        if (password.value.trim() === "") {

            showAlert("Please enter your password.");

            password.focus();

            return;

        }

        // -------------------------
        // Loading
        // -------------------------

        spinner.classList.remove("d-none");

        loginBtn.disabled = true;

        // -------------------------
        // AJAX Ready
        // -------------------------

        fetch("/", {

            method: "POST",

            headers: {

                "Content-Type": "application/json"

            },

            body: JSON.stringify({

                email: email.value,

                password: password.value

            })

        })

        .then(response => {

            // Temporary success until backend is connected

            return response.text();

        })

        .then(data => {

            spinner.classList.add("d-none");

            loginBtn.disabled = false;

            // Temporary message

            showAlert(
                "Backend connection coming in the next step.",
                "success"
            );

            console.log(data);

        })

        .catch(error => {

            spinner.classList.add("d-none");

            loginBtn.disabled = false;

            showAlert("Unable to connect to the server.");

            console.error(error);

        });

    });

});