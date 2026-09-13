(function () {
    function escapeHtml(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function statusModifier(status) {
        if (status === "Processing") return "status-processing";
        if (status === "Ready for pickup") return "status-pickup";
        return "status-completed";
    }

    function statusTextClass(status) {
        if (status === "Processing") return "is-processing";
        if (status === "Ready for pickup") return "is-pickup";
        return "is-completed";
    }

    function isOngoing(status) {
        return status === "Processing" || status === "Ready for pickup";
    }

    window.QReserveApp = {
        userType: document.body.getAttribute("data-qreserve-user") || "student",
        selectedService: "Registrar",
        selectedDoc: "True Copy Certificate of Registration",
        selectedPrice: 100,
        cachedRequests: [],

        fetchRequests: function (callback) {
            var self = this;
            fetch("/api/requests", { credentials: "same-origin" })
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    if (data.success) {
                        self.cachedRequests = data.requests || [];
                    }
                    if (callback) callback();
                })
                .catch(function (err) {
                    console.error("API Error:", err);
                    if (callback) callback();
                });
        },

        getActiveRequest: function () {
            return this.cachedRequests.find(function (r) {
                return isOngoing(r.status);
            });
        },

        selectCard: function (cardEl, serviceName, docName, price) {
            var grid = cardEl.closest(".doc-cards-grid");
            if (grid) {
                grid.querySelectorAll(".doc-card").forEach(function (c) {
                    c.classList.remove("selected");
                });
            }
            cardEl.classList.add("selected");
            this.selectedService = serviceName;
            this.selectedDoc = docName;
            this.selectedPrice = price;
        },

        documentPickerHtml: function () {
            var isStudent = this.userType === "student";
            var gradNote = isStudent
                ? '<div class="doc-card-note">ONLY APPLICABLE FOR GRADUATES</div>'
                : "";

            return (
                '<div class="requests-page-title">Select a service &amp; document</div>' +
                '<div class="doc-cards-grid">' +
                    '<div class="doc-card" onclick="QReserveApp.selectCard(this, \'Registrar\', \'Transcript of Records\', 100)">' +
                        '<div class="doc-card-name">Transcript of Records</div>' +
                        '<div class="doc-card-note">Registrar</div>' +
                        gradNote +
                        '<div class="doc-card-time">Process within 3–5 days &bull; ₱100</div>' +
                    "</div>" +
                    '<div class="doc-card" onclick="QReserveApp.selectCard(this, \'Registrar\', \'True Copy Report of Grades\', 100)">' +
                        '<div class="doc-card-name">True Copy Report of Grades</div>' +
                        '<div class="doc-card-note">Registrar</div>' +
                        '<div class="doc-card-time">Processing within 3–5 days &bull; ₱100</div>' +
                    "</div>" +
                    '<div class="doc-card" onclick="QReserveApp.selectCard(this, \'Registrar\', \'True Copy Certificate of Registration\', 100)">' +
                        '<div class="doc-card-name">True Copy Certificate of Registration</div>' +
                        '<div class="doc-card-note">Registrar</div>' +
                        '<div class="doc-card-time">Processing within 3–5 days &bull; ₱100</div>' +
                    "</div>" +
                    '<div class="doc-card" onclick="QReserveApp.selectCard(this, \'Registrar\', \'Good Moral\', 100)">' +
                        '<div class="doc-card-name">Good Moral</div>' +
                        '<div class="doc-card-note">Registrar</div>' +
                        '<div class="doc-card-time">Processing within 1 day &bull; ₱100</div>' +
                    "</div>" +
                    '<div class="doc-card" onclick="QReserveApp.selectCard(this, \'Cashier\', \'Tuition Payment\', 0)">' +
                        '<div class="doc-card-name">Tuition Payment</div>' +
                        '<div class="doc-card-note">Cashier</div>' +
                        '<div class="doc-card-time">Payment / Assessment</div>' +
                    "</div>" +
                    '<div class="doc-card" onclick="QReserveApp.selectCard(this, \'Cashier\', \'Graduation Fee\', 0)">' +
                        '<div class="doc-card-name">Graduation Fee</div>' +
                        '<div class="doc-card-note">Cashier</div>' +
                        '<div class="doc-card-time">Payment / Assessment</div>' +
                    "</div>" +
                    '<div class="doc-card" onclick="QReserveApp.selectCard(this, \'Cashier\', \'Assessment Validation\', 0)">' +
                        '<div class="doc-card-name">Assessment Validation</div>' +
                        '<div class="doc-card-note">Cashier</div>' +
                        '<div class="doc-card-time">Payment / Assessment</div>' +
                    "</div>" +
                    '<div class="doc-card" onclick="QReserveApp.selectCard(this, \'Cashier\', \'Others\', 0)">' +
                        '<div class="doc-card-name">Others</div>' +
                        '<div class="doc-card-note">Cashier</div>' +
                        '<div class="doc-card-time">Customized Request</div>' +
                    "</div>" +
                "</div>" +
                '<div class="request-now-wrap">' +
                    '<button class="btn-request-now" type="button" onclick="QReserveApp.submitRequest()">' +
                        '<i class="bi bi-check-circle"></i> Request now' +
                    "</button>" +
                "</div>"
            );
        },

        submitRequest: function () {
            var active = this.getActiveRequest();
            if (active) {
                alert("You currently have an active request (" + active.queueNum + "). Please complete or cancel it before requesting another.");
                return;
            }

            var docName = this.selectedDoc || "True Copy Certificate of Registration";
            var service = this.selectedService || "Registrar";
            var self = this;

            fetch("/api/request/create", {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ doc_name: docName, service: service })
            })
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    if (data.success) {
                        self.fetchRequests(function () {
                            self.renderAll();
                            if (self.userType === "student" && window.QReserve && QReserve.switchTab) {
                                QReserve.switchTab("my-queue");
                            } else if (window.QReserve && QReserve.switchTab) {
                                QReserve.switchTab("my-requests");
                            }
                        });
                    }
                })
                .catch(function (err) {
                    alert("Error creating request: " + err);
                });
        },

        cancelActive: function (dbId) {
            if (!confirm("Are you sure you want to cancel your active request?")) return;
            var self = this;
            if (!dbId) return;

            fetch("/api/request/" + dbId + "/cancel", {
                method: "POST",
                credentials: "same-origin"
            })
                .then(function (res) { return res.json(); })
                .then(function () {
                    self.fetchRequests(function () { self.renderAll(); });
                });
        },

        completeActive: function (dbId) {
            var self = this;
            if (!dbId) return;

            fetch("/api/request/" + dbId + "/complete", {
                method: "POST",
                credentials: "same-origin"
            })
                .then(function (res) { return res.json(); })
                .then(function () {
                    self.fetchRequests(function () { self.renderAll(); });
                });
        },

        renderAll: function () {
            this.renderMyQueue();
            this.renderMyRequests();
            this.renderQueueHistory();
            this.updateDashboardQueueCard();
        },

        updateDashboardQueueCard: function () {
            var numDisplay = document.querySelector("#tab-dashboard .queue-number-display");
            var fieldValues = document.querySelectorAll("#tab-dashboard .queue-field-value");
            var counterVal = fieldValues[0];
            var waitVal = document.querySelector("#tab-dashboard .wait-time-value");
            var serviceVal = fieldValues[1];
            var reqDocVal = fieldValues[2];
            var active = this.userType === "guest" ? null : this.getActiveRequest();

            if (active) {
                if (numDisplay) {
                    numDisplay.innerHTML = '<span style="font-size:24px;font-weight:900;color:#1e293b;letter-spacing:1px;">Queue ' +
                        escapeHtml(active.queueNum) + "</span>";
                }
                if (counterVal) counterVal.textContent = active.counter;
                if (waitVal) waitVal.textContent = active.waitTime;
                if (serviceVal) serviceVal.textContent = active.service;
                if (reqDocVal) reqDocVal.textContent = active.docName;
            } else {
                if (numDisplay) {
                    numDisplay.innerHTML = '<span class="dash"></span><span class="dash"></span><span class="dash"></span><span class="dash"></span><span class="dash"></span>';
                }
                if (counterVal) counterVal.textContent = "——";
                if (waitVal) waitVal.textContent = "0 minutes";
                if (serviceVal) serviceVal.textContent = "No document requested";
                if (reqDocVal) reqDocVal.textContent = "No document requested";
            }
        },

        renderMyQueue: function () {
            var container = document.getElementById("myQueueViewContainer");
            if (!container) return;

            if (this.userType === "guest") {
                container.innerHTML =
                    '<div class="queue-empty-state">' +
                        '<i class="bi bi-ticket-perforated"></i>' +
                        '<div class="queue-empty-title">No queue yet</div>' +
                        '<p class="queue-empty-copy">Guests do not receive a live queue ticket. If you request a document, it will appear under My Requests and Queue History.</p>' +
                    "</div>";
                return;
            }

            var active = this.getActiveRequest();
            if (!active) {
                container.innerHTML =
                    '<div class="queue-empty-state">' +
                        '<i class="bi bi-inbox"></i>' +
                        '<div class="queue-empty-title">No ongoing request right now</div>' +
                        '<p class="queue-empty-copy">Your live queue ticket will show here once you have a processing or ready-for-pickup request.</p>' +
                        '<button class="btn-request-now mt-3" type="button" onclick="QReserve.switchTab(\'my-requests\')">' +
                            '<i class="bi bi-plus-circle"></i> Request a document' +
                        "</button>" +
                    "</div>";
                return;
            }

            var qrBoxId = this.userType + "ActiveQrBox";
            var dbId = active.db_id || "";

            container.innerHTML =
                '<div class="my-queue-card">' +
                    '<div class="d-flex justify-content-between align-items-center mb-3">' +
                        '<div class="my-queue-card-title mb-0">Your Current Queue</div>' +
                        '<span class="badge bg-warning text-dark px-3 py-2 rounded-pill" style="font-size:12px;font-weight:700;">' +
                            escapeHtml(active.status) +
                        "</span>" +
                    "</div>" +
                    '<div class="my-queue-split">' +
                        '<div class="my-queue-info">' +
                            '<div class="queue-field-label">Queue Number</div>' +
                            '<div class="queue-number-display" style="font-size:26px;font-weight:900;color:#1e293b;letter-spacing:1px;margin-bottom:10px;">Queue ' +
                                escapeHtml(active.queueNum) +
                            "</div>" +
                            '<div class="queue-field-label">Counter</div>' +
                            '<div class="queue-field-value" style="font-weight:700;">' + escapeHtml(active.counter) + "</div>" +
                            '<div class="queue-field-label">Price</div>' +
                            '<div class="queue-field-value" style="font-weight:700;color:#047857;">₱' + escapeHtml(active.price) + ".00</div>" +
                            '<div class="queue-field-label">Estimated Wait Time</div>' +
                            '<div class="wait-time-value" style="font-size:20px;font-weight:800;color:#1e293b;">' +
                                escapeHtml(active.waitTime) +
                            "</div>" +
                            '<div style="font-size:11.5px;color:#64748b;font-weight:500;margin-bottom:12px;">' +
                                '<i class="bi bi-person-check"></i> The person in front of the queue is now being served.' +
                            "</div>" +
                            '<div class="queue-field-label">Service</div>' +
                            '<div class="queue-field-value">' + escapeHtml(active.service) + "</div>" +
                            '<div class="queue-field-label">Requests</div>' +
                            '<div class="queue-field-value" style="font-weight:700;color:#8c1010;">' +
                                escapeHtml(active.docName) +
                            "</div>" +
                        "</div>" +
                        '<div class="my-queue-qr-box" id="' + qrBoxId + '"></div>' +
                    "</div>" +
                    '<div class="my-queue-actions">' +
                        '<button class="btn-download-qr" type="button" onclick="QReserveApp.downloadActiveQR(\'' + qrBoxId + '\')">' +
                            '<i class="bi bi-qr-code-scan"></i> Download QR' +
                        "</button>" +
                        '<button class="btn btn-outline-success rounded-pill fw-bold" type="button" onclick="QReserveApp.completeActive(\'' + dbId + '\')">' +
                            '<i class="bi bi-check2-circle"></i> Complete' +
                        "</button>" +
                        '<button class="btn btn-outline-danger rounded-pill fw-bold" type="button" onclick="QReserveApp.cancelActive(\'' + dbId + '\')">' +
                            '<i class="bi bi-x-circle"></i> Cancel' +
                        "</button>" +
                    "</div>" +
                "</div>";

            setTimeout(function () {
                var box = document.getElementById(qrBoxId);
                if (box && typeof QRCode !== "undefined") {
                    box.innerHTML = "";
                    new QRCode(box, {
                        text: active.transactionId,
                        width: 140,
                        height: 140,
                        colorDark: "#1e293b",
                        colorLight: "#f8fafc",
                        correctLevel: QRCode.CorrectLevel.M
                    });
                }
            }, 50);
        },

        downloadActiveQR: function (qrBoxId) {
            var box = document.getElementById(qrBoxId);
            if (!box) return;
            var canvas = box.querySelector("canvas");
            if (!canvas) {
                alert("QR code not ready yet.");
                return;
            }
            var link = document.createElement("a");
            link.download = "QRESERVE-Ticket-QR.png";
            link.href = canvas.toDataURL("image/png");
            link.click();
        },

        renderMyRequests: function () {
            var container = document.getElementById("myRequestsViewContainer");
            if (!container) return;

            var list = this.cachedRequests;
            var html = '<div class="requests-page-title">Active &amp; Pending Requests</div>';

            if (!this.getActiveRequest()) {
                html += this.documentPickerHtml();
            }

            if (list.length === 0) {
                html +=
                    '<div class="queue-empty-state" style="margin-top:28px;">' +
                        '<i class="bi bi-file-earmark-text"></i>' +
                        '<div class="queue-empty-title">No requests yet</div>' +
                        '<p class="queue-empty-copy">Choose a document above and click Request now.</p>' +
                    "</div>";
            } else {
                html += '<div class="my-requests-list" style="margin-top:24px;">';
                list.forEach(function (item) {
                    var badgeClass = statusModifier(item.status);
                    html +=
                        '<div class="my-request-pill ' + badgeClass + '">' +
                            '<div class="my-request-pill-left">' +
                                '<div class="my-request-pill-icon"><i class="bi bi-file-earmark-text"></i></div>' +
                                '<div class="my-request-pill-info">' +
                                    '<div class="my-request-pill-name">' + escapeHtml(item.docName) + "</div>" +
                                    '<div class="my-request-pill-date">' + escapeHtml(item.dateTime) + "</div>" +
                                "</div>" +
                            "</div>" +
                            '<div class="my-request-pill-status">' + escapeHtml(item.status) + "</div>" +
                        "</div>";
                });
                html += "</div>";
            }

            container.innerHTML = html;
        },

        rebuildHistoryDateFilter: function () {
            var sel = document.getElementById("historyFilterDate");
            if (!sel) return;

            var previous = sel.value || "all";
            var groups = [];
            this.cachedRequests.forEach(function (item) {
                if (item.dateGroup && groups.indexOf(item.dateGroup) === -1) {
                    groups.push(item.dateGroup);
                }
            });

            sel.innerHTML = '<option value="all">All Dates</option>';
            groups.forEach(function (group) {
                var option = document.createElement("option");
                option.value = group;
                option.textContent = group;
                sel.appendChild(option);
            });

            var stillValid = previous === "all" || groups.indexOf(previous) !== -1;
            sel.value = stillValid ? previous : "all";
        },

        renderQueueHistory: function () {
            var container = document.getElementById("historyCardsListContainer");
            if (!container) return;

            this.rebuildHistoryDateFilter();

            var list = this.cachedRequests;
            var dateFilter = document.getElementById("historyFilterDate")
                ? document.getElementById("historyFilterDate").value
                : "all";
            var docFilter = document.getElementById("historyFilterDoc")
                ? document.getElementById("historyFilterDoc").value
                : "all";
            var statusFilter = document.getElementById("historyFilterStatus")
                ? document.getElementById("historyFilterStatus").value
                : "all";

            var filtered = list.filter(function (item) {
                if (dateFilter !== "all" && item.dateGroup !== dateFilter) return false;
                if (docFilter !== "all" && item.docName !== docFilter) return false;
                if (statusFilter !== "all" && item.status !== statusFilter) return false;
                return true;
            });

            if (filtered.length === 0) {
                container.innerHTML =
                    '<div class="queue-empty-state" style="margin-top:0;">' +
                        '<i class="bi bi-inbox"></i>' +
                        '<div class="queue-empty-title">No matching queue history</div>' +
                        '<p class="queue-empty-copy">Requests from My Queue and My Requests show up here after they are created.</p>' +
                    "</div>";
                return;
            }

            var html = "";
            filtered.forEach(function (item) {
                var iconHtml = item.status === "Completed"
                    ? '<div class="history-item-icon icon-check"><i class="bi bi-check-circle-fill"></i></div>'
                    : '<div class="history-item-icon icon-spinner"><i class="bi bi-arrow-repeat"></i></div>';

                html +=
                    '<div class="history-item-card">' +
                        '<div class="history-item-top">' +
                            iconHtml +
                            '<div class="history-item-title-wrap">' +
                                '<div class="history-item-name">' + escapeHtml(item.docName) + "</div>" +
                                '<div class="history-item-queue">Queue ' + escapeHtml(item.queueNum) + "</div>" +
                            "</div>" +
                            '<div class="history-item-date">' + escapeHtml(item.dateTime) + "</div>" +
                            '<div class="history-item-status-text ' + statusTextClass(item.status) + '">' +
                                escapeHtml(item.status) +
                            "</div>" +
                        "</div>" +
                        '<div class="history-item-details">' +
                            '<div class="history-item-labels">' +
                                "<div>Service</div>" +
                                "<div>Counter</div>" +
                                "<div>Price</div>" +
                                "<div>Waiting time</div>" +
                                "<div>Transaction ID</div>" +
                            "</div>" +
                            '<div class="history-item-values">' +
                                "<div>" + escapeHtml(item.service) + "</div>" +
                                "<div>" + escapeHtml(item.counter) + "</div>" +
                                "<div>₱" + escapeHtml(item.price) + ".00</div>" +
                                "<div>" + escapeHtml(item.waitTime) + "</div>" +
                                "<div>" + escapeHtml(item.transactionId) + "</div>" +
                            "</div>" +
                        "</div>" +
                    "</div>";
            });

            container.innerHTML = html;
        }
    };

    document.addEventListener("DOMContentLoaded", function () {
        QReserveApp.userType = document.body.getAttribute("data-qreserve-user") || QReserveApp.userType;
        QReserveApp.fetchRequests(function () {
            QReserveApp.renderAll();
        });

        document.querySelectorAll("[data-tab-target]").forEach(function (link) {
            link.addEventListener("click", function () {
                setTimeout(function () {
                    QReserveApp.renderAll();
                }, 200);
            });
        });
    });
})();
