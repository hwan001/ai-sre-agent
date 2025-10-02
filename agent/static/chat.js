/**
 * SRE Agent v3.0 Chat Interface
 * 
 * Conversational Multi-Agent WebSocket Chat Client
 * Dynamic Swarm collaboration with HandOff pattern
 */

class ChatApp {
    constructor() {
        this.ws = null;
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.reportButton = document.getElementById('reportButton');
        this.messagesDiv = document.getElementById('messages');
        this.connectionStatus = document.getElementById('connectionStatus');
        this.agentStatus = document.getElementById('agentStatus');
        
        this.activeAgents = new Set();
        this.conversationMessages = [];
        
        this.initEventListeners();
        this.connect();
    }
    
    initEventListeners() {
        this.sendButton.addEventListener('click', () => this.sendMessage());
        
        this.reportButton.addEventListener('click', () => {
            this.messageInput.value = 'Give me a comprehensive report';
            this.sendMessage();
        });
        
        this.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        this.messageInput.addEventListener('input', (e) => {
            e.target.style.height = 'auto';
            e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
        });
        
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
        
        this.updateConnectionStatus('connecting', '🔄 Connecting...');
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('✅ WebSocket connected');
            this.updateConnectionStatus('connected', '✅ Connected');
            this.updateAgentStatus('Conversational AI System v3.0 Ready');
            this.addSystemMessage('� Ready for conversation! Ask me anything about your Kubernetes cluster.');
        };
        
        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (error) {
                console.error('❌ Error parsing message:', error);
            }
        };
        
        this.ws.onclose = () => {
            console.log('🔌 WebSocket closed');
            this.updateConnectionStatus('disconnected', '⚠️ Disconnected');
            setTimeout(() => this.connect(), 5000);
        };
        
        this.ws.onerror = (error) => {
            console.error('❌ WebSocket error:', error);
            this.updateConnectionStatus('error', '❌ Connection Error');
        };
    }
    
    sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message) return;
        
        // Handle special commands
        if (message.toLowerCase() === 'clear') {
            this.messagesDiv.innerHTML = '';
            this.messageInput.value = '';
            this.addSystemMessage('🧹 Chat history cleared');
            return;
        }
        
        if (message.toLowerCase() === 'help') {
            this.showHelp();
            this.messageInput.value = '';
            return;
        }
        
        this.addMessage('user', message);
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';
        this.sendButton.disabled = true;
        
        // Send to server (v3.0 format - no mode)
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'chat',
                message: message
            }));
        } else {
            this.addSystemMessage('❌ Not connected to server');
            this.sendButton.disabled = false;
        }
    }
    
    handleMessage(data) {
        console.log('📩 Received:', data.type, data);
        
        switch (data.type) {
            case 'status':
                this.addSystemMessage(`⏳ ${data.message}`);
                break;
            case 'chat_start':
                this.handleChatStart(data);
                break;
            case 'agent_message':
                this.handleAgentMessage(data);
                break;
            case 'chat_complete':
                this.handleChatComplete(data);
                break;
            case 'error':
                this.addSystemMessage(`❌ ${data.message}`);
                this.sendButton.disabled = false;
                break;
            default:
                console.log('Unknown message type:', data.type);
        }
    }
    
    handleChatStart(data) {
        this.addSystemMessage(data.message || '🚀 Starting analysis...');
        this.activeAgents.clear();
        this.updateActiveAgents();
    }
    
    handleAgentMessage(data) {
        const agentName = data.agent || 'Agent';
        const message = data.message || '';
        
        // Skip messages that contain raw message objects
        if (message.includes('messages=[') || message.includes('TextMessage(')) {
            console.log('⚠️ Skipping raw message object:', message.substring(0, 100));
            return;
        }
        
        // Track active agent
        this.activeAgents.add(agentName);
        this.updateActiveAgents();
        
        // Skip very short messages
        if (!message || message.trim().length < 5) {
            return;
        }
        
        this.addAgentMessageStreaming(agentName, message);
    }
    
    addAgentMessageStreaming(agent, content) {
        const messageDiv = document.createElement('div');
        const isPresentation = agent.toLowerCase().includes('presentation');
        const collapsed = !isPresentation;  // Only presentation agent expanded by default
        
        messageDiv.className = `message assistant-message agent-message streaming ${collapsed ? 'collapsed' : ''}`;
        messageDiv.dataset.agent = agent;
        
        const agentIcon = this.getAgentIcon(agent);
        const toggleIcon = collapsed ? '▶' : '▼';
        
        messageDiv.innerHTML = `
            <div class="message-header collapsible" onclick="this.parentElement.classList.toggle('collapsed')">
                <span class="toggle-icon">${toggleIcon}</span>
                <span class="agent-icon">${agentIcon}</span>
                <span class="agent-name">${agent}</span>
                <span class="streaming-indicator">●</span>
            </div>
            <div class="message-content ${isPresentation ? 'markdown-content' : ''}">${this.formatAgentContent(content, isPresentation)}</div>
        `;
        
        this.messagesDiv.appendChild(messageDiv);
        this.scrollToBottom();
        
        // Remove streaming indicator after a moment
        setTimeout(() => {
            const indicator = messageDiv.querySelector('.streaming-indicator');
            if (indicator) {
                indicator.style.opacity = '0';
            }
        }, 1000);
    }
    
    formatAgentContent(content, isMarkdown = false) {
        if (isMarkdown && typeof marked !== 'undefined') {
            // Render markdown for presentation agent
            try {
                return marked.parse(content);
            } catch (e) {
                console.error('Markdown parsing error:', e);
                return this.escapeHtml(content).replace(/\n/g, '<br>');
            }
        }
        
        // Format agent messages more naturally
        let formatted = this.escapeHtml(content);
        
        // Don't show system messages like "TERMINATE"
        if (formatted.includes('TERMINATE') || formatted.includes('Transferred to')) {
            return '';
        }
        
        // Basic markdown-style formatting for non-presentation agents
        formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
        formatted = formatted.replace(/\n\n/g, '<br><br>');
        formatted = formatted.replace(/\n/g, '<br>');
        
        return formatted;
    }
    
    
    handleChatComplete(data) {
        // Final response from the workflow
        const message = data.message || 'Analysis completed';
        const agents = data.agents_participated || [];
        
        console.log('💬 Chat complete - Message:', message);
        console.log('👥 Agents participated:', agents);
        
        // Add the final response if it's meaningful
        if (message && message.length > 20 && !message.includes('messages=[')) {
            console.log('✅ Adding final message to chat');
            this.addMessage('assistant', message);
        } else {
            console.warn('⚠️ Message filtered or too short:', message.substring(0, 100));
        }
        
        // Show which agents participated
        if (agents.length > 0) {
            const agentList = agents
                .filter(a => a !== 'user')  // Filter out 'user'
                .map(a => this.getAgentIcon(a) + ' ' + a)
                .join(', ');
            
            if (agentList) {
                this.updateAgentStatus(`✅ Completed with: ${agentList}`);
                // Also add a system message showing completion
                this.addSystemMessage(`✨ Analysis completed by: ${agentList}`);
            }
        }
        
        // Re-enable send button
        this.sendButton.disabled = false;
        
        // Clear active agents after a delay
        setTimeout(() => {
            this.activeAgents.clear();
            this.updateActiveAgents();
        }, 2000);
    }
    
    formatAgentContent(content) {
        // Format agent messages more naturally
        let formatted = this.escapeHtml(content);
        
        // Don't show system messages like "TERMINATE"
        if (formatted.includes('TERMINATE') || formatted.includes('Transferred to')) {
            return '';
        }
        
        // Basic markdown-style formatting
        formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
        formatted = formatted.replace(/\n\n/g, '<br><br>');
        formatted = formatted.replace(/\n/g, '<br>');
        
        return formatted;
    }
    
    handleFinalSummary(data) {
        // Natural conversational summary
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant-message final-summary';
        
        messageDiv.innerHTML = `
            <div class="message-header">
                <span class="agent-icon">💡</span>
                <span class="agent-name">Summary</span>
            </div>
            <div class="message-content">${this.formatMarkdown(data.message)}</div>
        `;
        
        this.messagesDiv.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    handleAnalysisStart(data) {
        if (this.currentProgressDiv) {
            this.currentProgressDiv.remove();
        }
        
        this.addSystemMessage(`${data.message}`);
        
        if (data.teams && data.teams.length > 0) {
            const teamsText = `Teams: ${data.teams.join(', ')}`;
            this.addSystemMessage(`<small>�� ${teamsText}</small>`);
        }
        
        this.conversationMessages = [];
    }
    
    handleProgress(data) {
        if (!this.currentProgressDiv) {
            this.currentProgressDiv = document.createElement('div');
            this.currentProgressDiv.className = 'message system-message progress-message';
            this.messagesDiv.appendChild(this.currentProgressDiv);
        }
        
        const percentage = data.percentage || 0;
        const step = data.step || 0;
        const totalSteps = data.total_steps || 4;
        
        this.currentProgressDiv.innerHTML = `
            <div class="progress-container">
                <div class="progress-text">${data.message}</div>
                <div class="progress-bar-container">
                    <div class="progress-bar" style="width: ${percentage}%"></div>
                </div>
                <div class="progress-steps">Step ${step} of ${totalSteps} (${percentage}%)</div>
            </div>
        `;
        
        this.scrollToBottom();
    }
    
    handleConversationMessage(data) {
        const agent = data.agent || 'Agent';
        const message = data.message || '';
        const sequence = data.sequence || 1;
        const total = data.total || 1;
        
        this.conversationMessages.push({ agent, message, sequence });
        this.addAgentMessage(agent, message, sequence, total);
    }
    
    handleFinalResult(data) {
        if (this.currentProgressDiv) {
            this.currentProgressDiv.remove();
            this.currentProgressDiv = null;
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant-message final-result';
        
        let html = `<div class="agent-name">🎯 Final Analysis</div>`;
        html += `<div class="message-content">${this.formatMarkdown(data.message)}</div>`;
        
        if (data.metadata) {
            html += `<div class="result-metadata">`;
            if (data.confidence) {
                const confidencePercent = (data.confidence * 100).toFixed(0);
                html += `<span class="metadata-item">Confidence: ${confidencePercent}%</span>`;
            }
            if (data.actions_count > 0) {
                html += `<span class="metadata-item">Actions: ${data.actions_count}</span>`;
            }
            if (data.metadata.incident_id) {
                html += `<span class="metadata-item">ID: ${data.metadata.incident_id}</span>`;
            }
            html += `</div>`;
        }
        
        messageDiv.innerHTML = html;
        this.messagesDiv.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    handleAnalysisComplete(data) {
        this.addSystemMessage(`${data.message}`);
        
        if (data.summary) {
            let summaryHtml = '<div class="analysis-summary"><strong>Summary:</strong><br>';
            
            if (data.summary.messages_exchanged) {
                summaryHtml += `📝 Messages: ${data.summary.messages_exchanged}<br>`;
            }
            if (data.summary.actions_count) {
                summaryHtml += `🎯 Actions: ${data.summary.actions_count}<br>`;
            }
            if (data.summary.confidence !== undefined) {
                summaryHtml += `📊 Confidence: ${(data.summary.confidence * 100).toFixed(0)}%<br>`;
            }
            
            summaryHtml += '</div>';
            this.addSystemMessage(summaryHtml);
        }
        
        this.sendButton.disabled = false;
    }
    
    handleError(data) {
        if (this.currentProgressDiv) {
            this.currentProgressDiv.remove();
            this.currentProgressDiv = null;
        }
        
        this.addSystemMessage(`❌ Error: ${data.message || data.error || 'Unknown error'}`);
        this.sendButton.disabled = false;
    }
    
    addMessage(sender, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;
        
        if (sender === 'user') {
            messageDiv.innerHTML = `
                <div class="message-header">
                    <span class="sender-name">You</span>
                </div>
                <div class="message-content">${this.escapeHtml(content)}</div>
            `;
        } else if (sender === 'assistant') {
            // Format assistant messages with proper styling
            const formattedContent = this.formatAgentContent(content);
            messageDiv.innerHTML = `
                <div class="message-header">
                    <span class="agent-icon">🤖</span>
                    <span class="agent-name">AI Assistant</span>
                </div>
                <div class="message-content">${formattedContent}</div>
            `;
        } else {
            // Fallback for other message types
            messageDiv.innerHTML = `
                <div class="message-content">${this.escapeHtml(content)}</div>
            `;
        }
        
        this.messagesDiv.appendChild(messageDiv);
        this.scrollToBottom();
        
        console.log('✅ Message added to DOM:', sender, content.substring(0, 100));
    }
    
    addAgentMessage(agent, content, sequence, total) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant-message agent-message';
        
        const agentIcon = this.getAgentIcon(agent);
        
        messageDiv.innerHTML = `
            <div class="message-header">
                <span class="agent-icon">${agentIcon}</span>
                <span class="agent-name">${agent}</span>
                <span class="message-sequence">[${sequence}/${total}]</span>
            </div>
            <div class="message-content">${this.escapeHtml(content)}</div>
        `;
        
        this.messagesDiv.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    addSystemMessage(content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message system-message';
        messageDiv.innerHTML = `<div class="message-content">${content}</div>`;
        this.messagesDiv.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    getAgentIcon(agentName) {
        const icons = {
            'coordinator': '🎯',
            'orchestrator': '🎯',
            'triage': '�',
            'log': '📋',
            'metric': '📊',
            'metrics': '📊',
            'action': '🎬',
            'prometheus': '📈',
            'loki': '🔍',
            'summarizer': '📝',
            'analyzer': '�',
            'recommendation': '💡',
            'guard': '🛡️',
            'query': '🔎',
        };
        
        const nameLower = agentName.toLowerCase();
        for (const [key, icon] of Object.entries(icons)) {
            if (nameLower.includes(key)) {
                return icon;
            }
        }
        
        return '🤖';
    }
    
    updateConnectionStatus(status, message) {
        const statusDot = this.connectionStatus.querySelector('.status-dot');
        if (statusDot) {
            statusDot.className = `status-dot ${status}`;
        }
        const statusText = this.connectionStatus.querySelector('span:last-child');
        if (statusText) {
            statusText.textContent = message;
        }
    }
    
    updateAgentStatus(message) {
        if (this.agentStatus) {
            this.agentStatus.innerHTML = `<div class="status-item">${message}</div>`;
        }
    }
    
    updateActiveAgents() {
        // Highlight active agent badges
        document.querySelectorAll('.agent-badge').forEach(badge => {
            badge.classList.remove('active');
        });
        
        this.activeAgents.forEach(agentName => {
            const agentLower = agentName.toLowerCase();
            if (agentLower.includes('orchestrator')) {
                document.querySelector('.agent-badge.orchestrator')?.classList.add('active');
            } else if (agentLower.includes('metric')) {
                document.querySelector('.agent-badge.metric')?.classList.add('active');
            } else if (agentLower.includes('log')) {
                document.querySelector('.agent-badge.log')?.classList.add('active');
            } else if (agentLower.includes('analyst') || agentLower.includes('analysis')) {
                document.querySelector('.agent-badge.analysis')?.classList.add('active');
            } else if (agentLower.includes('report')) {
                document.querySelector('.agent-badge.report')?.classList.add('active');
            }
        });
    }
    
    scrollToBottom() {
        this.messagesDiv.scrollTop = this.messagesDiv.scrollHeight;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    formatMarkdown(text) {
        let formatted = this.escapeHtml(text);
        formatted = formatted.replace(/## (.*?)$/gm, '<h3>$1</h3>');
        formatted = formatted.replace(/# (.*?)$/gm, '<h2>$1</h2>');
        formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
        formatted = formatted.replace(/\n/g, '<br>');
        return formatted;
    }
    
    showHelp() {
        const helpMessage = `
            <div class="help-content">
                <h3>🤖 SRE Agent v3.0 - Help</h3>
                <p><strong>Conversational Interface:</strong></p>
                <p>Ask questions naturally! The system will engage appropriate experts automatically.</p>
                
                <p><strong>Available Agents:</strong></p>
                <ul>
                    <li>🎯 <strong>Orchestrator</strong>: Routes your questions to specialists</li>
                    <li>📊 <strong>Metric Expert</strong>: Analyzes Prometheus metrics</li>
                    <li>📋 <strong>Log Expert</strong>: Searches and analyzes logs via Loki</li>
                    <li>🔬 <strong>Analyst</strong>: Performs root cause analysis</li>
                    <li>📈 <strong>Reporter</strong>: Generates visual reports</li>
                </ul>
                
                <p><strong>Example Questions:</strong></p>
                <ul>
                    <li>"Why is my pod crashing?"</li>
                    <li>"Show me high CPU pods"</li>
                    <li>"Find errors in the last hour"</li>
                    <li>"Give me a system health report"</li>
                    <li>"Analyze service performance"</li>
                </ul>
                
                <p><strong>Commands:</strong></p>
                <ul>
                    <li><code>help</code> - Show this help message</li>
                    <li><code>clear</code> - Clear chat history</li>
                </ul>
                
                <p><strong>Tips:</strong></p>
                <ul>
                    <li>✨ Ask follow-up questions - conversation context is maintained</li>
                    <li>🔄 Multiple agents can collaborate on complex issues</li>
                    <li>� Request reports anytime with "give me a report"</li>
                </ul>
            </div>
        `;
        this.addSystemMessage(helpMessage);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Initializing SRE Agent v3.0 Chat Interface');
    window.chatApp = new ChatApp();
});
