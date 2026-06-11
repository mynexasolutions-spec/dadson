// ==================== CART MANAGEMENT ====================
const cartCountBadge = document.querySelector('.cart-count');
const wishlistCountBadge = document.querySelector('.wishlist-count');

// Add to cart logic
document.addEventListener('click', function(e) {
    if (e.target && e.target.classList.contains('add-to-cart-ajax')) {
        e.preventDefault();
        const btn = e.target;
        const productId = btn.getAttribute('data-id');

        if (productId) {
            const originalText = btn.textContent;
            btn.textContent = 'Adding...';
            btn.disabled = true;

            // Extract details for GA4
            const card = btn.closest('.product-card');
            let name = '';
            let price = 0;
            let category = '';
            if (card) {
                const nameEl = card.querySelector('.product-name');
                const priceEl = card.querySelector('.product-price');
                const catEl = card.querySelector('.product-category');
                name = nameEl ? nameEl.textContent.trim() : '';
                price = priceEl ? parseFloat(priceEl.textContent.replace(/[^0-9.]/g, '')) || 0 : 0;
                category = catEl ? catEl.textContent.trim() : '';
            }

            fetch(`/add-to-cart/${productId}`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    if (cartCountBadge) cartCountBadge.textContent = data.cart_count;
                    btn.textContent = '✓ Added';
                    btn.style.backgroundColor = '#10b981';
                    
                    // GA4 Track Add to Cart
                    if (typeof gtag !== 'undefined') {
                        gtag('event', 'add_to_cart', {
                            currency: 'INR',
                            value: price,
                            items: [{
                                item_id: productId,
                                item_name: name,
                                item_category: category,
                                price: price,
                                quantity: 1
                            }]
                        });
                    }
                    
                    setTimeout(() => {
                        btn.textContent = originalText;
                        btn.style.backgroundColor = '';
                        btn.disabled = false;
                    }, 2000);
                } else if (data.redirect) {
                    window.location.href = data.redirect;
                } else {
                    alert(data.message || 'Error adding product.');
                    btn.textContent = originalText;
                    btn.style.backgroundColor = '';
                    btn.disabled = false;
                }
            })
            .catch(err => {
                console.error('Cart Error:', err);
                btn.textContent = 'Error';
                btn.style.backgroundColor = '#ef4444';
                setTimeout(() => {
                    btn.textContent = originalText;
                    btn.style.backgroundColor = '';
                    btn.disabled = false;
                }, 2000);
            });
        }
    }
});

// ==================== BUY NOW ====================
document.addEventListener('click', function(e) {
    var btn = e.target.closest('.buy-now-ajax');
    if (!btn) return;
    e.preventDefault();

    var productId = btn.getAttribute('data-id');
    if (!productId) return;

    var originalHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin" style="margin-right:6px;font-size:0.85em;"></i>Please wait...';

    fetch('/add-to-cart/' + productId, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(function(res) { return res.json(); })
    .then(function(data) {
        if (data.success) {
            // Update cart badge then go straight to checkout
            var badge = document.getElementById('cartBadge') || document.querySelector('.cart-count');
            if (badge) badge.textContent = data.cart_count;
            window.location.href = '/checkout';
        } else if (data.redirect) {
            // Variable product — needs variant selection on product page
            window.location.href = data.redirect;
        } else {
            alert(data.message || 'Could not process. Please try again.');
            btn.innerHTML = originalHTML;
            btn.disabled = false;
        }
    })
    .catch(function() {
        btn.innerHTML = originalHTML;
        btn.disabled = false;
    });
});

// ==================== WISHLIST MANAGEMENT ====================
window.toggleWishlist = function(e, productId) {
    if (e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    const btn = e ? (e.currentTarget || e.target.closest('.product-wishlist') || e.target.closest('.btn-wish-circle-premium')) : null;
    if (!btn) return;
    const img = btn.querySelector('img');
    
    // Extract details for GA4 if adding to wishlist
    const card = btn.closest('.product-card');
    let name = '';
    let price = 0;
    let category = '';
    if (card) {
        const nameEl = card.querySelector('.product-name');
        const priceEl = card.querySelector('.product-price');
        const catEl = card.querySelector('.product-category');
        name = nameEl ? nameEl.textContent.trim() : '';
        price = priceEl ? parseFloat(priceEl.textContent.replace(/[^0-9.]/g, '')) || 0 : 0;
        category = catEl ? catEl.textContent.trim() : '';
    }
    
    fetch(`/toggle-wishlist/${productId}`, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            if (wishlistCountBadge) wishlistCountBadge.textContent = data.wishlist_count;
            
            if (data.action === 'added') {
                btn.classList.add('active');
                if (img) img.src = 'https://api.iconify.design/ph:heart-fill.svg?color=%23b88a44';
                
                // GA4 Track Add to Wishlist
                if (typeof gtag !== 'undefined') {
                    gtag('event', 'add_to_wishlist', {
                        currency: 'INR',
                        value: price,
                        items: [{
                            item_id: productId,
                            item_name: name,
                            item_category: category,
                            price: price,
                            quantity: 1
                        }]
                    });
                }
            } else {
                btn.classList.remove('active');
                if (img) img.src = 'https://api.iconify.design/ph:heart-bold.svg?color=%23b88a44';
            }
        }
    })
    .catch(err => console.error('Wishlist Error:', err));
};

