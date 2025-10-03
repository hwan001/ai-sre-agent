/**
 * Visualization Components for SRE Agent v4.0
 * 
 * Provides interactive charts and visual components for:
 * - Metrics visualization (line, bar, gauge charts)
 * - Anomaly detection displays
 * - Log pattern timelines
 * - Health status indicators
 */

class VisualizationManager {
    constructor() {
        this.chartInstances = new Map();
        this.chartIdCounter = 0;
        
        // Load Chart.js dynamically if not loaded
        if (typeof Chart === 'undefined') {
            this.loadChartJS();
        }
    }
    
    loadChartJS() {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js';
        script.onload = () => console.log('📊 Chart.js loaded');
        document.head.appendChild(script);
    }
    
    /**
     * Create a metric chart visualization
     */
    createMetricChart(data, container) {
        const chartId = `chart-${this.chartIdCounter++}`;
        const chartType = data.type || 'line';
        
        const chartContainer = document.createElement('div');
        chartContainer.className = 'chart-container';
        chartContainer.innerHTML = `
            <div class="chart-header">
                <h4>${data.title || 'Metric Chart'}</h4>
                ${data.subtitle ? `<p class="chart-subtitle">${data.subtitle}</p>` : ''}
            </div>
            <canvas id="${chartId}" width="400" height="200"></canvas>
        `;
        
        container.appendChild(chartContainer);
        
        // Wait for Chart.js to load
        this.whenChartReady(() => {
            const ctx = document.getElementById(chartId);
            if (!ctx) return;
            
            const chartConfig = this.getChartConfig(chartType, data);
            const chart = new Chart(ctx, chartConfig);
            this.chartInstances.set(chartId, chart);
        });
        
        return chartId;
    }
    
    /**
     * Create anomaly visualization
     */
    createAnomalyDisplay(anomalies, container) {
        const anomalyDiv = document.createElement('div');
        anomalyDiv.className = 'anomaly-display';
        
        const title = document.createElement('h4');
        title.innerHTML = '🔍 Anomaly Detection Results';
        anomalyDiv.appendChild(title);
        
        if (!anomalies || anomalies.length === 0) {
            anomalyDiv.innerHTML += '<p class="no-data">No anomalies detected</p>';
            container.appendChild(anomalyDiv);
            return;
        }
        
        anomalies.forEach(anomaly => {
            const anomalyCard = document.createElement('div');
            anomalyCard.className = `anomaly-card severity-${anomaly.severity}`;
            
            const severityIcon = {
                'critical': '🚨',
                'warning': '⚠️',
                'info': 'ℹ️'
            }[anomaly.severity] || '•';
            
            const confidence = (anomaly.confidence * 100).toFixed(1);
            const score = anomaly.anomaly_score.toFixed(3);
            
            anomalyCard.innerHTML = `
                <div class="anomaly-header">
                    <span class="anomaly-icon">${severityIcon}</span>
                    <span class="anomaly-metric">${anomaly.metric}</span>
                    <span class="anomaly-badge">${anomaly.severity.toUpperCase()}</span>
                </div>
                <div class="anomaly-body">
                    <p class="anomaly-message">${anomaly.message}</p>
                    <div class="anomaly-metrics">
                        <span class="metric-item">
                            <strong>Confidence:</strong> ${confidence}%
                        </span>
                        <span class="metric-item">
                            <strong>Score:</strong> ${score}
                        </span>
                    </div>
                    ${anomaly.detectors ? `
                        <div class="detectors">
                            <strong>Triggered by:</strong> ${anomaly.detectors.join(', ')}
                        </div>
                    ` : ''}
                </div>
            `;
            
            anomalyDiv.appendChild(anomalyCard);
        });
        
        container.appendChild(anomalyDiv);
    }
    
    /**
     * Create log pattern timeline
     */
    createLogTimeline(patterns, container) {
        const timelineDiv = document.createElement('div');
        timelineDiv.className = 'log-timeline';
        
        const title = document.createElement('h4');
        title.innerHTML = '📋 Log Pattern Analysis';
        timelineDiv.appendChild(title);
        
        if (!patterns || patterns.length === 0) {
            timelineDiv.innerHTML += '<p class="no-data">No patterns detected</p>';
            container.appendChild(timelineDiv);
            return;
        }
        
        const categoryCounts = {};
        patterns.forEach(pattern => {
            const cat = pattern.category || 'unknown';
            categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;
        });
        
        // Create category summary
        const summary = document.createElement('div');
        summary.className = 'pattern-summary';
        Object.entries(categoryCounts).forEach(([category, count]) => {
            const badge = document.createElement('span');
            badge.className = `pattern-badge category-${category}`;
            badge.textContent = `${category}: ${count}`;
            summary.appendChild(badge);
        });
        timelineDiv.appendChild(summary);
        
        // Create pattern list
        const patternList = document.createElement('div');
        patternList.className = 'pattern-list';
        
        patterns.forEach(pattern => {
            const patternItem = document.createElement('div');
            patternItem.className = 'pattern-item';
            
            const categoryIcon = {
                'errors': '❌',
                'performance': '⚡',
                'security': '🔒',
                'http': '🌐',
                'database': '🗄️'
            }[pattern.category] || '📄';
            
            patternItem.innerHTML = `
                <span class="pattern-icon">${categoryIcon}</span>
                <div class="pattern-details">
                    <strong>${pattern.name}</strong>
                    <p>${pattern.description}</p>
                </div>
                ${pattern.detected ? '<span class="status-badge detected">DETECTED</span>' : ''}
            `;
            
            patternList.appendChild(patternItem);
        });
        
        timelineDiv.appendChild(patternList);
        container.appendChild(timelineDiv);
    }
    
