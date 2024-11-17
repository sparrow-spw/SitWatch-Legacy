document.addEventListener('DOMContentLoaded', function() {
    // Modal elementlerini seç
    const reportModal = document.getElementById('reportModal');
    const reportForm = document.getElementById('reportForm');
    const reportButtons = document.querySelectorAll('.report-button');

    // Elementlerin varlığını kontrol et
    if (!reportModal || !reportForm) {
        console.error('Report modal veya form elementleri bulunamadı');
        return;
    }

    // Tüm report butonlarına event listener ekle
    reportButtons.forEach(button => {
        button.addEventListener('click', openReportModal);
    });

    // Modal dışına tıklanma kontrolü
    reportModal.addEventListener('click', function(e) {
        if (e.target === reportModal) {
            closeReportModal();
        }
    });

    // ESC tuşu kontrolü
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && !reportModal.classList.contains('hidden')) {
            closeReportModal();
        }
    });

    // Form gönderimi
    reportForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const submitButton = this.querySelector('button[type="submit"]');
        if (submitButton) submitButton.disabled = true;
        
        try {
            const formData = new FormData(this);
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

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                closeReportModal();
                this.reset();
            } else {
                alert(data.message || 'Bildirim gönderilirken bir hata oluştu.');
            }
        } catch (error) {
            console.error('Hata:', error);
            alert('Bildirim gönderilirken bir hata oluştu. Lütfen daha sonra tekrar deneyin.');
        } finally {
            if (submitButton) submitButton.disabled = false;
        }
    });
}); 