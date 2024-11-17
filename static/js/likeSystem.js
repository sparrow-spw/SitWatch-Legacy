document.addEventListener('DOMContentLoaded', function() {
    const actionButtons = document.querySelectorAll('.action-btn[data-action]');

    const activeButton = document.querySelector('.action-btn.active');
    if (activeButton) {
        activeButton.classList.add('active');
    }

    actionButtons.forEach(button => {
        button.addEventListener('click', async function() {
            if (!this.dataset.action || !this.dataset.videoId) return;

            try {
                const response = await fetch(`/video_action/${this.dataset.videoId}/${this.dataset.action}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    credentials: 'include'
                });

                if (!response.ok) {
                    if (response.status === 401) {
                        window.location.href = '/login';
                        return;
                    }
                    throw new Error(`HTTP hata! durum: ${response.status}`);
                }

                const data = await response.json();

                if (data.success) {
                    actionButtons.forEach(btn => btn.classList.remove('active'));

                    const currentAction = this.dataset.action;
                    const currentButton = document.querySelector(`.action-btn[data-action="${currentAction}"]`);
                    if (currentButton) {
                        currentButton.classList.add('active');
                    }

                    updateCounts(data);
                } else {
                    alert(data.message || 'Bir hata oluştu');
                }
            } catch (error) {
                console.error('Hata:', error);
                alert('İşlem sırasında bir hata oluştu. Lütfen oturum açtığınızdan emin olun.');
            }
        });
    });
});

function updateCounts(data) {
    const likeCount = document.querySelector('.button-like-count');
    if (likeCount) likeCount.textContent = data.likes || '0';

    const midLikeCount = document.querySelector('.button-mid-like-count');
    if (midLikeCount) midLikeCount.textContent = data.mid_likes || '0';

    const dislikeCount = document.querySelector('.button-dislike-count');
    if (dislikeCount) dislikeCount.textContent = data.dislikes || '0';
}