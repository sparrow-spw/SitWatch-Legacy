document.addEventListener('DOMContentLoaded', function() {

    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('reply-btn')) {
            const commentId = e.target.dataset.commentId;
            const commentDiv = document.getElementById(`comment-${commentId}`);

            const existingForm = commentDiv.querySelector('.reply-form');
            if (existingForm) {
                existingForm.remove();
                return;
            }

            const replyForm = document.createElement('div');
            replyForm.className = 'reply-form mt-3 ml-8';
            replyForm.innerHTML = `
                <div class="flex gap-3">
                    <img src="${current_user.profile_image}" alt="${current_user.username}" class="w-8 h-8 rounded-full">
                    <div class="flex-1">
                        <textarea class="w-full min-h-[80px] p-2 border border-[#e8e8e8] text-[12px] focus:outline-none focus:border-[#167ac6]" 
                                placeholder="Yanıtınızı yazın..."></textarea>
                        <div class="mt-2">
                            <button class="submit-reply-btn bg-[#167ac6] text-white text-[12px] px-4 py-2 hover:bg-[#2793e6] mr-2">
                                Yanıtla
                            </button>
                            <button class="cancel-reply-btn text-[12px] text-[#666] hover:text-[#333]">
                                İptal
                            </button>
                        </div>
                    </div>
                </div>
            `;

            const repliesContainer = commentDiv.querySelector('.replies-container');
            repliesContainer.insertBefore(replyForm, repliesContainer.firstChild);

            replyForm.querySelector('.cancel-reply-btn').addEventListener('click', function() {
                replyForm.remove();
            });

            replyForm.querySelector('.submit-reply-btn').addEventListener('click', async function() {
                const content = replyForm.querySelector('textarea').value.trim();
                if (!content) return;

                try {
                    const formData = new FormData();
                    formData.append('content', content);

                    const response = await fetch(`/api/comments/${commentId}/reply`, {
                        method: 'POST',
                        body: formData,
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest'
                        }
                    });

                    const data = await response.json();

                    if (data.success && data.reply) {

                        replyForm.remove();

                        const replyElement = createReplyElement(data.reply);
                        repliesContainer.insertBefore(replyElement, repliesContainer.firstChild);
                    } else {
                        alert(data.error || 'Yanıt eklenirken bir hata oluştu');
                    }
                } catch (error) {
                    console.error('Hata:', error);
                    alert('Yanıt gönderilirken bir hata oluştu');
                }
            });
        }
    });
});

function createReplyElement(reply) {
    const div = document.createElement('div');
    div.id = `comment-${reply.id}`;
    div.className = 'reply mb-3';
    div.innerHTML = `
        <div class="flex gap-3">
            <img src="/static/profile_images/${reply.user_avatar}" alt="${reply.username}" class="w-8 h-8 rounded-full">
            <div class="flex-1">
                <div class="comment-header">
                    <a href="/profile/${reply.username}" class="font-bold text-[13px] text-[#065fd4] hover:underline">
                        ${reply.username}
                    </a>
                    <span class="text-[11px] text-[#606060] ml-2">
                        ${reply.created_at}
                    </span>
                    ${reply.is_edited ? '<span class="comment-edited text-[11px] text-[#606060] ml-2">(düzenlendi)</span>' : ''}
                </div>
                <p class="comment-text text-[13px] text-[#333] mt-1">${reply.content}</p>
                <div class="comment-actions mt-2">
                    ${reply.can_edit ? `
                        <button class="edit-comment-btn text-[11px] text-[#606060] hover:text-[#065fd4] mr-2"
                                data-comment-id="${reply.id}">
                            Düzenle
                        </button>
                    ` : ''}
                    ${reply.can_delete ? `
                        <button class="delete-comment-btn text-[11px] text-[#606060] hover:text-[#e62117]"
                                data-comment-id="${reply.id}">
                            Sil
                        </button>
                    ` : ''}
                </div>
            </div>
        </div>
    `;
    return div;
}