/*!
 * QRESERVE — Queue Card PNG renderer
 *
 * Single source of truth for the printable queue card. Used by:
 *   - templates/student_dashboard.html  (Download QR)
 *   - templates/guest_login.html        (Download QR)
 *   - templates/ticket_status.html      (card shown after scanning the QR)
 *
 * Public API (window.QReserveTicketCard):
 *   LAYOUT                card geometry (640x820, 320px QR slot)
 *   ticketUrl(txId)       absolute URL encoded into the QR code
 *   baseUrl()             base address used for QR codes
 *   isLocalBaseUrl()      true when that address is a loopback address
 *   warnLocalBase()       log a console warning when it is
 *   draw(canvas, data)      paint the card onto an existing canvas
 *   render(data)            return a new offscreen <canvas> holding the card
 *   toPNG(data)             return the card as a PNG data URL
 *   download(data)          trigger a browser download of the card PNG
 *   buildData(source)       normalize a request (camelCase or snake_case)
 *   formatDate(value)       "January 01, 2026" style date label
 *   buildQRCanvas(el, url)  render a QR code into `el`, return its <canvas>
 *   ensureHolder()          hidden offscreen element used for QR rendering
 */
(function (global) {
    'use strict';

    var LAYOUT = {
        width: 640,
        height: 820,
        padding: 40,
        qrSize: 320,
        qrY: 165,
        cardPad: 18,
        radius: 20
    };

    function roundRect(ctx, x, y, w, h, r) {
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.arcTo(x + w, y, x + w, y + h, r);
        ctx.arcTo(x + w, y + h, x, y + h, r);
        ctx.arcTo(x, y + h, x, y, r);
        ctx.arcTo(x, y, x + w, y, r);
        ctx.closePath();
    }

    function formatDate(value) {
        var d;
        if (value instanceof Date) {
            d = value;
        } else if (value === null || value === undefined || value === '') {
            d = new Date();
        } else {
            d = new Date(value);
        }
        if (!d || isNaN(d.getTime())) d = new Date();
        return d.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    }

    function pick(source, camel, snake, fallback) {
        if (!source) return fallback;
        var value = source[camel];
        if (value === undefined || value === null || value === '') value = source[snake];
        return (value === undefined || value === null || value === '') ? fallback : value;
    }

    /* Mirrors the dashboards' getDisplayDocName(): while the request sits in the
       Registrar step, show only the academic items, not the paid ones. */
    function resolveDocName(source) {
        var items = (source && (source.items || source.Items)) || [];
        var step = pick(source, 'queueStep', 'queue_step', null);
        if (step === 'processing' && items.length) {
            var academic = items.filter(function (it) { return it && it.type === 'academic'; });
            if (academic.length) {
                return academic.map(function (it) { return it.name; }).join(', ');
            }
        }
        return pick(source, 'docName', 'doc_name', 'Document Request');
    }

    function buildData(source) {
        source = source || {};
        var resolvedTx = pick(source, 'txId', 'transaction_id', '');
        if (!resolvedTx && source.transactionId) resolvedTx = source.transactionId;
        return {
            qrImage: source.qrImage || source.qr || null,
            qrUrl: source.qrUrl || null,
            qrPayload: source.qrPayload || null,
            queueNum: String(pick(source, 'queueNum', 'queue_number', '---')),
            docName: String(resolveDocName(source) || 'Document Request'),
            counter: String(pick(source, 'counter', 'counter', '') || ''),
            txId: String(resolvedTx || ''),
            transactionId: String(resolvedTx || ''),
            date: source.date || source.dateTime || null,
            dateTime: source.dateTime || null,
            userName: pick(source, 'userName', 'user_name', ''),
            userType: pick(source, 'userType', 'user_type', ''),
            price: pick(source, 'price', 'total_price', 0),
            isPaid: pick(source, 'isPaid', 'is_paid', false),
            queueStep: pick(source, 'queueStep', 'queue_step', null),
            status: pick(source, 'status', 'status', 'Processing')
        };
    }

    /* Offline-first text receipt embedded into the QR code matrix.
       When any smartphone camera scans this, the complete receipt details
       appear natively on-screen instantly without needing local server or Wi-Fi. */
    function buildReceiptText(source) {
        var data = buildData(source);
        var queueNum = data.queueNum || '---';
        var txId = data.txId || data.transactionId || '---';
        var userName = data.userName || (data.userType === 'student' ? 'Student' : 'Guest');
        var userType = data.userType ? (String(data.userType).charAt(0).toUpperCase() + String(data.userType).slice(1)) : 'Student';
        var docName = String(data.docName || resolveDocName(data) || 'Document Request').replace(/[\u2010-\u2015]/g, '-');
        var counter = String(data.counter || 'Registrar').replace(/[\u2010-\u2015]/g, '-');
        var price = (data.price !== null && data.price !== undefined) ? 'PHP ' + Number(data.price).toFixed(2) : 'PHP 0.00';
        var isPaid = data.isPaid ? 'PAID' : (data.queueStep === 'payment' ? 'UNPAID' : 'PAID');
        var dateStr = String(data.dateTime || formatDate(data.date)).replace(/[\u2010-\u2015]/g, '-');
        var url = data.qrUrl || (txId !== '---' ? ticketUrl(txId) : '');

        var lines = [
            '*** BULSU BUSTOS - QRESERVE RECEIPT ***',
            '----------------------------------------',
            'QUEUE NO: ' + queueNum,
            'STATUS: DOCUMENT PROCESSING (3-5 DAYS)',
            'TX CODE: ' + txId,
            'REQUESTED BY: ' + userName + ' (' + userType + ')',
            'DOCUMENT: ' + docName,
            'AMOUNT: ' + price + ' [' + isPaid + ']',
            'COUNTER: ' + counter,
            'DATE: ' + dateStr,
            '----------------------------------------',
            'Est. Claim: 3-5 Working Days at Registrar',
            'Present this receipt & valid ID upon pickup.',
            url ? ('Online Receipt: ' + url) : ''
        ].filter(Boolean);

        return lines.join('\n');
    }

    /* Hidden scratch element used to render the QR offscreen at card resolution. */
    function ensureHolder() {
        var holder = document.getElementById('qreserve-qr-holder');
        if (!holder) {
            holder = document.createElement('div');
            holder.id = 'qreserve-qr-holder';
            holder.setAttribute('aria-hidden', 'true');
            holder.style.cssText = 'position:absolute;width:0;height:0;overflow:hidden;visibility:hidden;';
            document.body.appendChild(holder);
        }
        return holder;
    }

    /* Keep text inside the card by shrinking the font just enough. */
    function fillTextFitted(ctx, text, x, y, maxWidth) {
        if (ctx.measureText(text).width <= maxWidth) {
            ctx.fillText(text, x, y);
            return;
        }
        var size = parseInt(ctx.font, 10);
        while (size > 10) {
            size -= 1;
            ctx.font = ctx.font.replace(/(\d+)px/, size + 'px');
            if (ctx.measureText(text).width <= maxWidth) {
                ctx.fillText(text, x, y);
                return;
            }
        }
        ctx.fillText(text, x, y);
    }

    function draw(canvas, source) {
        var data = buildData(source);
        var W = LAYOUT.width;
        var H = LAYOUT.height;
        var padding = LAYOUT.padding;
        var maxWidth = W - padding * 2;

        canvas.width = W;
        canvas.height = H;

        var ctx = canvas.getContext('2d');
        if (!ctx) return canvas;

        // Card background
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, W, H);

        // Top accent bar
        ctx.fillStyle = '#8c1010';
        ctx.fillRect(0, 0, W, 14);

        // Branding
        ctx.fillStyle = '#8c1010';
        ctx.font = '900 34px Poppins, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'alphabetic';
        ctx.fillText('QRESERVE', W / 2, 92);

        // Subtitle
        ctx.fillStyle = '#64748b';
        ctx.font = '600 14px Poppins, sans-serif';
        ctx.fillText('Official Transaction Receipt', W / 2, 118);

        // Divider
        ctx.strokeStyle = '#e2e8f0';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(padding, 138);
        ctx.lineTo(W - padding, 138);
        ctx.stroke();

        // Card label box around QR
        var qrSize = LAYOUT.qrSize;
        var qrX = (W - qrSize) / 2;
        var qrY = LAYOUT.qrY;
        var cardPad = LAYOUT.cardPad;
        var radius = LAYOUT.radius;

        // Soft card behind QR (like login card)
        ctx.fillStyle = '#f8fafc';
        roundRect(ctx, qrX - cardPad, qrY - cardPad, qrSize + cardPad * 2, qrSize + cardPad * 2, radius);
        ctx.fill();
        ctx.strokeStyle = '#e2e8f0';
        ctx.lineWidth = 1.5;
        roundRect(ctx, qrX - cardPad, qrY - cardPad, qrSize + cardPad * 2, qrSize + cardPad * 2, radius);
        ctx.stroke();

        // Draw the QR code into the card
        if (data.qrImage) {
            ctx.imageSmoothingEnabled = true;
            try {
                ctx.drawImage(data.qrImage, qrX, qrY, qrSize, qrSize);
            } catch (e) {
                /* QR canvas not ready yet — leave the frame empty */
            }
        }

        // Queue number
        ctx.fillStyle = '#1e293b';
        ctx.font = '800 28px Poppins, sans-serif';
        fillTextFitted(ctx, 'Queue ' + data.queueNum, W / 2, qrY + qrSize + 60, maxWidth);

        // Detail rows
        ctx.fillStyle = '#8c1010';
        ctx.font = '700 16px Poppins, sans-serif';
        fillTextFitted(ctx, data.docName, W / 2, qrY + qrSize + 88, maxWidth);

        ctx.fillStyle = '#64748b';
        ctx.font = '600 14px Poppins, sans-serif';
        fillTextFitted(
            ctx,
            (data.counter || '') + '   |   ' + formatDate(data.date),
            W / 2,
            qrY + qrSize + 112,
            maxWidth
        );

        ctx.fillStyle = '#047857';
        ctx.font = '700 13px Poppins, sans-serif';
        var statusLabel = (data.status === 'Ready for pickup' ? 'READY FOR PICKUP' : 'DOCUMENT PROCESSING') +
                          (data.isPaid ? '  •  PAID (₱' + (data.price || 0) + '.00)' : '');
        fillTextFitted(ctx, statusLabel, W / 2, qrY + qrSize + 136, maxWidth);

        // Transaction ID at bottom
        ctx.strokeStyle = '#e2e8f0';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(padding, H - 90);
        ctx.lineTo(W - padding, H - 90);
        ctx.stroke();

        ctx.fillStyle = '#94a3b8';
        ctx.font = '600 13px Poppins, sans-serif';
        ctx.fillText('Transaction ID', W / 2, H - 62);

        ctx.fillStyle = '#1e293b';
        ctx.font = '700 15px Poppins, sans-serif';
        fillTextFitted(ctx, data.txId, W / 2, H - 38, maxWidth);

        return canvas;
    }

    function render(source) {
        return draw(document.createElement('canvas'), source);
    }

    function toPNG(source) {
        var data = buildData(source);
        data.qrImage = resolveQR(data);
        return render(data).toDataURL('image/png');
    }

    function triggerDownload(filename, dataUrl) {
        if (!dataUrl) return;
        var link = document.createElement('a');
        link.download = filename;
        link.href = dataUrl;
        link.style.display = 'none';
        document.body.appendChild(link);
        try {
            link.click();
        } finally {
            setTimeout(function () {
                if (link.parentNode) link.parentNode.removeChild(link);
            }, 100);
        }
    }

    function download(source) {
        var data = buildData(source);
        data.qrImage = resolveQR(data);
        var filename = 'QRESERVE-Receipt-' + (data.queueNum || 'Receipt') + '.png';
        try {
            var dataUrl = render(data).toDataURL('image/png');
            triggerDownload(filename, dataUrl);
        } catch (e) {
            console.error('[QRESERVE] Receipt PNG render error:', e);
            alert('Could not generate receipt image. Please try again.');
        }
    }

    /* Downloads ONLY the clean QR code image (no ticket background, no text).
       Scanning this QR code directs the user to their online receipt or shows receipt offline. */
    function downloadQR(source) {
        var data = buildData(source);
        var text = data.qrPayload || (data.txId ? buildReceiptText(data) : (data.qrUrl || ticketUrl(data.txId)));

        // If QRCode library is missing, fallback to existing rendered canvas/image
        if (typeof QRCode === 'undefined' || !text) {
            if (data.qrImage) {
                var src = data.qrImage.toDataURL ? data.qrImage.toDataURL('image/png') : data.qrImage.src;
                if (src) {
                    triggerDownload('QRESERVE-QR-' + (data.queueNum || 'Code') + '.png', src);
                    return;
                }
            }
            alert('QR code is still loading. Please wait a moment and try again.');
            return;
        }

        warnLocalBase();

        // Render clean, high-resolution QR (340x340)
        var holder = ensureHolder();
        holder.innerHTML = '';
        var qrSize = 340;
        try {
            new QRCode(holder, {
                text: text,
                width: qrSize,
                height: qrSize,
                colorDark: '#000000',
                colorLight: '#ffffff',
                correctLevel: QRCode.CorrectLevel.M
            });
        } catch (e) {
            holder.innerHTML = '';
            new QRCode(holder, {
                text: text,
                width: qrSize,
                height: qrSize,
                colorDark: '#000000',
                colorLight: '#ffffff',
                correctLevel: QRCode.CorrectLevel.L
            });
        }

        var canvas = holder.querySelector('canvas');
        var padding = 24;
        var outCanvas = document.createElement('canvas');
        outCanvas.width = qrSize + (padding * 2);
        outCanvas.height = qrSize + (padding * 2);
        var ctx = outCanvas.getContext('2d');

        // Pure white background and margin for effortless phone camera detection
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, outCanvas.width, outCanvas.height);

        if (canvas) {
            ctx.drawImage(canvas, padding, padding);
            triggerDownload('QRESERVE-QR-' + (data.queueNum || 'Ticket') + '.png', outCanvas.toDataURL('image/png'));
        } else {
            var img = holder.querySelector('img');
            if (img && img.src && img.src.indexOf('data:image') === 0) {
                var tempImg = new Image();
                tempImg.onload = function () {
                    ctx.drawImage(tempImg, padding, padding, qrSize, qrSize);
                    triggerDownload('QRESERVE-QR-' + (data.queueNum || 'Ticket') + '.png', outCanvas.toDataURL('image/png'));
                };
                tempImg.src = img.src;
            } else {
                setTimeout(function () {
                    var c2 = holder.querySelector('canvas');
                    var img2 = holder.querySelector('img');
                    if (c2) {
                        ctx.drawImage(c2, padding, padding);
                    } else if (img2) {
                        ctx.drawImage(img2, padding, padding, qrSize, qrSize);
                    }
                    triggerDownload('QRESERVE-QR-' + (data.queueNum || 'Ticket') + '.png', outCanvas.toDataURL('image/png'));
                }, 40);
            }
        }
    }

    /* Renders a QR code into `el` using the global QRCode library (qrcode.js)
       and returns the underlying <canvas> or <img>, or null when unavailable. */
    function buildQRCanvas(el, url, size) {
        if (!el || typeof QRCode === 'undefined') return null;
        warnLocalBase();
        el.innerHTML = '';
        var s = size || 140;
        try {
            new QRCode(el, {
                text: url,
                width: s,
                height: s,
                colorDark: '#1e293b',
                colorLight: '#f8fafc',
                correctLevel: QRCode.CorrectLevel.M
            });
            return el.querySelector('canvas') || el.querySelector('img');
        } catch (e) {
            console.warn('[QRESERVE] QRCode Level M failed, falling back to Level L:', e);
            try {
                el.innerHTML = '';
                new QRCode(el, {
                    text: url,
                    width: s,
                    height: s,
                    colorDark: '#1e293b',
                    colorLight: '#f8fafc',
                    correctLevel: QRCode.CorrectLevel.L
                });
                return el.querySelector('canvas') || el.querySelector('img');
            } catch (err2) {
                console.error('[QRESERVE] buildQRCanvas failed:', err2);
                return null;
            }
        }
    }

    /* Prefer a QR rendered at the card's native resolution over a small
       on-screen QR, so the exported PNG stays crisp and scannable. */
    function resolveQR(data) {
        var text = data.qrPayload || (data.txId ? buildReceiptText(data) : data.qrUrl);
        if (text && typeof QRCode !== 'undefined') {
            var canvas = buildQRCanvas(ensureHolder(), text, LAYOUT.qrSize);
            if (canvas) return canvas;
        }
        return data.qrImage || null;
    }

    /* ------------------------------------------------------------------
     * QR destination
     *
     * The QR must point at an address a phone can actually reach. Using
     * window.location.origin is wrong whenever the app is opened through
     * 127.0.0.1 / localhost: the phone would then look up its own machine.
     * The server injects PUBLIC_BASE_URL as window.QRESERVE_BASE_URL; we
     * only fall back to the origin when that is not set.
     * ------------------------------------------------------------------ */

    function baseUrl() {
        var base = window.QRESERVE_BASE_URL;
        if (typeof base !== 'string' || !base) {
            base = (window.location && window.location.origin) || '';
        }
        return String(base).replace(/\/+$/, '');
    }

    function ticketUrl(transactionId) {
        if (!transactionId) return '';
        return baseUrl() + '/ticket/' + encodeURIComponent(transactionId);
    }

    function baseHostname() {
        var base = baseUrl();
        var m = /^[a-z][a-z0-9+.-]*:\/\/([^/?#]+)/i.exec(base);
        var host = (m ? m[1] : base).split('@').pop().split(':')[0];
        return host.toLowerCase();
    }

    function isLocalBaseUrl() {
        var host = baseHostname();
        return (
            host === '' ||
            host === 'localhost' ||
            host === '::1' ||
            host === '0.0.0.0' ||
            host.indexOf('127.') === 0
        );
    }

    /* Loopback base URLs are a deployment problem, not something the person
       holding the ticket can act on, so this stays in the console instead of
       taking up the page. */
    function warnLocalBase() {
        if (!isLocalBaseUrl()) return;
        if (warnLocalBase.done) return;
        warnLocalBase.done = true;
        if (window.console && console.warn) {
            console.warn(
                '[QRESERVE] QR codes point at ' + baseHostname() +
                ', which a phone cannot reach. Open the app through your Wi-Fi ' +
                'address or set PUBLIC_BASE_URL to a public URL, otherwise ' +
                'scanned tickets will not load.'
            );
        }
    }

    global.QReserveTicketCard = {
        LAYOUT: LAYOUT,
        draw: draw,
        render: render,
        toPNG: toPNG,
        download: download,
        downloadReceipt: download,
        downloadQR: downloadQR,
        buildData: buildData,
        buildReceiptText: buildReceiptText,
        buildQRCanvas: buildQRCanvas,
        ensureHolder: ensureHolder,
        baseUrl: baseUrl,
        ticketUrl: ticketUrl,
        isLocalBaseUrl: isLocalBaseUrl,
        warnLocalBase: warnLocalBase,
        formatDate: formatDate,
        roundRect: roundRect
    };
})(window);