/**
 * QRESERVE - Ultra-Smooth Animations, Transitions & Delays
 * Handles:
 * 1. Smooth page entrance and exit transitions with subtle delay when changing HTMLs.
 * 2. Animated tab switching with smooth delay when changing tabs within dashboard & pages.
 * 3. Fluid top progress bar simulation.
 */

(function () {
    // 1. Setup Top Progress Bar
    let progressBar = document.getElementById('qreserve-top-progress');
    if (!progressBar) {
        progressBar = document.createElement('div');
        progressBar.id = 'qreserve-top-progress';
        document.documentElement.appendChild(progressBar);
    }

    function startProgress() {
        if (!progressBar) return;
        progressBar.classList.remove('finish');
        progressBar.classList.add('active');
    }

    function finishProgress() {
        if (!progressBar) return;
        progressBar.classList.add('finish');
        setTimeout(() => {
            progressBar.classList.remove('active', 'finish');
            progressBar.style.width = '0%';
        }, 300);
    }

    // 2. Page Entrance Transition
    window.addEventListener('DOMContentLoaded', function () {
        // Quick progress flash on load
        startProgress();
        setTimeout(finishProgress, 260);

        // Initialize Tab Switching on pages that have tab panes
        initTabSwitching();
    });

    // Handle BFCache (back/forward button navigation)
    window.addEventListener('pageshow', function (e) {
        document.querySelectorAll('.page-is-exiting').forEach(el => {
            el.classList.remove('page-is-exiting');
        });
        document.body.classList.remove('page-is-exiting-full');
        finishProgress();
    });

    // 3. Smooth Page Exit Transition & Delay when Changing HTMLs
    document.addEventListener('click', function (e) {
        const link = e.target.closest('a');
        if (!link) return;

        const href = link.getAttribute('href');
        if (!href) return;

        // Skip non-navigating links or special links
        if (
            href === '#' ||
            href.startsWith('#') ||
            href.startsWith('javascript:') ||
            href.startsWith('mailto:') ||
            href.startsWith('tel:') ||
            link.getAttribute('target') === '_blank' ||
            link.getAttribute('download') !== null ||
            e.ctrlKey || e.metaKey || e.shiftKey || e.altKey
        ) {
            return;
        }

        // If link is data-tab or tab switch link, don't navigate HTML
        if (link.hasAttribute('data-tab-target')) {
            return;
        }

        // This is a real HTML navigation!
        e.preventDefault();

        // Visual feedback on clicked item
        link.classList.add('tab-switching-pulse');

        // Start top progress sweep
        startProgress();

        // If navigating to logout or exit guest, fade whole body
        const isLogout = href.includes('logout') || href.includes('login');
        if (isLogout) {
            document.body.classList.add('page-is-exiting-full');
        } else {
            // Otherwise, target content: keeps sidebar solid, glides content
            const contentTarget = document.querySelector('.content, .intro-card, .profile-card, .dashboard-content') ||
                                  document.querySelector('.main') ||
                                  document.body;
            contentTarget.classList.add('page-is-exiting');
        }

        // Silky transition delay before navigating (tuned to 250ms for smooth completion)
        const TRANSITION_DELAY_MS = 250;
        setTimeout(() => {
            window.location.href = href;
        }, TRANSITION_DELAY_MS);
    });

    // 4. Smooth Tab Switching with Transition & Delay (Changing Tabs)
    function initTabSwitching() {
        const tabLinks = document.querySelectorAll('[data-tab-target]');
        if (!tabLinks.length) return;

        tabLinks.forEach(link => {
            link.addEventListener('click', function (e) {
                e.preventDefault();

                const targetId = this.getAttribute('data-tab-target');
                const targetPane = document.getElementById(targetId);
                if (!targetPane) return;

                // If already active, do nothing
                if (this.classList.contains('active') && targetPane.classList.contains('active')) {
                    return;
                }

                // Visual click pulse on the tab item
                this.classList.add('tab-switching-pulse');
                setTimeout(() => this.classList.remove('tab-switching-pulse'), 300);

                // Update sidebar active link
                tabLinks.forEach(l => l.classList.remove('active'));
                this.classList.add('active');

                // Animate current active pane out smoothly
                const currentActivePane = document.querySelector('.tab-pane-animated.active');
                
                // Show brief top progress indicator
                startProgress();

                // Smooth delay: allows outgoing tab to glide out smoothly before incoming tab glides in
                const TAB_SWITCH_DELAY = 160;

                if (currentActivePane && currentActivePane !== targetPane) {
                    currentActivePane.classList.add('tab-exiting');
                    
                    setTimeout(() => {
                        currentActivePane.classList.remove('active', 'tab-exiting');
                        targetPane.classList.add('active');
                        finishProgress();
                    }, TAB_SWITCH_DELAY);
                } else {
                    targetPane.classList.add('active');
                    finishProgress();
                }

                // Update URL hash smoothly without jump
                if (history.replaceState) {
                    history.replaceState(null, null, '#' + targetId.replace('tab-', ''));
                }
            });
        });

        // Check if URL has hash (e.g. #my-queue, #announcements)
        const hash = window.location.hash.replace('#', '');
        if (hash) {
            const matchedLink = document.querySelector(`[data-tab-target="tab-${hash}"]`);
            if (matchedLink) {
                matchedLink.click();
            }
        }
    }

    // Expose utility for programmatic tab switching
    window.QReserve = window.QReserve || {};
    window.QReserve.switchTab = function (tabName) {
        const link = document.querySelector(`[data-tab-target="tab-${tabName}"]`);
        if (link) link.click();
    };
})();
