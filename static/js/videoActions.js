document.addEventListener('DOMContentLoaded', function() {
    // Modal elementlerini seç
    const reportModal = document.getElementById('reportModal');
    const reportForm = document.getElementById('reportForm');

    // Global fonksiyonları tanımla
    window.showReportModal = function() {
        if (reportModal) {
            reportModal.classList.remove('hidden');
        }
    };

    window.closeReportModal = function() {
        if (reportModal) {
            reportModal.classList.add('hidden');
        }
    };

    // Form submit işleyicisi
    if (reportForm) {
        reportForm.addEventListener('submit', async function(event) {
            event.preventDefault();
            
            const formData = new FormData(this);
            
            try {
                const response = await fetch('/report_video', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({
                        video_id: formData.get('video_id'),
                        reason: formData.get('reason'),
                        description: formData.get('description')
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert('Bildiriminiz başarıyla alındı. İncelemeye alınacaktır.');
                    closeReportModal();
                    this.reset();
                } else {
                    alert(data.message || 'Bildirim gönderilirken bir hata oluştu.');
                }
            } catch (error) {
                console.error('Hata:', error);
                alert('Bildirim gönderilirken bir hata oluştu.');
            }
        });
    }

    // Modal dışına tıklandığında kapatma
    window.onclick = function(event) {
        if (event.target === reportModal) {
            closeReportModal();
        }
    };
}); 