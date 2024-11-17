const chatContainer = document.getElementById('chat-container');
const chatHeader = document.getElementById('chat-header');
const chatBody = document.getElementById('chat-body');
const onlineUsers = document.getElementById('online-users');
const chatMessages = document.getElementById('chat-messages');
const messageInput = document.getElementById('message-input');
const toggleChat = document.getElementById('toggle-chat');

let isChatOpen = true;
let currentRecipientId = null;

toggleChat.addEventListener('click', () => {
    isChatOpen = !isChatOpen;
    chatBody.style.display = isChatOpen ? 'flex' : 'none';
    toggleChat.textContent = isChatOpen ? '▲' : '▼';
});

function loadOnlineUsers() {
    fetch('/get_online_users')
        .then(response => response.json())
        .then(users => {
            onlineUsers.innerHTML = '';
            users.forEach(user => {
                const userElement = document.createElement('div');
                userElement.textContent = user.username;
                userElement.onclick = () => startChat(user.id, user.username);
                onlineUsers.appendChild(userElement);
            });
        });
}

function startChat(userId, username) {
    currentRecipientId = userId;
    chatMessages.innerHTML = '';
    loadMessages();
}

function loadMessages() {
    if (!currentRecipientId) return;

    fetch(`/get_messages/${currentRecipientId}`)
        .then(response => response.json())
        .then(messages => {
            chatMessages.innerHTML = '';
            messages.forEach(message => {
                const messageElement = document.createElement('div');
                messageElement.textContent = `${message.sender_id === currentRecipientId ? 'Onlar' : 'Sen'}: ${message.content}`;
                chatMessages.appendChild(messageElement);
            });
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });
}

messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && currentRecipientId) {
        const message = messageInput.value.trim();
        if (message) {
            fetch('/send_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `recipient_id=${currentRecipientId}&content=${encodeURIComponent(message)}`
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    messageInput.value = '';
                    loadMessages();
                }
            });
        }
    }
});

setInterval(loadMessages, 5000); // Her 5 saniyede bir mesajları güncelle
loadOnlineUsers();
