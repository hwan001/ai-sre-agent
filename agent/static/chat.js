/**
 * SRE AI Team - Modern Chat Interface
 */

class ChatApp {
    constructor() {
        this.ws = null;
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.messagesDiv = document.getElementById('messages');
        this.connectionStatus = document.getElementById('connectionStatus');
        this.typingIndicator = document.getElementById('typingIndicator');
        this.activeAgents = new Set();
        this.isFirstMessage = true;
        this.lastMessageContent = null; // Track last message to avoid duplicates
        
        this.initEventListeners();
        this.connect();
    }
    
    initEventListeners() {
        this.sendButton.addEventListener('click', () => this.sendMessage());
        
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        this.messageInput.addEventListener('input', (e) => {
            e.target.style.height = 'auto';
            e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
        });
        
        document.querySelectorAll('.quick-q').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const query = e.target.getAttribute('data-query');
                if (query) {
                    this.messageInput.value = query;
                    this.sendMessage();
                }
            });
        });
    }
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        this.updateConnectionStatus('connecting', 'Connecting...');
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('✅ Connected');
            this.updateConnectionStatus('connected', 'Connected');
        };
        
        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (error) {
                console.error('Error:', error);
            }
        };
        
        this.ws.onclose = () => {
            this.updateConnectionStatus('disconnected', 'Disconnected');
            this.hideTypingIndicator();
            setTimeout(() => this.connect(), 5000);
        };
    }
    
    sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message) return;
        
        if (this.isFirstMessage) {
            const welcomeMsg = document.querySelector('.welcome-message');
            if (welcomeMsg) {
                welcomeMsg.style.transition = 'all 0.3s ease';
                welcomeMsg.style.opacity = '0';
                welcomeMsg.style.transform = 'translateY(-20px)';
                setTimeout(() => welcomeMsg.remove(), 300);
            }
            this.isFirstMessage = false;
        }
        
        this.addUserMessage(message);
        
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'chat',
                message: message
            }));
            this.showTypingIndicator();
        }
        
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';
        this.messageInput.focus();
    }
    
    handleMessage(data) {
        console.log('Received:', data.type, data);
        
        switch(data.type) {
            case 'chat_start':
                this.showTypingIndicator();
                this.lastMessageContent = null; // Reset for new conversation
                break;
                
            case 'agent_message':
                // Skip 'User' agent messages (these are internal)
                if (data.agent === 'User' || data.agent === 'user') {
                    console.log('Skipping User agent message');
                    break;
                }
                // Skip duplicate messages
                if (this.lastMessageContent === data.message) {
                    console.log('Skipping duplicate message from', data.agent);
                    break;
                }
                this.lastMessageContent = data.message;
                this.hideTypingIndicator();
                this.addAgentMessage(data.agent, data.message);
                this.activateAgent(data.agent);
                break;
                
            case 'agent_thinking':
                // Show thinking messages as agent messages
                if (this.lastMessageContent === data.message) {
                    console.log('Skipping duplicate thinking message');
                    break;
                }
                this.lastMessageContent = data.message;
                this.hideTypingIndicator();
                this.addAgentMessage(data.agent, data.message);
                this.activateAgent(data.agent);
                this.showTypingIndicator();
                break;
                
            case 'agent_handoff':
                this.addSystemMessage(data.message);
                this.showTypingIndicator();
                break;
                
            case 'chat_complete':
                this.hideTypingIndicator();
                // Only show final message if it's different from last message
                if (data.message && data.message.trim() && data.message !== this.lastMessageContent) {
                    this.addAgentMessage('🎯 팀 리더', data.message);
                }
                this.clearActiveAgents();
                this.lastMessageContent = null; // Reset for next conversation
                break;
                
            case 'system_message':
                this.addSystemMessage(data.message);
                break;
                
            case 'status':
                // Just update status, don't show message
                console.log('Status update:', data.message);
                break;
                
            case 'error':
                this.hideTypingIndicator();
                this.addSystemMessage(`⚠️ ${data.message}`);
                break;
                
            default:
                console.log('Unknown message type:', data.type, data);
        }
    }
    
    addUserMessage(content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user';
        
        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'message-bubble';
        bubbleDiv.textContent = content;
        
        const timestampDiv = document.createElement('div');
        timestampDiv.className = 'message-timestamp';
        timestampDiv.textContent = this.getCurrentTime();
        
        messageDiv.appendChild(bubbleDiv);
        messageDiv.appendChild(timestampDiv);
        
        this.messagesDiv.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    addAgentMessage(agent, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message agent';
        messageDiv.setAttribute('data-agent', agent);
        
        const headerDiv = document.createElement('div');
        headerDiv.className = 'agent-header';
        
        const badgeDiv = document.createElement('div');
        badgeDiv.className = 'agent-badge';
        
        const agentInfo = this.getAgentInfo(agent);
        badgeDiv.innerHTML = `<span class="emoji">${agentInfo.emoji}</span><span>${agentInfo.name}</span>`;
        
        headerDiv.appendChild(badgeDiv);
        
        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'message-bubble';
        
        if (typeof marked !== 'undefined') {
            bubbleDiv.innerHTML = marked.parse(content);
        } else {
            bubbleDiv.textContent = content;
        }
        
        const timestampDiv = document.createElement('div');
        timestampDiv.className = 'message-timestamp';
        timestampDiv.textContent = this.getCurrentTime();
        
        messageDiv.appendChild(headerDiv);
        messageDiv.appendChild(bubbleDiv);
        messageDiv.appendChild(timestampDiv);
        
        this.messagesDiv.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    addSystemMessage(content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message system';
        
        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'message-bubble';
        bubbleDiv.textContent = content;
        
        messageDiv.appendChild(bubbleDiv);
        
        this.messagesDiv.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    getAgentInfo(agent) {
        const agentMap = {
            'chat_orchestrator': { emoji: '🎯', name: '팀 리더' },
            '팀 리더': { emoji: '🎯', name: '팀 리더' },
            'metric_expert': { emoji: '📊', name: '메트릭 전문가' },
            '메트릭 전문가': { emoji: '📊', name: '메트릭 전문가' },
            'log_expert': { emoji: '📋', name: '로그 분석가' },
            '로그 분석가': { emoji: '📋', name: '로그 분석가' },
            'analysis_agent': { emoji: '🔬', name: '데이터 분석가' },
            '데이터 분석가': { emoji: '🔬', name: '데이터 분석가' },
            'report_agent': { emoji: '📈', name: '리포터' },
            'presentation_agent': { emoji: '🎨', name: '프레젠터' },
        };
        
        if (agentMap[agent]) return agentMap[agent];
        
        for (const [key, value] of Object.entries(agentMap)) {
            if (agent.includes(value.name)) return value;
        }
        
        return { emoji: '🤖', name: agent };
    }
    
    activateAgent(agentName) {
        const agentMap = {
            'chat_orchestrator': 'orchestrator',
            '팀 리더': 'orchestrator',
            'metric_expert': 'metrics',
            '메트릭 전문가': 'metrics',
            'log_expert': 'logs',
            '로그 분석가': 'logs',
            'analysis_agent': 'analyst',
            '데이터 분석가': 'analyst',
        };
        
        const agentType = agentMap[agentName] || agentName;
        this.activeAgents.add(agentType);
        
        const avatar = document.querySelector(`.agent-avatar[data-agent="${agentType}"]`);
        if (avatar) avatar.classList.add('active');
    }
    
    clearActiveAgents() {
        document.querySelectorAll('.agent-avatar.active').forEach(avatar => {
            setTimeout(() => avatar.classList.remove('active'), 2000);
        });
        this.activeAgents.clear();
    }
    
    showTypingIndicator() {
        if (this.typingIndicator) {
            this.typingIndicator.style.display = 'flex';
            this.scrollToBottom();
        }
    }
    
    hideTypingIndicator() {
        if (this.typingIndicator) {
            this.typingIndicator.style.display = 'none';
        }
    }
    
    updateTypingText(text) {
        const typingText = document.querySelector('.typing-text');
        if (typingText) typingText.textContent = text;
    }
    
    updateConnectionStatus(status, text) {
        const statusDot = this.connectionStatus.querySelector('.status-dot');
        const statusText = this.connectionStatus.querySelector('.status-text');
        
        statusDot.className = `status-dot ${status}`;
        statusText.textContent = text;
    }
    
    getCurrentTime() {
        const now = new Date();
        return now.toLocaleTimeString('ko-KR', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    }
    
    scrollToBottom() {
        setTimeout(() => {
            this.messagesDiv.scrollTop = this.messagesDiv.scrollHeight;
        }, 100);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 SRE AI Team Chat initializing...');
    window.chatApp = new ChatApp();
    console.log('✅ Chat app ready!');
});