// ==================== DROPDOWN MENU ====================
document.querySelectorAll(".dropdown-trigger").forEach((trigger) => {
  trigger.addEventListener("click", function (e) {
    // If click is on a dropdown item link, let the navigation proceed
    if (e.target.closest(".dropdown-item")) {
      return;
    }
    e.preventDefault();
    this.classList.toggle("active");
  });
});

// Close dropdown when clicking outside
document.addEventListener("click", function (e) {
  document.querySelectorAll(".dropdown-trigger").forEach((trigger) => {
    if (!trigger.contains(e.target)) {
      trigger.classList.remove("active");
    }
  });
});

document.addEventListener(
  "click",
  function (e) {
    if (navLinks && mobileMenuBtn && navLinks.classList.contains("show")) {
      if (!navLinks.contains(e.target) && !mobileMenuBtn.contains(e.target)) {
        navLinks.classList.remove("show");
        mobileMenuBtn.classList.remove("active");
        document.body.classList.remove("menu-open");
      }
    }
  },
  true,
);

// ==================== NEWSLETTER FORM ====================
const newsletterForm = document.getElementById('newsletter-form');
if (newsletterForm) {
    newsletterForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const input = this.querySelector('input');
        const button = this.querySelector('.btn');
        const email = input.value;
        
        if (email) {
            const originalText = button.textContent;
            button.textContent = 'Subscribing...';
            button.disabled = true;

            try {
                const response = await fetch('/api/subscribe', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ email: email }),
                });

                const result = await response.json();

                if (result.success) {
                    button.textContent = '✓ Subscribed!';
                    button.style.backgroundColor = '#10b981';
                    input.value = '';
                    
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.style.backgroundColor = '';
                        button.disabled = false;
                    }, 3000);
                } else {
                    throw new Error(result.message || 'Subscription failed');
                }
            } catch (error) {
                console.error('Newsletter Error:', error);
                button.textContent = 'Error!';
                button.style.backgroundColor = '#ef4444';
                
                setTimeout(() => {
                    button.textContent = originalText;
                    button.style.backgroundColor = '';
                    button.disabled = false;
                }, 3000);
            }
        }
    });
}

// ==================== SMOOTH SCROLL FOR LINKS ====================
document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', function(e) {
        const href = this.getAttribute('href');
        if (href !== '#') {
            e.preventDefault();
            const target = document.querySelector(href);
            if (target) {
                target.scrollIntoView({ behavior: 'smooth' });
            }
        }
    });
});

// ==================== SCROLL ANIMATIONS ====================
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -100px 0px'
};

const observer = new IntersectionObserver(function(entries) {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

// Observe all sections for fade-in animation
document.querySelectorAll('section').forEach(section => {
    section.classList.add('reveal');
    observer.observe(section);
});

// ==================== MOBILE MENU ====================
const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
const navLinks = document.querySelector('.nav-links');

if (mobileMenuBtn) {
  mobileMenuBtn.addEventListener("click", function (e) {
    e.stopPropagation();
    this.classList.toggle("active");
    if (navLinks) {
      if (!navLinks._movedToBody) {
        document.body.appendChild(navLinks);
        navLinks._movedToBody = true;
      }
      navLinks.classList.toggle("show");
      document.body.classList.toggle(
        "menu-open",
        navLinks.classList.contains("show"),
      );
    }
  });
}

// Close mobile menu when clicking on a link
if (navLinks) {
    navLinks.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', function(e) {
            // Do NOT close mobile menu if clicking a parent submenu link on mobile/tablet viewports
            if (window.innerWidth <= 1024 && this.closest('.dropdown-item-with-submenu') && this.nextElementSibling && this.nextElementSibling.classList.contains('submenu')) {
                return;
            }
            mobileMenuBtn.classList.remove('active');
            navLinks.classList.remove('show');
            document.body.classList.remove('menu-open');
        });
    });
}

// ==================== NAVBAR STICKY EFFECT ====================
const navbar = document.querySelector('.navbar');
window.addEventListener('scroll', function() {
    if (window.scrollY > 50) {
        navbar.style.boxShadow = '0 2px 10px rgba(0,0,0,0.1)';
    } else {
        navbar.style.boxShadow = 'none';
    }
});

// ==================== FEATURE CARD ANIMATION ====================
document.querySelectorAll('.feature-card').forEach((card, index) => {
    card.style.opacity = '0';
    card.style.animation = `slideInUp 0.6s ease forwards`;
    card.style.animationDelay = `${index * 0.1}s`;
});

