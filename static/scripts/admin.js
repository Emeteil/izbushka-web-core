function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

function getToken() {
    const token = getCookie('token');
    if (!token) {
        alert('Token not found in cookies. Please login first.');
        throw new Error('Token not found');
    }
    return token;
}

async function loadCurrentSettings() {
    try {
        const token = getToken();
        const response = await fetch('/api/webcam/quality', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.status === 'success') {
            const quality = data.data.quality;
            const stats = data.data.statistics;

            document.getElementById('quality-slider').value = quality.quality;
            document.getElementById('quality-value').textContent = quality.quality;

            const resString = `${quality.width}x${quality.height}`;
            const resSelect = document.getElementById('resolution-select');
            let found = false;

            for (let option of resSelect.options) {
                if (option.value === resString) {
                    resSelect.value = resString;
                    found = true;
                    break;
                }
            }

            if (!found) {
                resSelect.value = 'custom';
                document.getElementById('custom-resolution').style.display = 'block';
                document.getElementById('custom-width').value = quality.width;
                document.getElementById('custom-height').value = quality.height;
            } else {
                document.getElementById('custom-resolution').style.display = 'none';
            }

            document.getElementById('fps-select').value = quality.fps.toString();
            document.getElementById('auto-adjust').checked = quality.auto_adjust;
            document.getElementById('network-adaptation').checked = quality.network_adaptation;

            updateStatsDisplay(stats, quality);
        }
    } catch (error) {
        console.error('Error loading settings:', error);
        showMessage(`Failed to load settings: ${error.message}`, 'red');
    }
}

function updateStatsDisplay(stats, quality) {
    const statsDiv = document.getElementById('stats-display');

    let html = `
        <div><strong>Current Quality:</strong> ${quality.quality}</div>
        <div><strong>Resolution:</strong> ${quality.width} x ${quality.height}</div>
        <div><strong>FPS:</strong> ${quality.fps}</div>
        <div><strong>Auto Adjust:</strong> ${quality.auto_adjust ? 'Yes' : 'No'}</div>
        <div><strong>Network Adaptation:</strong> ${quality.network_adaptation ? 'Yes' : 'No'}</div>
        <hr>
        <div><strong>Capture Time:</strong> ${(stats.avg_capture_time * 1000).toFixed(2)} ms</div>
        <div><strong>Encode Time:</strong> ${(stats.avg_encode_time * 1000).toFixed(2)} ms</div>
        <div><strong>Stream Interval:</strong> ${(stats.avg_stream_interval * 1000).toFixed(2)} ms</div>
        <div><strong>Actual FPS:</strong> ${stats.avg_stream_interval ? (1 / stats.avg_stream_interval).toFixed(1) : 'null'}</div>
    `;

    statsDiv.innerHTML = html;
}

async function updateVideoSettings() {
    const token = getToken();
    const quality = parseInt(document.getElementById('quality-slider').value);
    const fps = parseInt(document.getElementById('fps-select').value);
    const autoAdjust = document.getElementById('auto-adjust').checked;
    const networkAdaptation = document.getElementById('network-adaptation').checked;

    let width, height;
    const resolution = document.getElementById('resolution-select').value;

    if (resolution === 'custom') {
        width = parseInt(document.getElementById('custom-width').value);
        height = parseInt(document.getElementById('custom-height').value);
    } else {
        const [w, h] = resolution.split('x');
        width = parseInt(w);
        height = parseInt(h);
    }

    const settings = {
        quality: quality,
        width: width,
        height: height,
        fps: fps,
        auto_adjust: autoAdjust,
        network_adaptation: networkAdaptation
    };

    try {
        const response = await fetch('/api/webcam/quality', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(settings)
        });

        const data = await response.json();

        if (data.status === 'success') {
            showMessage('Video settings updated successfully!', 'green');
            setTimeout(loadCurrentSettings, 500);
        } else {
            showMessage(`Error: ${data.error?.message || 'Unknown error'}`, 'red');
        }
    } catch (error) {
        console.error('Error updating settings:', error);
        showMessage(`Failed to update settings: ${error.message}`, 'red');
    }
}

async function getWebcamStatus() {
    try {
        const token = getToken();
        const response = await fetch('/api/webcam/status', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.status === 'success') {
            const statusDiv = document.getElementById('webcam-status');
            const status = data.data;

            let statusText = `Status: ${status.status}`;
            if (status.current_quality) {
                statusText += ` | Quality: ${status.current_quality}`;
            }
            if (status.actual_fps) {
                statusText += ` | FPS: ${status.actual_fps.toFixed(1)}`;
            }

            statusSpan.textContent = statusText;
            showMessage('Webcam status updated', 'green');
        }
    } catch (error) {
        console.error('Error getting webcam status:', error);
    }
}

