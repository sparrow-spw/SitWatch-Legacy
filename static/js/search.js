document.addEventListener('DOMContentLoaded', function() {
    // Arama türü değiştirme
    const searchTypeLinks = document.querySelectorAll('.search-type-link');
    searchTypeLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const type = this.textContent.toLowerCase();
            const currentUrl = new URL(window.location.href);
            currentUrl.searchParams.set('type', type);
            window.location.href = currentUrl.toString();
        });
    });

    // Sıralama değiştirme
    const sortSelect = document.getElementById('sort-select');
    sortSelect.addEventListener('change', function() {
        const currentUrl = new URL(window.location.href);
        currentUrl.searchParams.set('sort', this.value);
        window.location.href = currentUrl.toString();
    });
}); 