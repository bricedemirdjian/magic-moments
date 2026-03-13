/* ========================================
   SUBMAGIC CLONE - JavaScript
   ======================================== */

document.addEventListener('DOMContentLoaded', () => {
    // ---------- MOBILE NAV ----------
    const mobileToggle = document.getElementById('mobileToggle');
    const navLinks = document.getElementById('navLinks');

    if (mobileToggle) {
        mobileToggle.addEventListener('click', () => {
            mobileToggle.classList.toggle('active');
            navLinks.classList.toggle('active');
            document.body.style.overflow = navLinks.classList.contains('active') ? 'hidden' : '';
        });
    }

    // ---------- NAVBAR SCROLL ----------
    const navbar = document.querySelector('.navbar');
    let lastScroll = 0;

    window.addEventListener('scroll', () => {
        const currentScroll = window.scrollY;
        if (currentScroll > 100) {
            navbar.style.background = 'rgba(10, 10, 10, 0.95)';
        } else {
            navbar.style.background = 'rgba(10, 10, 10, 0.8)';
        }
        lastScroll = currentScroll;
    });

    // ---------- FAQ ACCORDION ----------
    const faqItems = document.querySelectorAll('.faq-item');

    faqItems.forEach(item => {
        const question = item.querySelector('.faq-question');
        const answer = item.querySelector('.faq-answer');

        question.addEventListener('click', () => {
            const isActive = item.classList.contains('active');

            // Close all
            faqItems.forEach(other => {
                other.classList.remove('active');
                other.querySelector('.faq-answer').style.maxHeight = '0';
            });

            // Open clicked if it was closed
            if (!isActive) {
                item.classList.add('active');
                answer.style.maxHeight = answer.scrollHeight + 'px';
            }
        });
    });

    // ---------- PRICING TOGGLE ----------
    const pricingToggle = document.getElementById('pricingToggle');
    const toggleLabels = document.querySelectorAll('.toggle-label');
    const monthlyPrices = document.querySelectorAll('.price.monthly');
    const yearlyPrices = document.querySelectorAll('.price.yearly');
    let isYearly = false;

    if (pricingToggle) {
        pricingToggle.addEventListener('click', () => {
            isYearly = !isYearly;
            pricingToggle.classList.toggle('active', isYearly);

            toggleLabels.forEach(label => {
                if (label.dataset.plan === 'yearly') {
                    label.classList.toggle('active', isYearly);
                } else {
                    label.classList.toggle('active', !isYearly);
                }
            });

            monthlyPrices.forEach(el => {
                el.style.display = isYearly ? 'none' : 'inline';
            });
            yearlyPrices.forEach(el => {
                el.style.display = isYearly ? 'inline' : 'none';
            });
        });

        // Also toggle on label click
        toggleLabels.forEach(label => {
            label.addEventListener('click', () => {
                const plan = label.dataset.plan;
                if ((plan === 'yearly' && !isYearly) || (plan === 'monthly' && isYearly)) {
                    pricingToggle.click();
                }
            });
        });
    }

    // ---------- SCROLL REVEAL ----------
    const revealElements = document.querySelectorAll(
        '.feature-card, .step-card, .usecase-card, .pricing-card, .faq-item, .section-header, .cta-stat'
    );

    revealElements.forEach(el => el.classList.add('reveal'));

    const revealObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                revealObserver.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    });

    revealElements.forEach(el => revealObserver.observe(el));

    // ---------- CAPTION WORD ANIMATION ----------
    const captionWords = document.querySelectorAll('.video-caption-demo .caption-word');
    if (captionWords.length > 0) {
        let activeIndex = 0;

        setInterval(() => {
            captionWords.forEach(w => w.classList.remove('active'));
            captionWords[activeIndex].classList.add('active');
            activeIndex = (activeIndex + 1) % captionWords.length;
        }, 800);
    }

    // ---------- SMOOTH SCROLL ----------
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href === '#') return;

            e.preventDefault();
            const target = document.querySelector(href);
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });

                // Close mobile nav
                if (navLinks.classList.contains('active')) {
                    mobileToggle.click();
                }
            }
        });
    });

    // ---------- DUPLICATE TESTIMONIALS FOR INFINITE SCROLL ----------
    const testimonialsTrack = document.querySelector('.testimonials-track');
    if (testimonialsTrack) {
        const cards = testimonialsTrack.innerHTML;
        testimonialsTrack.innerHTML = cards + cards;
    }

    // ---------- COUNTER ANIMATION ----------
    const statValues = document.querySelectorAll('.stat-value');

    const counterObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const el = entry.target;
                const text = el.textContent;
                el.style.opacity = '0';
                el.style.transform = 'translateY(10px)';

                setTimeout(() => {
                    el.style.transition = 'all 0.6s ease-out';
                    el.style.opacity = '1';
                    el.style.transform = 'translateY(0)';
                }, 200);

                counterObserver.unobserve(el);
            }
        });
    }, { threshold: 0.5 });

    statValues.forEach(el => counterObserver.observe(el));
});