async function resetStats() {
    try {
        const token = getToken();
        const response = await fetch('/api/webcam/stats/reset', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.status === 'success') {
            showMessage('Statistics reset successfully', 'green');
            setTimeout(loadCurrentSettings, 500);
        }
    } catch (error) {
        console.error('Error resetting stats:', error);
        showMessage(`Failed to reset stats: ${error.message}`, 'red');
    }
}

document.getElementById('resolution-select').addEventListener('change', function () {
    const customDiv = document.getElementById('custom-resolution');
    if (this.value === 'custom') {
        customDiv.style.display = 'block';
    } else {
        customDiv.style.display = 'none';
    }
});

document.getElementById('quality-slider').addEventListener('input', function () {
    document.getElementById('quality-value').textContent = this.value;
});

async function loadEmotions() {
    try {
        const token = getToken();
        const response = await fetch('/api/emotions', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        const data = await response.json();

        if (data.status === 'success') {
            const container = document.getElementById('emotions-list');
            container.innerHTML = '';

            data.data.emotions.forEach(emotion => {
                const button = document.createElement('button');
                button.textContent = `${emotion.emoji} ${emotion.name}`;
                button.style.margin = '5px';
                button.style.padding = '10px 15px';
                button.style.fontSize = '16px';

                button.onclick = () => setEmotion(emotion.id);

                container.appendChild(button);
                container.appendChild(document.createElement('br'));
            });
        }
    } catch (error) {
        console.error('Error loading emotions:', error);
        document.getElementById('message').style.color = 'red';
        document.getElementById('message').textContent = error.message;
    }
}

async function setEmotion(emotionId) {
    const messageDiv = document.getElementById('message');
    messageDiv.style.color = 'green';
    messageDiv.textContent = `Setting emotion: ${emotionId}...`;

    try {
        const token = getToken();
        const response = await fetch('/api/emotions/current', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ emotion: emotionId })
        });

        const data = await response.json();

        if (data.status === 'success') {
            messageDiv.textContent = `Emotion set to: ${emotionId}`;
        } else {
            messageDiv.style.color = 'red';
            messageDiv.textContent = `Error: ${data.error.message || 'Unknown error'}`;
        }
    } catch (error) {
        messageDiv.style.color = 'red';
        messageDiv.textContent = `Request failed: ${error.message}`;
    }

    setTimeout(() => {
        messageDiv.textContent = '';
    }, 3000);
}

let socket;
let sensorDataHistory = {
    distance: [],
    gyro: [],
    timestamps: []
};
let distanceChart, gyroChart;

function initWebSocket() {
    const token = getToken();
    const options = {};
    if (token) {
        options.query = { token: token };
    }
    socket = io(options);

    socket.on('connect', () => {
        console.log('Connected to WebSocket');
    });

    socket.on('disconnect', () => {
        console.log('Disconnected from WebSocket');
        updateConnectionStatus(false);
    });

    socket.on('system.connection_status', (data) => {
        updateConnectionStatus(data.connected);
    });

    socket.on('sensor.data', (data) => {
        updateSensorData(data);
    });

    socket.on('error', (error) => {
        console.error('WebSocket error:', error);
        showMessage(error.message, 'red');
    });

    socket.on('command.result', (result) => {
        console.log('Command result:', result);
        if (result.target === 'ping') {
            document.getElementById('ping-result').textContent =
                result.success ? 'Ping successful!' : 'Ping failed!';
        }
    });
}

function updateConnectionStatus(connected) {
    const statusText = document.getElementById('status-text');
    const statusDiv = document.getElementById('connection-status');

    if (connected) {
        statusText.textContent = 'Connected';
        statusDiv.style.borderColor = 'green';
        statusDiv.style.backgroundColor = '#e8f5e8';
    } else {
        statusText.textContent = 'Disconnected';
        statusDiv.style.borderColor = 'red';
        statusDiv.style.backgroundColor = '#ffe8e8';
    }
}

function updateSensorData(data) {
    const now = new Date();
    sensorDataHistory.timestamps.push(now);

    if (data.distance) {
        document.getElementById('distance-display').textContent =
            `Distance: ${data.distance.distance_cm} cm`;
        sensorDataHistory.distance.push(data.distance.distance_cm);
    }

    if (data.gyro) {
        document.getElementById('gyro-display').textContent =
            `Gyro: Accel(${data.gyro.accel.join(', ')}), Gyro(${data.gyro.gyro.join(', ')}), Temp(${data.gyro.temperature}°C)`;
        sensorDataHistory.gyro.push(data.gyro.accel[0]);
    }

    if (data.millis) {
        document.getElementById('millis-display').textContent =
            `Millis: ${data.millis.millis}`;
    }

    if (sensorDataHistory.timestamps.length > 50) {
        sensorDataHistory.timestamps.shift();
        sensorDataHistory.distance.shift();
        sensorDataHistory.gyro.shift();
    }

    updateCharts();
}

