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

        getActiveCounterTicket: function () {
            var live = this.cachedRequests.filter(function (r) {
                return (r.status === 'Processing') && !r.counterTurnDone && (r.queueStep !== 'document_processing');
            });
            return live.length ? live[0] : null;
        },

        getProcessingDocuments: function () {
            return this.cachedRequests.filter(function (r) {
                return (r.status === 'Processing' && (Boolean(r.counterTurnDone) || r.queueStep === 'document_processing')) ||
                       (r.status === 'Ready for pickup');
            });
        },

        getActiveRequest: function () {
            return this.getActiveCounterTicket() || (this.getProcessingDocuments()[0] || null);
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
            var isTurnFinished = Boolean(active.counterTurnDone) || active.status === "Ready for pickup" || active.status === "Completed" || active.queueStep === "document_processing";

            var badgeClass = active.isNowServing
                ? "bg-success text-white"
                : (isTurnFinished
                    ? (active.status === "Ready for pickup" ? "bg-info text-white" : "bg-success text-white")
                    : (active.queueStep === "payment" ? "bg-warning text-dark" : "bg-primary text-white"));

            var badgeText = active.isNowServing
                ? "Now Serving"
                : (isTurnFinished
                    ? (active.status === "Ready for pickup" ? "Ready for Pickup" : (active.status === "Completed" ? "Completed" : "Document Processing"))
                    : (active.queueStep === "payment" ? "Awaiting Payment" : "Waiting for Counter"));

            var bannerHtml = "";
            if (active.isNowServing) {
                bannerHtml =
                    '<div style="background:linear-gradient(135deg,#047857 0%,#059669 100%);border-radius:14px;padding:20px 24px;margin-bottom:16px;text-align:center;box-shadow:0 4px 14px rgba(4,120,87,0.25);">' +
                        '<div style="display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;border-radius:50%;background:rgba(255,255,255,0.2);margin-bottom:8px;">' +
                            '<i class="bi bi-megaphone-fill" style="font-size:22px;color:#fff;"></i>' +
                        "</div>" +
                        '<div style="font-size:18px;font-weight:900;color:#fff;letter-spacing:1.5px;text-transform:uppercase;">Now Calling Your Number!</div>' +
                        '<div style="font-size:13px;color:rgba(255,255,255,0.95);margin-top:4px;font-weight:600;">' +
                            (active.queueStep === "payment"
                                ? "Please proceed to " + escapeHtml(active.counter) + " to pay ₱" + escapeHtml(active.price) + ".00"
                                : (active.status === "Ready for pickup"
                                    ? "Your document is ready! Please proceed to " + escapeHtml(active.counter) + " to claim it."
                                    : "Please proceed to " + escapeHtml(active.counter) + " and have your documents ready.")) +
                        "</div>" +
                    "</div>";
            } else if (isTurnFinished) {
                if (active.status === "Ready for pickup") {
                    bannerHtml =
                        '<div style="background:linear-gradient(135deg,#0284c7 0%,#0369a1 100%);border-radius:14px;padding:20px 24px;margin-bottom:16px;text-align:center;">' +
                            '<div style="display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;border-radius:50%;background:rgba(255,255,255,0.2);margin-bottom:8px;">' +
                                '<i class="bi bi-file-earmark-check-fill" style="font-size:22px;color:#fff;"></i>' +
                            "</div>" +
                            '<div style="font-size:18px;font-weight:900;color:#fff;letter-spacing:1.5px;text-transform:uppercase;">Document Ready for Pickup</div>' +
                            '<div style="font-size:13px;color:rgba(255,255,255,0.9);margin-top:4px;font-weight:500;">Your document is ready. Please proceed to ' + escapeHtml(active.counter) + " to claim it.</div>" +
                        "</div>";
                } else if (active.status === "Completed") {
                    bannerHtml =
                        '<div style="background:linear-gradient(135deg,#047857 0%,#059669 100%);border-radius:14px;padding:20px 24px;margin-bottom:16px;text-align:center;">' +
                            '<div style="display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;border-radius:50%;background:rgba(255,255,255,0.2);margin-bottom:8px;">' +
                                '<i class="bi bi-check-circle-fill" style="font-size:22px;color:#fff;"></i>' +
                            "</div>" +
                            '<div style="font-size:18px;font-weight:900;color:#fff;letter-spacing:1px;text-transform:uppercase;">Transaction Completed</div>' +
                            '<div style="font-size:13px;color:rgba(255,255,255,0.95);margin-top:4px;font-weight:600;">Your document request has been completed. Thank you for using QRESERVE!</div>' +
                        "</div>";
                } else {
                    bannerHtml =
                        '<div style="background:linear-gradient(135deg,#047857 0%,#059669 100%);border-radius:14px;padding:20px 24px;margin-bottom:16px;text-align:center;box-shadow:0 4px 14px rgba(4,120,87,0.25);">' +
                            '<div style="display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;border-radius:50%;background:rgba(255,255,255,0.2);margin-bottom:8px;">' +
                                '<i class="bi bi-check2-circle" style="font-size:24px;color:#fff;"></i>' +
                            "</div>" +
                            '<div style="font-size:18px;font-weight:900;color:#fff;letter-spacing:1px;text-transform:uppercase;">Counter Turn Completed!</div>' +
                            '<div style="font-size:13px;color:rgba(255,255,255,0.95);margin-top:4px;font-weight:600;">Your document request is now processing (Est. 3–5 working days). Keep your QR receipt below to claim your document.</div>' +
                        "</div>";
                }
            } else {
                bannerHtml =
                    '<div style="margin-bottom:16px;">' +
                        (active.queueStep === "payment"
                            ? '<div style="display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:700;color:#b45309;background:#fef3c7;padding:3px 10px;border-radius:20px;margin-bottom:8px;"><i class="bi bi-wallet2"></i> Cashier Payment Pending (₱' + escapeHtml(active.price) + '.00)</div>'
                            : '<div style="display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:700;color:#1e40af;background:#dbeafe;padding:3px 10px;border-radius:20px;margin-bottom:8px;"><i class="bi bi-clock-history"></i> Waiting for Counter Turn</div>') +
                        '<div class="queue-field-label">Queue Status</div>' +
                        '<div class="wait-time-value" style="font-size:20px;font-weight:800;color:#1e293b;">' +
                            escapeHtml(active.aheadCount === 0 ? "Next in line" : active.waitTime) +
                        "</div>" +
                    "</div>";
            }

            var stageNotice = "";
            if (!isTurnFinished) {
                if (active.queueStep === "payment") {
                    stageNotice =
                        '<div style="background:#fffbeb;border:1.5px solid #fde68a;border-radius:12px;padding:12px 16px;margin-top:14px;display:flex;align-items:center;gap:10px;font-size:12.5px;color:#92400e;line-height:1.45;">' +
                            '<i class="bi bi-info-circle-fill" style="font-size:18px;color:#d97706;flex-shrink:0;"></i>' +
                            "<div>Please wait for your ticket to be called at <strong>" + escapeHtml(active.counter) + "</strong> to settle payment. <em>Your scannable QR receipt will be issued once your window turn is completed.</em></div>" +
                        "</div>";
                } else {
                    stageNotice =
                        '<div style="background:#eff6ff;border:1.5px solid #bfdbfe;border-radius:12px;padding:12px 16px;margin-top:14px;display:flex;align-items:center;gap:10px;font-size:12.5px;color:#1e40af;line-height:1.45;">' +
                            '<i class="bi bi-info-circle-fill" style="font-size:18px;color:#2563eb;flex-shrink:0;"></i>' +
                            "<div>Payment confirmed! Please proceed to <strong>" + escapeHtml(active.counter) + "</strong> when called. <em>Your scannable QR receipt will appear once the counter officer completes your turn.</em></div>" +
                        "</div>";
                }
            }

            var mainBody = "";
            if (isTurnFinished) {
                mainBody =
                    '<div class="my-queue-split">' +
                        '<div class="my-queue-info">' +
                            '<div class="queue-field-label">Queue Number</div>' +
                            '<div class="queue-number-display" style="font-size:26px;font-weight:900;color:#1e293b;letter-spacing:1px;margin-bottom:10px;">Queue ' +
                                escapeHtml(active.queueNum) +
                            "</div>" +
                            '<div class="queue-field-label">Counter</div>' +
                            '<div class="queue-field-value" style="font-weight:700;">' + escapeHtml(active.counter) + "</div>" +
                            '<div class="queue-field-label">Price</div>' +
                            '<div class="queue-field-value" style="font-weight:700;color:#047857;">₱' + escapeHtml(active.price) + ".00" + (active.isPaid ? " – paid" : "") + "</div>" +
                            '<div class="queue-field-label">Service</div>' +
                            '<div class="queue-field-value">' + escapeHtml(active.service) + "</div>" +
                            '<div class="queue-field-label">Requests</div>' +
                            '<div class="queue-field-value" style="font-weight:700;color:#8c1010;">' +
                                escapeHtml(active.docName) +
                            "</div>" +
                        "</div>" +
                        '<div style="display:flex;flex-direction:column;align-items:center;gap:6px;">' +
                            '<div class="my-queue-qr-box" id="' + qrBoxId + '" style="cursor:pointer;" onclick="window.open(\'/ticket/\' + encodeURIComponent(\'' + active.transactionId + '\'), \'_blank\')" title="Click to view digital receipt &amp; ticket details">' +
                            "</div>" +
                            '<div style="font-size:11px;font-weight:700;color:#64748b;text-align:center;margin-top:2px;"><i class="bi bi-qr-code me-1"></i>Official QR Receipt</div>' +
                            '<div style="font-size:10px;color:#94a3b8;text-align:center;max-width:140px;">Scannable by phone camera (works offline)</div>' +
                        "</div>" +
                    "</div>" +
                    '<div class="my-queue-actions d-flex flex-wrap gap-2">' +
                        '<button class="btn btn-success rounded-pill fw-bold d-inline-flex align-items-center gap-2 px-3 py-2" type="button" onclick="QReserveApp.downloadReceiptPNG()" style="font-size:13px;">' +
                            '<i class="bi bi-file-earmark-arrow-down-fill"></i> Download Receipt (PNG)' +
                        "</button>" +
                        '<button class="btn btn-outline-dark rounded-pill fw-bold d-inline-flex align-items-center gap-2 px-3 py-2" type="button" onclick="QReserveApp.downloadActiveQR(\'' + qrBoxId + '\')" style="font-size:13px;">' +
                            '<i class="bi bi-qr-code-scan"></i> Download QR' +
                        "</button>" +
                        '<a href="/ticket/' + encodeURIComponent(active.transactionId) + '" target="_blank" class="btn btn-outline-secondary rounded-pill fw-bold d-inline-flex align-items-center gap-2 px-3 py-2" style="font-size:13px;text-decoration:none;">' +
                            '<i class="bi bi-receipt"></i> View Online' +
                        "</a>" +
                    "</div>";
            } else {
                mainBody =
                    '<div class="my-queue-info">' +
                        '<div class="row g-3">' +
                            '<div class="col-6">' +
                                '<div class="queue-field-label">Queue Number</div>' +
                                '<div class="queue-number-display" style="font-size:28px;font-weight:900;color:#1e293b;letter-spacing:1px;margin-bottom:8px;">Queue ' + escapeHtml(active.queueNum) + '</div>' +
                            '</div>' +
                            '<div class="col-6">' +
                                '<div class="queue-field-label">Counter</div>' +
                                '<div class="queue-field-value" style="font-weight:700;font-size:16px;">' + escapeHtml(active.counter) + '</div>' +
                            '</div>' +
                            '<div class="col-6">' +
                                '<div class="queue-field-label">Price</div>' +
                                '<div class="queue-field-value" style="font-weight:700;' + (active.price > 0 ? (active.queueStep === 'payment' ? 'color:#b45309;' : 'color:#047857;') : 'color:#64748b;') + '">' +
                                    (active.price > 0 ? '₱' + escapeHtml(active.price) + '.00' + (active.queueStep === 'payment' ? ' (pending)' : ' – paid') : '—') +
                                '</div>' +
                            '</div>' +
                            '<div class="col-6">' +
                                '<div class="queue-field-label">Service</div>' +
                                '<div class="queue-field-value">' + escapeHtml(active.service) + '</div>' +
                            '</div>' +
                            '<div class="col-12">' +
                                '<div class="queue-field-label">Requests</div>' +
                                '<div class="queue-field-value" style="font-weight:700;color:#8c1010;">' + escapeHtml(active.docName) + '</div>' +
                            '</div>' +
                        '</div>' +
                        stageNotice +
                    '</div>' +
                    '<div class="my-queue-actions d-flex justify-content-end mt-3">' +
                        '<button class="btn btn-outline-danger rounded-pill fw-bold d-inline-flex align-items-center gap-2 px-3 py-2" type="button" onclick="QReserveApp.cancelActive(\'' + dbId + '\')" style="font-size:13px;">' +
                            '<i class="bi bi-x-circle"></i> Cancel Queue Ticket' +
                        '</button>' +
                    '</div>';
            }

            container.innerHTML =
                '<div class="my-queue-card fade-in-stagger delay-1">' +
                    '<div class="d-flex justify-content-between align-items-center mb-3">' +
                        '<div class="my-queue-card-title mb-0">Your Current Queue</div>' +
                        '<span class="badge ' + badgeClass + ' px-3 py-2 rounded-pill" style="font-size:12px;font-weight:700;">' +
                            badgeText +
                        "</span>" +
                    "</div>" +
                    bannerHtml +
                    mainBody +
                "</div>";

            if (isTurnFinished) {
                var renderQrCode = function (attempts) {
                    var box = document.getElementById(qrBoxId);
                    if (!box) return;
                    if (typeof QRCode === "undefined") {
                        if ((attempts || 0) < 25) {
                            setTimeout(function () { renderQrCode((attempts || 0) + 1); }, 80);
                        }
                        return;
                    }
                    var payload = (window.QReserveTicketCard && window.QReserveTicketCard.buildReceiptText)
                        ? window.QReserveTicketCard.buildReceiptText(active)
                        : (window.QReserveTicketCard ? window.QReserveTicketCard.ticketUrl(active.transactionId) : "");
                    if (window.QReserveTicketCard && window.QReserveTicketCard.buildQRCanvas) {
                        window.QReserveTicketCard.buildQRCanvas(box, payload, 140);
                    } else {
                        box.innerHTML = "";
                        new QRCode(box, {
                            text: payload,
                            width: 140,
                            height: 140,
                            colorDark: "#1e293b",
                            colorLight: "#f8fafc",
                            correctLevel: QRCode.CorrectLevel.M
                        });
                    }
                };
                setTimeout(function () { renderQrCode(0); }, 30);
            }
        },

        downloadReceiptPNG: function () {
            var active = this.getActiveRequest();
            if (!active) return;
            var boxId = this.userType + "ActiveQrBox";
            var box = document.getElementById(boxId);
            var qrEl = box ? (box.querySelector("canvas") || box.querySelector("img")) : null;

            if (window.QReserveTicketCard) {
                window.QReserveTicketCard.download({
                    qrImage: qrEl,
                    qrPayload: window.QReserveTicketCard.buildReceiptText(active),
                    queueNum: active.queueNum,
                    docName: active.docName,
                    counter: active.counter,
                    txId: active.transactionId,
                    transactionId: active.transactionId,
                    date: active.dateTime,
                    dateTime: active.dateTime,
                    userName: active.userName,
                    userType: active.userType,
                    price: active.price,
                    isPaid: active.isPaid,
                    status: active.status
                });
            } else {
                alert("Receipt generator is still loading. Please try again.");
            }
        },

        downloadActiveQR: function (qrBoxId) {
            var active = this.getActiveRequest();
            if (!active) return;
            var box = document.getElementById(qrBoxId);
            var qrEl = box ? (box.querySelector("canvas") || box.querySelector("img")) : null;

            if (window.QReserveTicketCard) {
                window.QReserveTicketCard.downloadQR({
                    qrImage: qrEl,
                    qrPayload: window.QReserveTicketCard.buildReceiptText(active),
                    qrUrl: window.QReserveTicketCard.ticketUrl(active.transactionId),
                    queueNum: active.queueNum,
                    docName: active.docName,
                    counter: active.counter,
                    txId: active.transactionId,
                    transactionId: active.transactionId,
                    date: active.dateTime,
                    dateTime: active.dateTime,
                    userName: active.userName,
                    userType: active.userType,
                    price: active.price,
                    isPaid: active.isPaid,
                    status: active.status
                });
            } else {
                alert("QR generator is still loading. Please try again.");
            }
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
