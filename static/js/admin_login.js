<!DOCTYPE html>
<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta name="viewport"
          content="width=device-width, initial-scale=1.0">

    <title>QRESERVE | Administrator Login</title>

    <!-- Bootstrap 5 -->
    <link
        href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/css/bootstrap.min.css"
        rel="stylesheet">

    <!-- Bootstrap Icons -->
    <link
        href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css"
        rel="stylesheet">

    <!-- Custom CSS -->
    <link
        rel="stylesheet"
        href="{{ url_for('static', filename='css/style.css') }}">

</head>


<body>

<!-- =======================================================
     BACKGROUND
======================================================= -->

<div class="background-image"></div>

<div class="overlay"></div>


<!-- =======================================================
     NAVIGATION BAR
======================================================= -->

<nav class="navbar navbar-dark custom-navbar">

    <div class="container-fluid">

        <a class="navbar-brand d-flex align-items-center"
           href="{{ url_for('auth.login') }}">

            <img
                src="{{ url_for('static', filename='images/logo.png') }}"
                class="logo"
                alt="Bulacan State University Logo">

            <div class="ms-3">

                <h6 class="mb-0 fw-bold">
                    BULACAN STATE UNIVERSITY
                </h6>

                <small>
                    BUSTOS CAMPUS
                </small>

            </div>

        </a>

    </div>

</nav>


<!-- =======================================================
     ADMIN LOGIN
======================================================= -->

<div class="container-fluid">

    <div class="row justify-content-center align-items-center login-page">

        <div class="col-12">

            <!-- Title -->

            <h1 class="text-center login-title mb-4">

                ADMINISTRATOR LOGIN

            </h1>


            <!-- Login Card -->

            <div class="card login-card admin-login-card">

                <div class="card-body px-4 py-4">


                    <!-- Admin Icon -->

                    <div class="text-center admin-icon">

                        <i class="bi bi-shield-lock-fill"></i>

                    </div>


                    <!-- Description -->

                    <p class="text-center admin-description">

                        Administrator access only

                    </p>


                    <!-- Error Message -->

                    {% if error %}

                    <div class="alert alert-danger rounded-4 text-center">

                        <i class="bi bi-exclamation-circle me-1"></i>

                        {{ error }}

                    </div>

                    {% endif %}


                    <!-- Admin Login Form -->

                    <form
                        method="POST"
                        action="{{ url_for('auth.admin_login') }}"
                        id="adminLoginForm">


                        <!-- Email -->

                        <div class="mb-3">

                            <label
                                for="email"
                                class="form-label">

                                Administrator Email

                            </label>

                            <input
                                type="email"
                                class="form-control rounded-pill"
                                id="email"
                                name="email"
                                placeholder="Enter administrator email"
                                required>

                        </div>


                        <!-- Password -->

                        <div class="mb-3">

                            <label
                                for="password"
                                class="form-label">

                                Password

                            </label>


                            <div class="input-group">

                                <input
                                    type="password"
                                    class="form-control rounded-start-pill"
                                    id="password"
                                    name="password"
                                    placeholder="Enter your password"
                                    required>


                                <button
                                    class="btn btn-light rounded-end-pill"
                                    type="button"
                                    id="toggleAdminPassword">

                                    <i class="bi bi-eye"></i>

                                </button>

                            </div>

                        </div>


                        <!-- Login Button -->

                        <div class="d-grid mt-4">

                            <button
                                type="submit"
                                class="btn btn-success rounded-pill admin-login-button">

                                <i class="bi bi-box-arrow-in-right me-2"></i>

                                ADMIN LOGIN

                            </button>

                        </div>


                        <!-- Back to Login -->

                        <div class="text-center mt-4">

                            <a
                                href="{{ url_for('auth.login') }}"
                                class="text-decoration-none">

                                <i class="bi bi-arrow-left me-1"></i>

                                Back to Login

                            </a>

                        </div>


                    </form>

                </div>

            </div>

        </div>

    </div>

</div>


<!-- Bootstrap -->

<script
    src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/js/bootstrap.bundle.min.js">
</script>


<!-- Admin Login JS -->

<script
    src="{{ url_for('static', filename='js/admin_login.js') }}">
</script>

</body>

</html>
const adminPassword = document.getElementById("adminPassword");
const toggleAdminPassword = document.getElementById("toggleAdminPassword");

if (toggleAdminPassword) {

    toggleAdminPassword.addEventListener("click", function () {

        const type =
            adminPassword.type === "password"
                ? "text"
                : "password";

        adminPassword.type = type;

        this.innerHTML =
            type === "password"
                ? '<i class="bi bi-eye"></i>'
                : '<i class="bi bi-eye-slash"></i>';

    });

}