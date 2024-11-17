(function() {
    window.initializeEditModal = function() {
        const modal = document.getElementById('editVideoModal');
        if (modal) {
            modal.classList.add('show');
        }
    };

    window.closeEditModal = function() {
        const modal = document.getElementById('editVideoModal');
        if (modal) {
            modal.classList.remove('show');
        }
    };

    // Video silme fonksiyonu
    window.deleteVideo = function(videoId) {
        if (confirm('Bu videoyu silmek istediğinizden emin misiniz?')) {
            fetch(`/video/${videoId}/delete`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    window.location.href = '/';
                } else {
                    alert(data.error || 'Video silinirken bir hata oluştu.');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Video silinirken bir hata oluştu.');
            });
        }
    };

    document.addEventListener('DOMContentLoaded', function() {
        const editVideoForm = document.getElementById('editVideoForm');
        
        if (editVideoForm) {
            editVideoForm.addEventListener('submit', function(e) {
                e.preventDefault();
                const formData = new FormData(this);
                const videoId = formData.get('video_id');
                
                fetch(`/video/${videoId}/edit_video`, {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        location.reload();
                    } else {
                        alert(data.error || 'Video güncellenirken bir hata oluştu.');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Video güncellenirken bir hata oluştu: ' + error);
                });
            });
        }

        window.addEventListener('click', function(event) {
            const modal = document.getElementById('editVideoModal');
            if (event.target === modal) {
                window.closeEditModal();
            }
        });
    });
})();