function updateCharts() {
    if (!distanceChart)
        initCharts();

    distanceChart.data.labels = sensorDataHistory.timestamps.map(t => t.toLocaleTimeString());
    distanceChart.data.datasets[0].data = sensorDataHistory.distance;
    distanceChart.update();

    gyroChart.data.labels = sensorDataHistory.timestamps.map(t => t.toLocaleTimeString());
    gyroChart.data.datasets[0].data = sensorDataHistory.gyro;
    gyroChart.update();
}

function initCharts() {
    const distanceCtx = document.getElementById('distanceChart').getContext('2d');
    distanceChart = new Chart(distanceCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Distance (cm)',
                data: [],
                borderColor: 'rgb(75, 192, 192)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });

    const gyroCtx = document.getElementById('gyroChart').getContext('2d');
    gyroChart = new Chart(gyroCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Accel X',
                data: [],
                borderColor: 'rgb(255, 99, 132)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function sendMotorCommand(command) {
    const speed = parseInt(document.getElementById('motor-speed').value);
    socket.emit('robot.motors', {
        action: command,
        speed: speed
    });
}

function sendServoCommand(command) {
    const channel = parseInt(document.getElementById('servo-channel').value);
    const angle = parseInt(document.getElementById('servo-angle').value);
    socket.emit('robot.servo', {
        action: command,
        channel: channel,
        angle: angle
    });
}

function sendPing() {
    socket.emit('robot.ping', {});
}

document.getElementById('motor-speed').addEventListener('input', function () {
    document.getElementById('speed-value').textContent = this.value;
});

document.getElementById('servo-angle').addEventListener('input', function () {
    document.getElementById('angle-value').textContent = this.value;
});

function showMessage(message, color = 'green') {
    const messageDiv = document.getElementById('message');
    messageDiv.style.color = color;
    messageDiv.textContent = message;
    setTimeout(() => {
        messageDiv.textContent = '';
    }, 3000);
}

let webcamStreamActive = false;

function startWebcamStream() {
    if (webcamStreamActive) return;

    const streamImg = document.getElementById('webcam-stream');
    const loadingDiv = document.getElementById('webcam-loading');
    const errorDiv = document.getElementById('webcam-error');
    const statusSpan = document.getElementById('webcam-status');
    const startBtn = document.getElementById('start-webcam-btn');
    const stopBtn = document.getElementById('stop-webcam-btn');

    try {
        const token = getToken();
        const streamUrl = `/api/webcam/stream?token=${encodeURIComponent(token)}`;

        streamImg.style.display = 'none';
        loadingDiv.style.display = 'flex';
        errorDiv.style.display = 'none';
        statusSpan.textContent = 'Status: Connecting...';
        startBtn.disabled = true;
        stopBtn.disabled = false;

        streamImg.src = streamUrl;
        streamImg.onload = function () {
            loadingDiv.style.display = 'none';
            streamImg.style.display = 'block';
            statusSpan.textContent = 'Status: Streaming';
            webcamStreamActive = true;
            showMessage('Webcam stream started', 'green');
        };

        streamImg.onerror = function () {
            loadingDiv.style.display = 'none';
            errorDiv.style.display = 'flex';
            statusSpan.textContent = 'Status: Error';
            startBtn.disabled = false;
            stopBtn.disabled = true;
            webcamStreamActive = false;
            showMessage('Failed to start webcam stream', 'red');
        };

    } catch (error) {
        loadingDiv.style.display = 'none';
        errorDiv.style.display = 'flex';
        statusSpan.textContent = 'Status: Error';
        startBtn.disabled = false;
        stopBtn.disabled = true;
        webcamStreamActive = false;
        showMessage(`Webcam error: ${error.message}`, 'red');
    }
}

function stopWebcamStream() {
    if (!webcamStreamActive) return;

    const streamImg = document.getElementById('webcam-stream');
    const loadingDiv = document.getElementById('webcam-loading');
    const errorDiv = document.getElementById('webcam-error');
    const statusSpan = document.getElementById('webcam-status');
    const startBtn = document.getElementById('start-webcam-btn');
    const stopBtn = document.getElementById('stop-webcam-btn');

    streamImg.src = '';
    streamImg.style.display = 'none';
    loadingDiv.style.display = 'none';
    errorDiv.style.display = 'none';
    statusSpan.textContent = 'Status: Stopped';
    startBtn.disabled = false;
    stopBtn.disabled = true;
    webcamStreamActive = false;

    showMessage('Webcam stream stopped', 'green');
}

document.addEventListener('DOMContentLoaded', function () {
    loadEmotions();
    initWebSocket();
    initCharts();
    loadCurrentSettings();

});