// Vacation Rental Booking System — main.js

// Auto-dismiss flash messages after 5 seconds
document.addEventListener('DOMContentLoaded', () => {
    const flashes = document.querySelectorAll('.flash');
    flashes.forEach(flash => {
        setTimeout(() => {
            flash.style.transition = 'opacity 0.4s';
            flash.style.opacity = '0';
            setTimeout(() => flash.remove(), 400);
        }, 5000);
    });
});

// Make table rows with data-href clickable (links/buttons inside still work)
document.addEventListener('click', (e) => {
    const row = e.target.closest('tr[data-href]');
    if (!row) return;
    if (e.target.closest('a, button, input, select, label, form')) return;
    window.location = row.dataset.href;
});