// Add animation keyframes dynamically
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInUp {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    @keyframes pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.1); }
    }
    
    .dropdown-trigger.active .dropdown-menu {
        opacity: 1 !important;
        visibility: visible !important;
        transform: translateY(0) !important;
    }

    .wishlist-count, .cart-count {
        position: absolute;
        top: -5px;
        right: -5px;
        background: #d4af37;
        color: #1a1a1a;
        font-size: 10px;
        font-weight: 700;
        width: 16px;
        height: 16px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .wishlist-toggle.active svg {
        fill: #ef4444;
        stroke: #ef4444;
    }
    
    .product-card-top {
        position: relative;
    }
    
    .wishlist-toggle {
        position: absolute;
        top: 15px;
        right: 15px;
        background: white;
        border: none;
        width: 35px;
        height: 35px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        transition: all 0.3s;
        z-index: 2;
    }
    
    .wishlist-toggle:hover {
        transform: scale(1.1);
    }
`;
document.head.appendChild(style);

// ==================== PRODUCT IMAGE LAZY LOADING ====================
if ('IntersectionObserver' in window) {
    const imageObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src || img.src;
                imageObserver.unobserve(img);
            }
        });
    });
    
    document.querySelectorAll('img[data-src]').forEach(img => {
        imageObserver.observe(img);
    });
}

// ==================== SEARCH FUNCTIONALITY ====================
const searchInline = document.getElementById('searchInline');
const searchInlineInput = document.getElementById('searchInlineInput');
const searchInlineCloseBtn = document.getElementById('searchInlineCloseBtn');

document.querySelectorAll('.search-btn').forEach(btn => {
    btn.addEventListener('click', function(e) {
        e.preventDefault();
        if (searchInline) {
            searchInline.classList.add('active');
            if (searchInlineInput) {
                searchInlineInput.value = ''; // Start afresh, clear previous search text
                searchInlineInput.focus();
            }
        }
    });
});

if (searchInlineCloseBtn) {
    searchInlineCloseBtn.addEventListener('click', function() {
        if (searchInline) {
            searchInline.classList.remove('active');
        }
    });
}

// Close search inline with Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && searchInline && searchInline.classList.contains('active')) {
        searchInline.classList.remove('active');
    }
});

// Close search inline when clicking outside
document.addEventListener('click', function(e) {
    if (searchInline && searchInline.classList.contains('active')) {
        const navbarCenter = document.querySelector('.navbar-center');
        const isClickInside = navbarCenter && navbarCenter.contains(e.target);
        const isSearchBtnClick = e.target.closest('.search-btn');
        if (!isClickInside && !isSearchBtnClick) {
            searchInline.classList.remove('active');
        }
    }
});

// ==================== TOUCH DEVICE DETECTION ====================
const isTouchDevice = () => {
    return (('ontouchstart' in window) ||
            (navigator.maxTouchPoints > 0) ||
            (navigator.msMaxTouchPoints > 0));
};

// Adjust hover effects for touch devices
if (isTouchDevice()) {
    document.querySelectorAll('.product-card, .category-card, .feature-card').forEach(card => {
        card.style.cursor = 'pointer';
    });
}

// ==================== KEYBOARD NAVIGATION ====================
document.addEventListener('keydown', function(e) {
    // Close dropdown with Escape
    if (e.key === 'Escape') {
        document.querySelectorAll('.dropdown-trigger').forEach(trigger => {
            trigger.classList.remove('active');
        });
    }
});

// ==================== PERFORMANCE: DEBOUNCE SCROLL ====================
let scrollTimeout;
window.addEventListener('scroll', function() {
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(function() {
        // Perform expensive operations here if needed
    }, 150);
}, { passive: true });

// ==================== INITIALIZE ====================
document.addEventListener('DOMContentLoaded', function() {
    console.log('DADSON jewelry website loaded successfully.');
    
    // Add focus indicators for accessibility
    document.querySelectorAll('button, a').forEach(element => {
        element.addEventListener('focus', function() {
            this.style.outline = `2px solid #d4af37`;
            this.style.outlineOffset = '2px';
        });
        
        element.addEventListener('blur', function() {
            this.style.outline = 'none';
        });
    });

    // Mobile submenu accordion toggling was removed to allow direct navigation to categories on mobile.
});

// ==================== ERROR HANDLING ====================
window.addEventListener('error', function(e) {
    console.error('Error occurred:', e.error);
});

// ==================== UTILITY FUNCTIONS ====================
function formatPrice(price) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR'
    }).format(price);
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        background: ${type === 'success' ? '#10b981' : '#3b82f6'};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 9999;
        animation: slideIn 0.3s ease;
    `;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

function updateCartCount(count) {
    if (cartCountBadge) cartCountBadge.textContent = count;
}

// Export functions for external use
window.dadson = {
    formatPrice,
    showNotification,
    updateCartCount
};
// ==================== FAQ ACCORDION ====================
document.querySelectorAll('.faq-question').forEach(button => {
    button.addEventListener('click', () => {
        const faqItem = button.parentElement;
        
        // Toggle active class on current item
        faqItem.classList.toggle('active');
        
        // Optional: Close other items when one is opened
        document.querySelectorAll('.faq-item').forEach(otherItem => {
            if (otherItem !== faqItem) {
                otherItem.classList.remove('active');
            }
        });
    });
});
