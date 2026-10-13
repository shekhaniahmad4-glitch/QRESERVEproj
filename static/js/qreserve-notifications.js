/* ==================================================================
   QRESERVE — Notifications
   Shared by the student dashboard and the guest dashboard.

   Renders the bell dropdown, keeps a badge count, polls for new
   notifications, shows an urgent toast (fade in / fade out), and lets
   the user dismiss or delete each notification with the X button.

   Markup expected on the page (ids match both dashboards):

     <div class="notification-bell-wrapper">
       <i id="notificationBell"></i>
       <span id="notificationBadge"></span>
       <div id="notificationDropdown" class="notification-dropdown">
         <div class="notification-dropdown-header">
           <span>Notifications</span>
           <div class="notification-header-actions">
             <button id="markAllRead" class="notification-mark-all">Mark all read</button>
             <button id="clearAllNotifications" class="notification-clear-all">Clear all</button>
           </div>
         </div>
         <div id="notificationList" class="notification-list"></div>
       </div>
     </div>

   Usage:

     QReserveNotifications.init({ pollMs: 2000 });

   Public API (window.QReserveNotifications):
     init(options)   wire up the bell, start polling
     poll()           fetch now and re-render
     render(list)     render a notification array
     toast(notif)     show the animated toast
     label(type)      human label for a notification type
     sound()          play the alert chime
     requestPermission()
   ================================================================== */

