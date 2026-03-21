const joystickManager = nipplejs.create({
    zone: document.getElementById('joystick-container'),
    mode: 'static',
    position: { left: '50%', top: '50%' },
    color: '#00f3ff',
    size: 150
});

const token = getCookie('token');
const socket = io({
    query: { token: token }
});

let lastCommand = 'stop';
let currentSpeed = 150;

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

joystickManager.on('move', function (evt, data) {
    if (data.direction) {
        if (data.force < 0.2) return;

        const angle = data.angle.degree;
        const force = Math.min(data.force, 2.0);

        currentSpeed = Math.floor(Math.min(255, Math.max(100, force * 100)));
        document.getElementById('speed-val').textContent = currentSpeed;

        let command = 'stop';

        if (angle > 90 - 45 && angle < 90 + 45)
            command = 'move_forward';
        else if (angle > 270 - 45 && angle < 270 + 45)
            command = 'move_backward';
        else if (angle > 180 - 45 && angle < 180 + 45)
            command = 'turn_left';
        else if (angle < 45 || angle > 315)
            command = 'turn_right';

        if (command !== lastCommand || command !== 'stop') {
            sendCommand(command, currentSpeed);
            lastCommand = command;
            updateStatus(`MOVING: ${command.toUpperCase()}`);
        }
    }
});

joystickManager.on('end', function () {
    sendCommand('stop', 0);
    lastCommand = 'stop';
    currentSpeed = 0;
    document.getElementById('speed-val').textContent = currentSpeed;
    updateStatus('SYSTEM IDLE');
});

function sendCommand(cmd, speed) {
    socket.emit('robot.motors', {
        action: cmd,
        speed: speed,
        wait_response: false
    });
}

function rotateTurret(direction) {
    let currentAngle = parseInt(localStorage.getItem('turret_angle') || '90');
    const step = 15;

    if (direction === 'left') currentAngle = Math.min(180, currentAngle + step);
    if (direction === 'right') currentAngle = Math.max(0, currentAngle - step);

    localStorage.setItem('turret_angle', currentAngle);

    socket.emit('robot.servo', {
        action: 'move_smooth',
        channel: 0,
        angle: currentAngle,
        wait_response: false
    });
    updateStatus(`TURRET: ${currentAngle}°`);
}

socket.on('connect', () => {
    document.getElementById('connection-indicator').classList.add('connected');
    document.getElementById('connection-indicator').classList.remove('disconnected');
    document.getElementById('sys-status').textContent = 'ONLINE';
    updateStatus('UPLINK ESTABLISHED');
});

socket.on('disconnect', () => {
    document.getElementById('connection-indicator').classList.remove('connected');
    document.getElementById('connection-indicator').classList.add('disconnected');
    document.getElementById('sys-status').textContent = 'OFFLINE';
    updateStatus('CONNECTION LOST');
});

socket.on('sensor.data', (data) => {
    if (data.distance) {
        document.getElementById('sensor-dist').textContent = data.distance.distance_cm + ' CM';
    }
    if (data.gyro) {
        document.getElementById('sensor-temp').textContent = data.gyro.temperature + '°C';
        document.getElementById('sensor-gyro').textContent = `X:${data.gyro.gyro[0]}`;
    }
});

function updateStatus(msg) {
    const log = document.getElementById('log-output');
    const entry = document.createElement('div');
    entry.textContent = `> ${msg}`;
    log.prepend(entry);
    if (log.children.length > 5) log.lastChild.remove();
}

let streamController;
let lastBlobUrl;
let streamWatchdog;

