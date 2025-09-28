class ChatApp {
    constructor() {
        this.ws = null;
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.messagesDiv = document.getElementById('messages');
        this.connectionStatus = document.getElementById('connectionStatus');
        this.agentStatus = document.getElementById('agentStatus');
        
        this.initEventListeners();
        this.connect();
    }
    
    initEventListeners() {
        this.sendButton.addEventListener('click', () => this.sendMessage());
        this.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Auto-resize textarea
        this.messageInput.addEventListener('input', (e) => {
            e.target.style.height = 'auto';
            e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
        });
        
        // Quick action buttons
        document.querySelectorAll('.quick-btn').forEach(btn => {
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
        
        this.updateConnectionStatus('connecting', '연결 중...');
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connection established');
        };
        
        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (error) {
                console.error('Error parsing message:', error);
            }
        };
        
        this.ws.onclose = (event) => {
            console.log('WebSocket connection closed:', event.code, event.reason);
            this.updateConnectionStatus('disconnected', '🔴 연결 끊김');
            this.addSystemMessage('❌ SRE Agent 연결이 끊어졌습니다. 시스템을 재시작하는 중...');
            
            // 자동 재연결 시도 (5초 후)
            setTimeout(() => {
                console.log('Attempting to reconnect...');
                this.connect();
            }, 5000);
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateConnectionStatus('disconnected', '🚨 연결 오류 - 시스템 점검 필요');
        };
    }
    
    sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message) return;
        
        // 채팅 모드 확인
        const chatMode = document.querySelector('input[name="chatMode"]:checked').value;
        
        // SRE 특수 명령어 처리
        if (message.toLowerCase() === 'clear') {
            this.messagesDiv.innerHTML = '';
            this.messageInput.value = '';
            this.addSystemMessage('💫 채팅 히스토리가 초기화되었습니다.');
            return;
        }
        
        if (message.toLowerCase() === 'status') {
            this.addSystemMessage('🔍 전체 시스템 상태 조회 중...');
            this.messageInput.value = '전체 클러스터와 관찰가능성 시스템의 상태를 확인해줘';
        }
        
        if (message.toLowerCase() === 'help') {
            this.addSystemMessage(`
                🤖 <strong>SRE AI Agent 사용 가이드</strong><br>
                • <code>status</code> - 전체 시스템 상태 확인<br>
                • <code>incident</code> - 인시던트 분석 모드<br>
                • <code>metrics</code> - 핵심 메트릭 조회<br>
                • <code>clear</code> - 채팅 기록 초기화<br><br>
                📊 <strong>분석 예시:</strong><br>
                • "production 네임스페이스 장애 분석해줘"<br>
                • "CPU 사용량이 높은 서비스 찾아줘"<br>
                • "최근 에러 로그 패턴 분석"
            `);
            this.messageInput.value = '';
            return;
        }
        
        this.addMessage('user', message);
        this.messageInput.value = '';
        this.sendButton.disabled = true;
        
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            const message_data = { 
                type: 'chat', 
                message: message,
                mode: chatMode 
            };
            
            // 개별 모드인 경우 agent_type 추가
            if (chatMode === 'individual') {
                message_data.agent_type = 'metric_analyze_agent';  // 기본값
            }
            
            this.ws.send(JSON.stringify(message_data));
        } else {
            this.addSystemMessage('❌ SRE Agent와의 연결이 끊어져 있습니다. 시스템 관리자에게 문의하세요.');
            this.sendButton.disabled = false;
        }
    }
    
    handleMessage(data) {
        console.log('Received message:', data);
        
        switch (data.type) {
            case 'connection_status':
                if (data.status === 'connected') {
                    this.updateConnectionStatus('connected', '연결됨');
                    this.addSystemMessage('✅ 서버에 연결되었습니다.');
                } else if (data.status === 'ready') {
                    this.updateConnectionStatus('ready', 'Multi-Agent 시스템 준비 완료');
                    this.addSystemMessage('🚀 Multi-Agent SRE 시스템 준비 완료! 메시지를 입력해주세요.');
                    this.updateAgentStatus(data.agent_status);
                }
                break;
                
            case 'processing':
                this.addProcessingMessage(data.message);
                break;
                
            case 'agent_start':
                this.removeProcessingMessages();
                this.addAgentStartMessage(data.agent, data.message);
                break;
                
            case 'team_start':
                this.removeProcessingMessages();
                this.addSystemMessage(`🚀 ${data.message} (모드: ${data.mode === 'team' ? '팀 채팅' : '개별 에이전트'})`);
                break;
                
            case 'team_message':
                this.addTeamMessage(data.agent, data.message, data.sequence, data.total);
                break;
                
            case 'team_complete':
                this.addSystemMessage(`🎉 ${data.message}<br><small>${data.summary}</small>`);
                this.sendButton.disabled = false;
                break;
                
            case 'individual_start':
                this.removeProcessingMessages();
                this.addSystemMessage(`🤖 ${data.message} (모드: 개별 에이전트)`);
                break;
                
            case 'individual_progress':
                // 실시간 진행 상태 업데이트
                this.updateProgressMessage(data.message, data.step, data.total_steps);
                break;
                
            case 'individual_response':
                this.removeProgressMessages(); // 진행 메시지 제거
                this.addAgentResponse(data.agent, data.display_name, data.response);
                break;
                
            case 'individual_complete':
                this.addAgentCompleteMessage(data.agent, data.message);
                this.sendButton.disabled = false;
                break;
                
            case 'agent_response':
                this.addAgentResponse(data.agent, data.display_name, data.response);
                break;
                
            case 'agent_complete':
                this.addAgentCompleteMessage(data.agent, data.message);
                break;
                
            case 'workflow_complete':
                this.addSystemMessage(`🎉 ${data.message}<br><small>${data.summary}</small>`);
                this.sendButton.disabled = false;
                break;
                
            case 'chat_response':
                this.removeProcessingMessages();
                this.addMessage('agent', data.response);
                this.updateAgentStatus(data.agent_status);
                this.sendButton.disabled = false;
                break;
                
            case 'error':
                this.removeProcessingMessages();
                this.addMessage('system', `❌ 오류: ${data.error}`);
                this.sendButton.disabled = false;
                break;
                
            default:
                console.warn('Unknown message type:', data.type);
        }
    }
    
    addTeamMessage(agent, message, sequence, total) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message team-message';
        messageDiv.innerHTML = `
            <div class="team-message-header">
                <span class="team-indicator">🤝</span>
                <strong>Team Message ${sequence}/${total}</strong>
                <span class="agent-name">${agent}</span>
            </div>
            <div class="message-content">
                ${marked.parse(message)}
            </div>
        `;
        this.messagesDiv.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    addAgentStartMessage(agent, message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message agent-start-message';
        messageDiv.innerHTML = `
            <div class="agent-start-content">
                <span class="agent-indicator">🔄</span>
                ${message}
            </div>
        `;
        this.messagesDiv.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    addAgentResponse(agent, displayName, response) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message agent-response-message';
        
        const timestamp = new Date().toLocaleTimeString();
        const renderedContent = marked.parse(response);
        
        messageDiv.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <strong>${displayName}:</strong><br>
                    <div class="markdown-content">${renderedContent}</div>
                </div>
                <small style="color: #666; font-size: 11px;">${timestamp}</small>
            </div>
        `;
        this.messagesDiv.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    addAgentCompleteMessage(agent, message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message agent-complete-message';
        messageDiv.innerHTML = `
            <div class="agent-complete-content">
                <span class="agent-indicator">✅</span>
                ${message}
            </div>
        `;
        this.messagesDiv.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    addMessage(sender, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;
        
        const timestamp = new Date().toLocaleTimeString();
        
        if (sender === 'user') {
            messageDiv.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div><strong>💬 You:</strong><br>${this.escapeHtml(content)}</div>
                    <small style="color: rgba(255,255,255,0.7); font-size: 11px;">${timestamp}</small>
                </div>
            `;
        } else if (sender === 'agent') {
            // 에이전트 응답은 마크다운으로 렌더링
            const renderedContent = marked.parse(content);
            messageDiv.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div><strong>🤖 SRE Agent:</strong><br><div class="markdown-content">${renderedContent}</div></div>
                    <small style="color: #666; font-size: 11px;">${timestamp}</small>
                </div>
            `;
        } else {
            messageDiv.innerHTML = content;
            messageDiv.className = 'message system-message';
        }
        
        this.messagesDiv.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    addSystemMessage(content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message system-message';
        messageDiv.innerHTML = content;
        this.messagesDiv.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    addProcessingMessage(content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message processing-message';
        messageDiv.innerHTML = content;
        messageDiv.setAttribute('data-processing', 'true');
        this.messagesDiv.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    removeProcessingMessages() {
        const processingMessages = this.messagesDiv.querySelectorAll('[data-processing="true"]');
        processingMessages.forEach(msg => msg.remove());
    }
    
    updateProgressMessage(message, step, totalSteps) {
        // 기존 진행 메시지 찾기 또는 생성
        let progressMsg = this.messagesDiv.querySelector('[data-progress="true"]');
        if (!progressMsg) {
            progressMsg = document.createElement('div');
            progressMsg.className = 'message processing-message';
            progressMsg.setAttribute('data-progress', 'true');
            this.messagesDiv.appendChild(progressMsg);
        }
        
        // 진행 바와 메시지 업데이트
        const percentage = Math.round((step / totalSteps) * 100);
        progressMsg.innerHTML = `
            <div style="margin-bottom: 8px;">${message}</div>
            <div style="background: rgba(255,255,255,0.1); border-radius: 10px; height: 6px; overflow: hidden;">
                <div style="background: #4CAF50; height: 100%; width: ${percentage}%; transition: width 0.5s ease;"></div>
            </div>
            <small style="color: rgba(255,255,255,0.7);">단계 ${step}/${totalSteps} (${percentage}%)</small>
        `;
        this.scrollToBottom();
    }
    
    removeProgressMessages() {
        const progressMessages = this.messagesDiv.querySelectorAll('[data-progress="true"]');
        progressMessages.forEach(msg => msg.remove());
    }
    
    updateConnectionStatus(status, text) {
        this.connectionStatus.innerHTML = `<span class="connection-status ${status}"></span>${text}`;
    }
    
    updateAgentStatus(status) {
        if (!status) return;
        
        let html = '';
        if (status.initialized) {
            html += `<div class="status-item">✅ SRE Agent 활성화 완료</div>`;
            if (status.current_step) {
                html += `<div class="status-item">📍 현재 단계: ${status.current_step}</div>`;
            }
            if (status.analysis_state) {
                const state = status.analysis_state;
                html += `<div class="status-item">
                    📊 <strong>분석 진행 상황</strong><br>
                    <div class="analysis-progress">
                        <div class="progress-item ${state.essential_metrics_collected ? 'completed' : 'pending'}">
                            <span class="progress-icon">${state.essential_metrics_collected ? '✅' : '🔄'}</span>
                            <span class="progress-text">기본 시스템 메트릭 수집</span>
                        </div>
                        <div class="progress-item ${state.metric_names_explored ? 'completed' : 'pending'}">
                            <span class="progress-icon">${state.metric_names_explored ? '✅' : '🔍'}</span>
                            <span class="progress-text">사용 가능한 메트릭 탐색</span>
                        </div>
                        <div class="progress-item ${state.detailed_metrics_queried ? 'completed' : 'pending'}">
                            <span class="progress-icon">${state.detailed_metrics_queried ? '✅' : '📈'}</span>
                            <span class="progress-text">상세 데이터 쿠리 수행</span>
                        </div>
                        <div class="progress-item ${state.targets_checked ? 'completed' : 'pending'}">
                            <span class="progress-icon">${state.targets_checked ? '✅' : '🎯'}</span>
                            <span class="progress-text">모니터링 대상 상태 확인</span>
                        </div>
                    </div>
                </div>`;
            }
        } else {
            html = '<div class="status-item">⏳ SRE Agent 초기화 대기 중...</div>';
        }
        
        this.agentStatus.innerHTML = html;
    }
    
    escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;")
            .replace(/\n/g, "<br>");
    }
    
    scrollToBottom() {
        setTimeout(() => {
            this.messagesDiv.scrollTop = this.messagesDiv.scrollHeight;
        }, 100);
    }
}

// 페이지 로드 시 앱 시작
document.addEventListener('DOMContentLoaded', function() {
    console.log('Starting MetricAnalyzeAgent Web Chat...');
    new ChatApp();
});