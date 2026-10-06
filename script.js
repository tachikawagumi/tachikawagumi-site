// ===========================
// Smooth Scrolling & Navigation
// ===========================

// Smooth scroll on navigation link click
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// ===========================
// Mobile Menu (if needed in future)
// ===========================

// Function to handle responsive behavior
function handleResponsive() {
    const header = document.querySelector('.header');
    if (window.innerWidth <= 768) {
        // Mobile optimizations can go here
    }
}

window.addEventListener('resize', handleResponsive);
handleResponsive();

// ===========================
// Analytics & Tracking
// ===========================

// Track button clicks
document.querySelectorAll('.btn').forEach(btn => {
    btn.addEventListener('click', function() {
        console.log('Button clicked:', this.textContent);
        // Add your analytics tracking here
    });
});

// ===========================
// Phone Link Handler
// ===========================

// Ensure phone links work properly on mobile
document.querySelectorAll('a[href^="tel:"]').forEach(link => {
    link.addEventListener('click', function(e) {
        // Allow default behavior on mobile devices
        if (!/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)) {
            // On desktop, prevent default and show a message
            e.preventDefault();
            const phone = this.getAttribute('href').replace('tel:', '');
            alert(`お電話いただく場合は以下の番号までお願いします:\n\n${phone}`);
        }
    });
});

// ===========================
// Email Link Handler
// ===========================

// Email links work by default, but we can add tracking
document.querySelectorAll('a[href^="mailto:"]').forEach(link => {
    link.addEventListener('click', function() {
        console.log('Email link clicked:', this.getAttribute('href'));
        // Add your analytics tracking here
    });
});

// ===========================
// Service Cards Animation
// ===========================

// Add intersection observer for scroll animations
if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1
    });

    document.querySelectorAll('.service-card').forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(card);
    });
}

// ===========================
// Scroll to Top Button (optional enhancement)
// ===========================

const scrollToTopButton = document.createElement('button');
scrollToTopButton.id = 'scroll-to-top';
scrollToTopButton.innerHTML = '↑';
scrollToTopButton.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    background-color: #f39c12;
    color: white;
    border: none;
    padding: 10px 15px;
    border-radius: 4px;
    cursor: pointer;
    display: none;
    z-index: 99;
    font-size: 20px;
    font-weight: bold;
    transition: all 0.3s;
`;

document.body.appendChild(scrollToTopButton);

window.addEventListener('scroll', () => {
    if (window.pageYOffset > 300) {
        scrollToTopButton.style.display = 'block';
    } else {
        scrollToTopButton.style.display = 'none';
    }
});

scrollToTopButton.addEventListener('click', () => {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
});

scrollToTopButton.addEventListener('mouseover', function() {
    this.style.backgroundColor = '#e67e22';
    this.style.transform = 'scale(1.1)';
});

scrollToTopButton.addEventListener('mouseout', function() {
    this.style.backgroundColor = '#f39c12';
    this.style.transform = 'scale(1)';
});

// ===========================
// Cloudflare Pages Detection
// ===========================

// Log deployment info for debugging
console.log('Website loaded successfully');
if (typeof fetch !== 'undefined') {
    console.log('Environment: Supports modern fetch API');
}

// ===========================
// Document Ready
// ===========================

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded - Site initialization complete');
    // Additional initialization can go here
});