    /**
     * Create insight cards
     */
    createInsightCards(insights, container) {
        if (!insights || insights.length === 0) return;
        
        const insightsDiv = document.createElement('div');
        insightsDiv.className = 'insights-container';
        
        const title = document.createElement('h4');
        title.innerHTML = '💡 Key Insights';
        insightsDiv.appendChild(title);
        
        const grid = document.createElement('div');
        grid.className = 'insights-grid';
        
        insights.forEach(insight => {
            const card = document.createElement('div');
            card.className = 'insight-card';
            
            // Detect insight type from emoji
            let cardClass = 'info';
            if (insight.includes('🚨')) cardClass = 'critical';
            else if (insight.includes('⚠️')) cardClass = 'warning';
            else if (insight.includes('📊')) cardClass = 'metric';
            
            card.classList.add(cardClass);
            card.innerHTML = `<p>${insight}</p>`;
            
            grid.appendChild(card);
        });
        
        insightsDiv.appendChild(grid);
        container.appendChild(insightsDiv);
    }
    
    /**
     * Create health status indicator
     */
    createHealthIndicator(healthData, container) {
        const healthDiv = document.createElement('div');
        healthDiv.className = 'health-indicator';
        
        const overallStatus = healthData.status || 'unknown';
        const statusIcon = {
            'healthy': '✅',
            'degraded': '⚠️',
            'unhealthy': '🚨',
            'unknown': '❓'
        }[overallStatus] || '❓';
        
        healthDiv.innerHTML = `
            <div class="health-header">
                <span class="health-icon">${statusIcon}</span>
                <span class="health-status ${overallStatus}">${overallStatus.toUpperCase()}</span>
            </div>
            ${healthData.message ? `<p class="health-message">${healthData.message}</p>` : ''}
        `;
        
        if (healthData.components) {
            const componentList = document.createElement('div');
            componentList.className = 'component-list';
            
            Object.entries(healthData.components).forEach(([name, status]) => {
                const component = document.createElement('div');
                component.className = 'component-item';
                
                const componentStatus = status.status || 'unknown';
                const componentIcon = {
                    'healthy': '✓',
                    'degraded': '⚠',
                    'unhealthy': '✗'
                }[componentStatus] || '?';
                
                component.innerHTML = `
                    <span class="component-icon ${componentStatus}">${componentIcon}</span>
                    <span class="component-name">${name}</span>
                `;
                
                componentList.appendChild(component);
            });
            
            healthDiv.appendChild(componentList);
        }
        
        container.appendChild(healthDiv);
    }
    
    /**
     * Get Chart.js configuration for different chart types
     */
    getChartConfig(type, data) {
        const baseConfig = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: data.showLegend !== false,
                    position: 'top'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            }
        };
        
        switch (type) {
            case 'line':
                return {
                    type: 'line',
                    data: {
                        labels: data.labels || [],
                        datasets: [{
                            label: data.label || 'Value',
                            data: data.values || [],
                            borderColor: data.color || 'rgb(75, 192, 192)',
                            backgroundColor: data.backgroundColor || 'rgba(75, 192, 192, 0.1)',
                            tension: 0.4,
                            fill: true
                        }]
                    },
                    options: {
                        ...baseConfig,
                        scales: {
                            y: {
                                beginAtZero: true
                            }
                        }
                    }
                };
            
            case 'bar':
                return {
                    type: 'bar',
                    data: {
                        labels: data.labels || [],
                        datasets: [{
                            label: data.label || 'Value',
                            data: data.values || [],
                            backgroundColor: data.colors || 'rgba(54, 162, 235, 0.8)',
                            borderColor: 'rgba(54, 162, 235, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        ...baseConfig,
                        scales: {
                            y: {
                                beginAtZero: true
                            }
                        }
                    }
                };
            
            case 'doughnut':
                return {
                    type: 'doughnut',
                    data: {
                        labels: data.labels || [],
                        datasets: [{
                            data: data.values || [],
                            backgroundColor: data.colors || [
                                'rgba(255, 99, 132, 0.8)',
                                'rgba(54, 162, 235, 0.8)',
                                'rgba(255, 206, 86, 0.8)',
                                'rgba(75, 192, 192, 0.8)'
                            ]
                        }]
                    },
                    options: baseConfig
                };
            
            default:
                return this.getChartConfig('line', data);
        }
    }
    
    /**
     * Wait for Chart.js to be ready
     */
    whenChartReady(callback) {
        if (typeof Chart !== 'undefined') {
            callback();
        } else {
            setTimeout(() => this.whenChartReady(callback), 100);
        }
    }
    
    /**
     * Destroy a chart instance
     */
    destroyChart(chartId) {
        const chart = this.chartInstances.get(chartId);
        if (chart) {
            chart.destroy();
            this.chartInstances.delete(chartId);
        }
    }
    
    /**
     * Clear all charts
     */
    clearAll() {
        this.chartInstances.forEach(chart => chart.destroy());
        this.chartInstances.clear();
    }
}

// Global instance
const visualizationManager = new VisualizationManager();