(function (global) {
    'use strict';

    var POLL_MS_DEFAULT = 2000;
    var TOAST_MS = 12000;

    /* A poll that never settles would otherwise latch the in-flight guard
       shut for the rest of the session, silently killing every future
       notification. Cap each request so one stalled response cannot
       disable polling permanently. */
    var REQUEST_TIMEOUT_MS = 10000;

    /* Types come from routes/auth.py (_notify / _notify_request).
       Keep this map in sync when adding a new notification type.

       toast: true means an on-screen popup. Outcome-type events always
       toast, because they are the ones a user waits on and would
       otherwise only see as a silent badge bump. Routine progress events
       (queue_joined, processing) stay bell-only so they do not bury the
       important ones under a wall of popups. */
    var TYPES = {
        now_serving:     { label: 'Now Serving',      icon: 'bi-bell-fill',            toast: true,  duration: 12000 },
        ready_for_pickup:{ label: 'Ready for Pickup', icon: 'bi-check-circle-fill',   toast: true,  duration: 12000 },
        payment_confirmed: { label: 'Payment Confirmed', icon: 'bi-receipt',           toast: true,  duration: 9000 },
        next_in_line:    { label: 'Next in Line',     icon: 'bi-hourglass-split',      toast: true,  duration: 9000 },
        queue_joined:    { label: 'Queue Joined',     icon: 'bi-ticket-perforated',   toast: false, duration: 6000 },
        processing:      { label: 'Processing',       icon: 'bi-gear-wide-connected', toast: false, duration: 6000 },
        completed:       { label: 'Completed',        icon: 'bi-check2-all',          toast: true,  duration: 9000 },
        cancelled:       { label: 'Cancelled',        icon: 'bi-x-octagon',           toast: true,  duration: 9000 },
        turn_ended:      { label: 'Turn Ended',       icon: 'bi-flag',                toast: true,  duration: 9000 },
        queue_reset:     { label: 'Queue Reset',      icon: 'bi-arrow-counterclockwise', toast: true,  duration: 9000 }
    };

    var DEFAULT_TYPE = { label: 'Update', icon: 'bi-info-circle', toast: false, duration: 6000 };

    var _state = {
        pollMs: POLL_MS_DEFAULT,
        lastUnread: 0,
        lastBadge: null,
        seenIds: {},
        pollCount: 0,
        timer: null,
        inFlight: false,
        booted: false,
        bootAt: 0,
        requestTimeoutMs: REQUEST_TIMEOUT_MS,
        urls: {
            list: '/api/notifications',
            read: '/api/notifications/read',
            readAll: '/api/notifications/read-all',
            clear: '/api/notifications/clear',
            remove: function (id) { return '/api/notifications/' + id; }
        },
        toastTypes: null
    };

    /* Endpoint indirection so the same module can drive the student,
       guest, and admin dashboards. Admin init() passes admin URLs. */
    function url(name, arg) {
        var u = _state.urls[name];
        if (typeof u === 'function') return u(arg);
        return u;
    }

    function shouldToast(type) {
        if (_state.toastTypes) return _state.toastTypes.indexOf(type) !== -1;
        return !!meta(type).toast;
    }

    /* ------------------------------------------------------------------
     * Helpers
     * ------------------------------------------------------------------ */

    function meta(type) {
        return TYPES[type] || DEFAULT_TYPE;
    }

    function label(type) {
        return meta(type).label;
    }

    function el(tag, className, text) {
        var node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined && text !== null) node.textContent = text;
        return node;
    }

    function byId(id) {
        return document.getElementById(id);
    }

    /* ------------------------------------------------------------------
     * Rendering
     * ------------------------------------------------------------------ */

    function updateBadge(count) {
        var badge = byId('notificationBadge');
        if (!badge) return;

        var n = count > 99 ? 99 : (count > 0 ? count : 0);

        // Only touch the DOM when the count really changed: re-writing the
        // same text would replay the pop animation and look like a blink.
        if (_state.lastBadge === n) return;
        _state.lastBadge = n;

        if (n > 0) {
            badge.textContent = n > 99 ? '99+' : String(n);
            badge.style.display = 'flex';
        } else {
            badge.style.display = 'none';
        }
    }

    /* A row's fingerprint. If this is unchanged we leave the existing DOM node
       completely alone, so its entry animation never replays. */
    function itemSignature(n) {
        return [
            n.type,
            n.is_read ? '1' : '0',
            n.title || '',
            n.message || '',
            n.queue_number || '',
            n.created_at || ''
        ].join('\u0001');
    }

    function buildItem(n) {
        var item = el('div', 'notification-item');
        item.setAttribute('data-id', n.id);

        var refs = {};
        refs.chip = el('span', 'notification-item-type');
        refs.head = el('div', 'notification-item-head');
        refs.title = el('div', 'notification-item-title');
        refs.message = el('div', 'notification-item-message');
        refs.queue = null;
        refs.time = el('div', 'notification-item-time');

        refs.head.appendChild(refs.title);
        refs.head.appendChild(refs.message);

        var close = el('button', 'notification-close', '\u00D7');
        close.type = 'button';
        close.title = 'Delete this notification';
        close.setAttribute('aria-label', 'Delete this notification');
        close.addEventListener('click', function (e) {
            e.stopPropagation();
            dismiss(item, item.__n.id);
        });

        item.appendChild(refs.chip);
        item.appendChild(refs.head);
        item.appendChild(refs.time);
        item.appendChild(close);

        // Clicking the body marks it read (but never triggers delete).
        item.addEventListener('click', function () {
            var current = item.__n;
            if (!current || current.is_read) return;
            fetch(url('read'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: current.id })
            }).then(poll).catch(function () {});
        });

        item.__refs = refs;
        syncItem(item, n);
        return item;
    }

    /* Writes the notification into an existing row, skipping any field that
       already matches so the node is left alone when nothing changed. */
    function syncItem(item, n) {
        item.__n = n;

        var sig = itemSignature(n);
        if (item.getAttribute('data-sig') === sig) return;
        item.setAttribute('data-sig', sig);

        var refs = item.__refs;

        item.classList.toggle('unread', !n.is_read);

        var chipClass = 'notification-item-type ' + n.type;
        if (refs.chip.className !== chipClass) refs.chip.className = chipClass;
        if (refs.chip.textContent !== label(n.type)) refs.chip.textContent = label(n.type);

        if (refs.title.textContent !== n.title) refs.title.textContent = n.title;
        if (refs.message.textContent !== n.message) refs.message.textContent = n.message;
        if (refs.time.textContent !== n.created_at) refs.time.textContent = n.created_at;

        if (n.queue_number) {
            if (!refs.queue) {
                refs.queue = el('span', 'notification-item-queue');
                item.insertBefore(refs.queue, refs.time);
            }
            if (refs.queue.textContent !== n.queue_number) {
                refs.queue.textContent = n.queue_number;
            }
        } else if (refs.queue) {
            if (refs.queue.parentNode) refs.queue.parentNode.removeChild(refs.queue);
            refs.queue = null;
        }
    }

    /* Keyed reconcile: existing rows are reused and only genuinely new ones
       are created, so polling never makes the list flicker or replay the
       row entry animation. */
    function render(notifications) {
        var list = byId('notificationList');
        if (!list) return;

        var scroll = list.scrollTop;
        var incoming = notifications || [];

        var existing = {};
        Array.prototype.slice.call(list.children).forEach(function (child) {
            var key = child.getAttribute('data-id');
            if (key !== null) existing[key] = child;
        });

        var keep = {};
        incoming.forEach(function (n) { keep[String(n.id)] = true; });

        // Drop rows that are gone (deleted here, or cleared elsewhere).
        Object.keys(existing).forEach(function (key) {
            if (keep[key]) return;
            if (existing[key].parentNode) existing[key].parentNode.removeChild(existing[key]);
            delete existing[key];
        });

        if (incoming.length === 0) {
            if (!list.querySelector('.notification-empty')) {
                list.appendChild(el('div', 'notification-empty', 'No notifications yet'));
            }
        } else {
            var empty = list.querySelector('.notification-empty');
            if (empty && empty.parentNode) empty.parentNode.removeChild(empty);

            var previous = null;
            incoming.forEach(function (n) {
                var key = String(n.id);
                var item = existing[key];

                if (item) {
                    syncItem(item, n);
                } else {
                    item = buildItem(n);
                    existing[key] = item;
                }

                // Place it directly after the previous entry. When the row is
                // already there this is a no-op, so an unchanged poll performs
                // zero DOM mutations and the list never appears to reload.
                if (previous) {
                    if (previous.nextSibling !== item) {
                        list.insertBefore(item, previous.nextSibling);
                    }
                } else if (list.firstChild !== item) {
                    list.insertBefore(item, list.firstChild);
                }

                previous = item;
            });
        }

        list.scrollTop = scroll;
    }

    /* ------------------------------------------------------------------
     * Deleting
     * ------------------------------------------------------------------ */

    function dismiss(item, id) {
        // Fade the row out first so the deletion feels deliberate.
        if (item) item.classList.add('removing');

        var done = function () {
            if (item && item.parentNode) item.parentNode.removeChild(item);
        };

        fetch(url('remove', id), { method: 'DELETE' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data || !data.success) {
                    if (item) item.classList.remove('removing');
                    return;
                }
                setTimeout(function () { done(); poll(); }, 180);
            })
            .catch(function () {
                if (item) item.classList.remove('removing');
            });
    }

    function clearAll() {
        var dropdown = byId('notificationDropdown');
        fetch(url('clear'), { method: 'POST' })
            .then(function (r) { return r.json(); })
            .then(function () {
                var list = byId('notificationList');
                if (list) list.innerHTML = '';
                if (dropdown) dropdown.classList.remove('show');
                poll();
            })
            .catch(function () {});
    }

    function markAllRead() {
        fetch(url('readAll'), { method: 'POST' })
            .then(poll)
            .catch(function () {});
    }

    /* ------------------------------------------------------------------
     * Toast — urgent notifications fade in, hold, then fade out
     * ------------------------------------------------------------------ */

    function ensureStack() {
        var stack = byId('notificationToastStack');
        if (stack) return stack;

        stack = el('div', 'notification-toast-stack');
        stack.id = 'notificationToastStack';
        document.body.appendChild(stack);
        return stack;
    }

    function toast(n) {
        if (!n || !document.body) return;

        var info = meta(n.type);
        var stack = ensureStack();

        var box = el('div', 'notification-toast');
        box.style.borderLeftColor = accentFor(n.type);

        var icon = el('i', 'bi ' + info.icon + ' notification-toast-icon');
        icon.style.background = tintFor(n.type);
        icon.style.color = accentFor(n.type);

        var body = el('div', 'notification-toast-body');
        body.appendChild(el('div', 'notification-toast-title', n.title));
        body.appendChild(el('div', 'notification-toast-message', n.message));
        if (n.queue_number) {
            body.appendChild(el('span', 'notification-toast-queue', n.queue_number));
        }

        var close = el('button', 'notification-toast-close', '\u00D7');
        close.type = 'button';
        close.setAttribute('aria-label', 'Dismiss');
        close.addEventListener('click', function (e) {
            e.stopPropagation();
            hide();
        });

        box.appendChild(icon);
        box.appendChild(body);
        box.appendChild(close);

        stack.appendChild(box);

        // Force layout so the browser commits the initial hidden state,
        // then flip to visible. Using a reflow instead of requestAnimationFrame
        // keeps the fade working in every browser (and in headless).
        void box.offsetWidth;
        box.classList.add('show');

        var duration = info.duration || TOAST_MS;
        var timer = setTimeout(hide, duration);

        function hide() {
            clearTimeout(timer);
            box.classList.remove('show');
            box.classList.add('hiding');
            setTimeout(function () {
                if (box.parentNode) box.parentNode.removeChild(box);
            }, 400);
        }

        box.addEventListener('click', function () {
            if (!n.is_read) {
                fetch(url('read'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: n.id })
                }).catch(function () {});
            }
            hide();
        });

        return box;
    }

    var ACCENTS = {
        now_serving: '#16a34a',
        ready_for_pickup: '#16a34a',
        payment_confirmed: '#0d9488',
        next_in_line: '#ca8a04',
        queue_joined: '#2563eb',
        processing: '#4f46e5',
        completed: '#475569',
        cancelled: '#dc2626',
        turn_ended: '#ea580c',
        queue_reset: '#64748b'
    };

    var TINTS = {
        now_serving: '#dcfce7',
        ready_for_pickup: '#bbf7d0',
        payment_confirmed: '#ccfbf1',
        next_in_line: '#fef9c3',
        queue_joined: '#dbeafe',
        processing: '#e0e7ff',
        completed: '#e2e8f0',
        cancelled: '#fee2e2',
        turn_ended: '#ffedd5',
        queue_reset: '#f1f5f9'
    };

    function accentFor(type) {
        return ACCENTS[type] || '#dc2626';
    }

    function tintFor(type) {
        return TINTS[type] || '#fee2e2';
    }

    /* ------------------------------------------------------------------
     * Browser push + sound
     * ------------------------------------------------------------------ */

    function requestPermission() {
        if (!('Notification' in global)) return;
        if (Notification.permission === 'default') {
            Notification.requestPermission().catch(function () {});
        }
    }

    function showBrowserNotification(title, body) {
        if (!('Notification' in global)) return;
        if (Notification.permission !== 'granted') return;

        try {
            var n = new Notification(title, {
                body: body,
                icon: '/static/images/favicon.png',
                badge: '/static/images/favicon.png',
                tag: 'qreserve-' + Date.now()
            });
            n.onclick = function () {
                global.focus();
                n.close();
            };
        } catch (e) {}
    }

    /* ------------------------------------------------------------------
     * Audio Engine — Web Audio API + HTML5 Audio Fallback
     * Unlocked on first user interaction (click, touch, key, pointer)
     * ------------------------------------------------------------------ */
    var _audioCtx = null;
    var _chimeAudio = null;
    var _chimeUrl = null;

    function getAudioContext() {
        if (!_audioCtx) {
            var AudioCtx = global.AudioContext || global.webkitAudioContext;
            if (AudioCtx) {
                try {
                    _audioCtx = new AudioCtx();
                } catch (e) {}
            }
        }
        return _audioCtx;
    }

    function generateChimeWavUrl() {
        if (_chimeUrl) return _chimeUrl;
        try {
            var sampleRate = 22050;
            var duration = 0.55;
            var numSamples = Math.floor(sampleRate * duration);
            var buffer = new ArrayBuffer(44 + numSamples * 2);
            var view = new DataView(buffer);

            function writeStr(offset, str) {
                for (var i = 0; i < str.length; i++) {
                    view.setUint8(offset + i, str.charCodeAt(i));
                }
            }

            writeStr(0, 'RIFF');
            view.setUint32(4, 36 + numSamples * 2, true);
            writeStr(8, 'WAVEfmt ');
            view.setUint32(16, 16, true);
            view.setUint16(20, 1, true); // PCM format
            view.setUint16(22, 1, true); // Mono channel
            view.setUint32(24, sampleRate, true);
            view.setUint32(28, sampleRate * 2, true);
            view.setUint16(32, 2, true);
            view.setUint16(34, 16, true);
            writeStr(36, 'data');
            view.setUint32(40, numSamples * 2, true);

            for (var i = 0; i < numSamples; i++) {
                var t = i / sampleRate;
                var freq, env;
                if (t < 0.12) {
                    freq = 659.25; // E5
                    env = Math.sin(Math.PI * (t / 0.12)) * 0.45;
                } else {
                    var t2 = t - 0.12;
                    freq = 880.00; // A5
                    env = Math.exp(-t2 * 6.0) * 0.5;
                }
                var sample = Math.floor(Math.sin(2 * Math.PI * freq * t) * env * 32767);
                view.setInt16(44 + i * 2, Math.max(-32767, Math.min(32767, sample)), true);
            }

            var blob = new Blob([buffer], { type: 'audio/wav' });
            var URLObj = global.URL || global.webkitURL;
            if (URLObj && typeof URLObj.createObjectURL === 'function') {
                _chimeUrl = URLObj.createObjectURL(blob);
            }
        } catch (e) {}
        return _chimeUrl;
    }

    function playWebAudioChime(ctx) {
        var now = ctx.currentTime;
        var osc1 = ctx.createOscillator();
        var osc2 = ctx.createOscillator();
        var gain = ctx.createGain();

        osc1.type = 'sine';
        osc1.frequency.setValueAtTime(659.25, now); // E5
        osc1.frequency.setValueAtTime(880.00, now + 0.12); // A5

        osc2.type = 'triangle';
        osc2.frequency.setValueAtTime(1318.50, now);
        osc2.frequency.setValueAtTime(1760.00, now + 0.12);

        gain.gain.setValueAtTime(0.001, now);
        gain.gain.linearRampToValueAtTime(0.35, now + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.65);

        osc1.connect(gain);
        osc2.connect(gain);
        gain.connect(ctx.destination);

        osc1.start(now);
        osc2.start(now);
        osc1.stop(now + 0.65);
        osc2.stop(now + 0.65);
    }

    function playFallbackAudio() {
        try {
            var url = generateChimeWavUrl();
            if (!url) return;
            var audio = new Audio(url);
            audio.volume = 0.65;
            var p = audio.play();
            if (p && typeof p.catch === 'function') {
                p.catch(function () {});
            }
        } catch (e) {}
    }

    function sound() {
        try {
            var ctx = getAudioContext();
            var played = false;

            if (ctx) {
                if (ctx.state === 'running') {
                    playWebAudioChime(ctx);
                    played = true;
                } else if (ctx.state === 'suspended') {
                    ctx.resume().then(function () {
                        playWebAudioChime(ctx);
                    }).catch(function () {
                        playFallbackAudio();
                    });
                    return;
                }
            }

            if (!played) {
                playFallbackAudio();
            }
        } catch (e) {
            playFallbackAudio();
        }
    }

    function unlockAudio() {
        try {
            var ctx = getAudioContext();
            if (ctx && ctx.state === 'suspended') {
                ctx.resume().catch(function () {});
            }
            if (!_chimeAudio) {
                var url = generateChimeWavUrl();
                if (url) {
                    _chimeAudio = new Audio(url);
                    _chimeAudio.volume = 0.01;
                    var p = _chimeAudio.play();
                    if (p && typeof p.then === 'function') {
                        p.then(function () {
                            _chimeAudio.pause();
                            _chimeAudio.currentTime = 0;
                            _chimeAudio.volume = 0.65;
                        }).catch(function () {});
                    }
                }
            }
        } catch (e) {}
    }

    ['click', 'touchstart', 'touchend', 'keydown', 'mousedown', 'pointerdown'].forEach(function (evt) {
        document.addEventListener(evt, unlockAudio, { passive: true, capture: true });
    });

    /* ------------------------------------------------------------------
     * Polling
     * ------------------------------------------------------------------ */

    /* Was this notification already in the feed before we started watching?
       Stale notifications older than 2 hours are suppressed on page load to
       avoid blasting old history, but any recent unread notification (e.g.
       marked Ready for Pickup while user was away or logging in) is shown. */
    function isPreBootBacklog(n) {
        if (!n.created_ts) return false;
        var created = Date.parse(n.created_ts);
        if (isNaN(created)) return false;
        var ageMs = Date.now() - created;
        // Suppress on first poll only if older than 2 hours
        return ageMs > 2 * 60 * 60 * 1000;
    }

    function poll() {
        // Never let a slow response stack up behind the next interval tick.
        if (_state.inFlight) return Promise.resolve();
        _state.inFlight = true;

        var controller = typeof AbortController !== 'undefined'
            ? new AbortController()
            : null;
        var timedOut = false;
        var timer = null;

        if (controller) {
            timer = setTimeout(function () {
                timedOut = true;
                try { controller.abort(); } catch (e) {}
            }, _state.requestTimeoutMs);
        }

        var opts = { cache: 'no-store' };
        if (controller) opts.signal = controller.signal;

        var fetchUrl = url('list') + '?_t=' + Date.now();
        try {
            var gk = localStorage.getItem('guest_session_key') || localStorage.getItem('qreserve_guest_key');
            if (gk) fetchUrl += '&guest_key=' + encodeURIComponent(gk);
        } catch (e) {}

        return fetch(fetchUrl, opts)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data || !data.success) return;

                var list = data.notifications || [];

                // render() reconciles by id, so an unchanged payload costs
                // nothing visually: no nodes are touched, no animation replays.
                render(list);
                updateBadge(data.unread_count || 0);

                var isFirstPoll = !_state.pollCount;
                _state.pollCount++;
                var bootToastsShown = 0;
                var MAX_BOOT_TOASTS = 2;

                list.forEach(function (n) {
                    var wasSeen = _state.seenIds[n.id];
                    _state.seenIds[n.id] = true;

                    // Read notifications never trigger a toast or chime
                    if (n.is_read) return;

                    // Session storage check: don't re-toast if already shown in this tab session
                    var toastedKey = 'qreserve_toasted_' + n.id;
                    var alreadyToasted = false;
                    try {
                        alreadyToasted = !!sessionStorage.getItem(toastedKey);
                    } catch (e) {}
                    if (alreadyToasted) return;

                    // If already seen in this in-memory polling session, do not re-toast
                    if (wasSeen) return;

                    // On the very first poll, show at most MAX_BOOT_TOASTS recent unread alerts
                    if (isFirstPoll) {
                        if (isPreBootBacklog(n)) return;
                        if (bootToastsShown >= MAX_BOOT_TOASTS) return;
                        bootToastsShown++;
                    }

                    // Mark as toasted in this session so it won't repeat on refresh
                    try {
                        sessionStorage.setItem(toastedKey, '1');
                    } catch (e) {}

                    // Fresh unread notification: pop out toast, play sound, show push
                    if (shouldToast(n.type)) {
                        toast(n);
                    }
                    showBrowserNotification(n.title, n.message);
                    sound();
                });

                _state.lastUnread = data.unread_count || 0;
            })
            .catch(function () {
                // Timeouts and network errors are expected; the next tick
                // retries. Never let one failure end the polling loop.
                if (timedOut && global.console) {
                    console.warn('[notifications] poll timed out, retrying');
                }
            })
            .then(function () {
                if (timer) clearTimeout(timer);
                // Reset unconditionally, including after an abort, so a hung
                // request can never wedge the poller for the whole session.
                _state.inFlight = false;
            });
    }

    /* ------------------------------------------------------------------
     * Boot
     * ------------------------------------------------------------------ */

    function init(options) {
        options = options || {};

        if (_state.timer) clearInterval(_state.timer);
        _state.pollMs = options.pollMs || POLL_MS_DEFAULT;
        _state.requestTimeoutMs = options.requestTimeoutMs || REQUEST_TIMEOUT_MS;

        // Optional overrides so one module can serve several dashboards.
        if (options.urls) {
            var defaults = {
                list: '/api/notifications',
                read: '/api/notifications/read',
                readAll: '/api/notifications/read-all',
                clear: '/api/notifications/clear',
                remove: function (id) { return '/api/notifications/' + id; }
            };
            _state.urls = {
                list: options.urls.list || defaults.list,
                read: options.urls.read || defaults.read,
                readAll: options.urls.readAll || defaults.readAll,
                clear: options.urls.clear || defaults.clear,
                remove: options.urls.remove || defaults.remove
            };
        }

        _state.toastTypes = options.toastTypes || null;

        var boot = function () {
            if (_state.booted) return;
            _state.booted = true;

            // Anything created after this instant is a live alert, not backlog.
            _state.bootAt = Date.now();

            var bell = byId('notificationBell');
            var dropdown = byId('notificationDropdown');
            var markAllBtn = byId('markAllRead');
            var clearBtn = byId('clearAllNotifications');

            if (bell && dropdown) {
                bell.addEventListener('click', function (e) {
                    e.stopPropagation();
                    dropdown.classList.toggle('show');
                    if (dropdown.classList.contains('show')) poll();
                });

                document.addEventListener('click', function (e) {
                    if (!dropdown.contains(e.target) && e.target !== bell) {
                        dropdown.classList.remove('show');
                    }
                });
            }

            if (markAllBtn) {
                markAllBtn.addEventListener('click', function (e) {
                    e.stopPropagation();
                    markAllRead();
                });
            }

            if (clearBtn) {
                clearBtn.addEventListener('click', function (e) {
                    e.stopPropagation();
                    clearAll();
                });
            }

            if (options.sound !== false) requestPermission();

            poll();
            _state.timer = setInterval(poll, _state.pollMs);

            /* Background tabs get their timers throttled hard (down to once
               per minute, and frozen entirely in some browsers), so anything
               that happened while the user was elsewhere can arrive many
               minutes late. Catch up the instant the tab comes back. */
            document.addEventListener('visibilitychange', function () {
                if (document.visibilityState === 'visible') poll();
            });
        };

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', boot);
        } else {
            boot();
        }

        return api;
    }

    var api = {
        TYPES: TYPES,
        init: init,
        poll: poll,
        render: render,
        toast: toast,
        label: label,
        dismiss: dismiss,
        clearAll: clearAll,
        markAllRead: markAllRead,
        sound: sound,
        unlockAudio: unlockAudio,
        requestPermission: requestPermission
    };

    global.QReserveNotifications = api;
})(window);