async function initStream() {
    if (streamController) streamController.abort();
    streamController = new AbortController();

    if (streamWatchdog) clearInterval(streamWatchdog);

    const img = document.getElementById('video-background');

    let lastPacketTime = Date.now();
    streamWatchdog = setInterval(() => {
        if (Date.now() - lastPacketTime > 3000) {
            if (streamController) streamController.abort();
        }
    }, 1000);

    try {
        const response = await fetch(`/api/webcam/stream?token=${encodeURIComponent(token)}`, {
            signal: streamController.signal
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        if (!response.body) throw new Error('No body');

        const reader = response.body.getReader();
        let buffer = new Uint8Array(0);

        window.videoLoaded = true;
        updateStatus('VIDEO FEED ACTIVE');

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            lastPacketTime = Date.now();

            const newBuffer = new Uint8Array(buffer.length + value.length);
            newBuffer.set(buffer);
            newBuffer.set(value, buffer.length);
            buffer = newBuffer;

            let lastEOI = -1;
            for (let i = buffer.length - 2; i >= 0; i--) {
                if (buffer[i] === 0xFF && buffer[i + 1] === 0xD9) {
                    lastEOI = i;
                    break;
                }
            }

            if (lastEOI !== -1) {
                let lastSOI = -1;
                for (let i = lastEOI - 2; i >= 0; i--) {
                    if (buffer[i] === 0xFF && buffer[i + 1] === 0xD8) {
                        lastSOI = i;
                        break;
                    }
                }

                if (lastSOI !== -1) {
                    const jpegData = buffer.slice(lastSOI, lastEOI + 2);
                    const blob = new Blob([jpegData], { type: 'image/jpeg' });
                    const url = URL.createObjectURL(blob);

                    img.src = url;

                    if (lastBlobUrl) URL.revokeObjectURL(lastBlobUrl);
                    lastBlobUrl = url;

                    buffer = buffer.slice(lastEOI + 2);
                }
            }

            if (buffer.length > 5000000) buffer = new Uint8Array(0);
        }

    } catch (error) {
        if (error.name === 'AbortError') return;
        console.error('Stream error:', error);

        if (streamWatchdog) clearInterval(streamWatchdog);
        window.videoLoaded = true;
        updateStatus('VIDEO LOST. RETRY IN 1S...');

        setTimeout(initStream, 1000);
    }
}

document.getElementById('btn-turret-left').addEventListener('click', () => rotateTurret('left'));
document.getElementById('btn-turret-right').addEventListener('click', () => rotateTurret('right'));

async function loadEmotions() {
    try {
        const response = await fetch('/api/emotions', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await response.json();

        if (data.status === 'success') {
            const select = document.getElementById('emotion-select');
            select.innerHTML = '';

            data.data.emotions.forEach(emotion => {
                const option = document.createElement('option');
                option.value = emotion.id;
                option.textContent = `${emotion.emoji} ${emotion.name}`;
                select.appendChild(option);
            });

            if (data.data.current_emotion) {
                select.value = data.data.current_emotion;
                setUIEmotion(data.data.current_emotion);
            }

            select.addEventListener('change', (e) => {
                setEmotion(e.target.value);
            });
        }
    } catch (error) {
        console.error('Error loading emotions:', error);
    }
}

async function setEmotion(emotionId) {
    updateStatus(`EMOTION: ${emotionId.toUpperCase()}`);
    setUIEmotion(emotionId);

    try {
        await fetch('/api/emotions/current', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ emotion: emotionId })
        });
    } catch (error) {
        console.error('Error setting emotion:', error);
    }
}

function setUIEmotion(emotionId) {
    document.body.className = '';
    document.getElementById('current-emotion').textContent = emotionId.toUpperCase();

    if (['aggressive', 'anger', 'angry'].some(k => emotionId.includes(k))) {
        document.body.classList.add('theme-aggressive');
    } else if (['happy', 'joy', 'excited'].some(k => emotionId.includes(k))) {
        document.body.classList.add('theme-happy');
    }
}

window.onload = () => {
    const minLoadTime = 2000;
    const startTime = Date.now();
    window.videoLoaded = false;

    initStream();
    loadEmotions();

    const checkLoad = setInterval(() => {
        const elapsed = Date.now() - startTime;

        if (elapsed > minLoadTime && window.videoLoaded) {
            clearInterval(checkLoad);
            const loader = document.getElementById('loading-screen');
            loader.style.opacity = '0';
            loader.style.transition = 'opacity 1s ease';
            setTimeout(() => {
                loader.style.display = 'none';
            }, 1000);
        }
    }, 100);
};