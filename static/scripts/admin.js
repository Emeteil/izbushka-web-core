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

    socket.on('voice.wake_word_changed', (data) => renderWakeWord(!!data.enabled));
    socket.on('voice.connected', loadWakeWord);
    socket.on('voice.disconnected', () => renderWakeWord(null));

    socket.on('sensor.data', (data) => {
        updateSensorData(data);
    });

    socket.on('error', (error) => {
        console.error('WebSocket error:', error);
        showMessage(error.message, 'red');
    });

    socket.on('command.result', (result) => {
        console.log('Command result:', result);
        if (result.target === 'gps') {
            document.getElementById('gps-refresh').disabled = false;
        }
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
    if (data.millis) {
        document.getElementById('millis-display').textContent =
            `Millis: ${data.millis.millis}`;
    }
    if (data.distance && Array.isArray(data.distance.sensors)) {
        updateDistance(data.distance.sensors);
    }
    if (data.magnetometer) {
        updateMagnetometer(data.magnetometer);
    }
    if ('gps' in data) {
        updateGps(data.gps);
    }
}

const MAG_STATUS_TEXT = {
    ok: 'Датчик работает',
    overflow: 'Переполнение: поле сильнее ±8 Гс (рядом магнит или мотор?)',
    no_data: 'Датчик найден, ждём первое измерение',
    not_found: 'Датчик не отвечает на I2C (адрес 0x2C)',
    bus_stuck: 'Шина I2C прижата: проверьте провода SCL (PB6) и SDA (PB7)',
    unknown: 'Неизвестный статус'
};
const MAG_REFERENCE_KEY = 'admin.magnetometer.reference';
const COMPASS_POINTS = ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'];
let magFiltered = null;
let magReference = loadMagReference();
let magLast = null;
let magArrivals = [];

function loadMagReference() {
    try {
        const saved = JSON.parse(localStorage.getItem(MAG_REFERENCE_KEY));
        return Array.isArray(saved) && saved.length === 3 ? saved : null;
    } catch (error) {
        return null;
    }
}

function saveMagReference(vector) {
    try {
        localStorage.setItem(MAG_REFERENCE_KEY, JSON.stringify(vector));
    } catch (error) {
        console.warn('reference not saved', error);
    }
}

function vecNorm(v) {
    return Math.hypot(v[0], v[1], v[2]);
}

function vecUnit(v) {
    const n = vecNorm(v);
    return n > 0 ? [v[0] / n, v[1] / n, v[2] / n] : null;
}

function headingOf(v) {
    return (Math.atan2(v[1], v[0]) * 180 / Math.PI + 360) % 360;
}

function compassPoint(deg) {
    return COMPASS_POINTS[Math.round(deg / 45) % 8];
}

function rotationBetween(from, to) {
    const a = vecUnit(from);
    const b = vecUnit(to);
    if (!a || !b) return null;
    const c = Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]));
    let axis = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
    const s = vecNorm(axis);
    if (s < 1e-9) {
        if (c > 0) return [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
        axis = Math.abs(a[0]) < 0.9 ? [0, -a[2], a[1]] : [-a[2], 0, a[0]];
    }
    const [x, y, z] = vecUnit(axis);
    const angle = Math.atan2(s, c);
    const cs = Math.cos(angle);
    const sn = Math.sin(angle);
    const t = 1 - cs;
    return [
        [t * x * x + cs, t * x * y - sn * z, t * x * z + sn * y],
        [t * x * y + sn * z, t * y * y + cs, t * y * z - sn * x],
        [t * x * z - sn * y, t * y * z + sn * x, t * z * z + cs]
    ];
}

function cubeTransform(r) {
    const m = [[0, -1, 0], [0, 0, -1], [-1, 0, 0]];
    const css = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
    for (let i = 0; i < 3; i++) {
        for (let j = 0; j < 3; j++) {
            let sum = 0;
            for (let k = 0; k < 3; k++) {
                for (let l = 0; l < 3; l++) {
                    sum += m[i][k] * r[k][l] * m[j][l];
                }
            }
            css[i][j] = sum;
        }
    }
    const v = [css[0][0], css[1][0], css[2][0], 0, css[0][1], css[1][1], css[2][1], 0,
        css[0][2], css[1][2], css[2][2], 0, 0, 0, 0, 1];
    return `matrix3d(${v.map(n => n.toFixed(5)).join(',')})`;
}

function updateMagnetometer(mag) {
    const now = performance.now();
    magArrivals.push(now);
    magArrivals = magArrivals.filter(t => now - t <= 2000);
    const span = (magArrivals[magArrivals.length - 1] - magArrivals[0]) / 1000;
    document.getElementById('mag-rate').textContent =
        span > 0 ? `${((magArrivals.length - 1) / span).toFixed(1)} Гц` : '--';

    const statusEl = document.getElementById('mag-status');
    statusEl.textContent = MAG_STATUS_TEXT[mag.status] || MAG_STATUS_TEXT.unknown;
    statusEl.style.color = mag.status === 'ok' ? 'green' : (mag.status === 'no_data' ? '#555' : 'red');
    document.getElementById('mag-raw').textContent = mag.raw ? mag.raw.join(' / ') : '--';

    if (!mag.ut) {
        ['mag-heading', 'mag-heading-rel', 'mag-tilt', 'mag-ut', 'mag-magnitude']
            .forEach(id => { document.getElementById(id).textContent = '--'; });
        return;
    }

    magFiltered = magFiltered
        ? magFiltered.map((v, i) => v + 0.3 * (mag.ut[i] - v))
        : mag.ut.slice();
    magLast = magFiltered;
    if (!magReference) {
        magReference = magFiltered.slice();
        saveMagReference(magReference);
    }

    const heading = headingOf(magFiltered);
    let relative = heading - headingOf(magReference);
    relative = ((relative + 540) % 360) - 180;
    const a = vecUnit(magFiltered);
    const b = vecUnit(magReference);
    const tilt = a && b ? Math.acos(Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))) * 180 / Math.PI : 0;

    document.getElementById('mag-heading').textContent = `${heading.toFixed(1)}° (${compassPoint(heading)})`;
    document.getElementById('mag-heading-rel').textContent = `${relative >= 0 ? '+' : ''}${relative.toFixed(1)}°`;
    document.getElementById('mag-tilt').textContent = `${tilt.toFixed(1)}°`;
    document.getElementById('mag-ut').textContent = mag.ut.map(v => `${v.toFixed(1)}`).join(' / ') + ' мкТл';
    document.getElementById('mag-magnitude').textContent = `${mag.magnitude_ut.toFixed(1)} мкТл`;

    const rotation = rotationBetween(magFiltered, magReference);
    if (rotation) {
        document.getElementById('mag-cube').style.transform = cubeTransform(rotation);
    }
}

function centerMagnetometer() {
    const info = document.getElementById('mag-center-info');
    if (!magLast) {
        info.textContent = 'нет данных с датчика';
        return;
    }
    magReference = magLast.slice();
    saveMagReference(magReference);
    info.textContent = `центр задан ${new Date().toLocaleTimeString()}`;
}

const GPS_FIX_TYPE = { 1: 'нет', 2: '2D', 3: '3D' };
const GPS_QUALITY = { 0: 'нет фикса', 1: 'GPS', 2: 'DGPS', 4: 'RTK', 5: 'RTK float', 6: 'счисление' };

function formatAge(ms) {
    if (ms === null || ms === undefined) return 'никогда';
    return ms < 1000 ? `${ms} мс` : `${(ms / 1000).toFixed(1)} с`;
}

function setText(id, text) {
    document.getElementById(id).textContent = text;
}

function updateGps(gps) {
    setText('gps-updated', `обновлено ${new Date().toLocaleTimeString()} · авто каждые 5 с`);
    if (!gps) {
        setText('gps-alive', 'нет ответа от микроконтроллера');
        document.getElementById('gps-alive').style.color = 'red';
        return;
    }

    const aliveEl = document.getElementById('gps-alive');
    aliveEl.textContent = gps.alive ? 'NMEA поступают' : 'модуль молчит (проверьте TX → PA3 и питание)';
    aliveEl.style.color = gps.alive ? 'green' : 'red';

    const fixEl = document.getElementById('gps-fix');
    fixEl.textContent = gps.position_valid
        ? `есть, ${GPS_FIX_TYPE[gps.fix_type] || '?'}`
        : 'нет (нужно открытое небо, первый поиск до 5 мин)';
    fixEl.style.color = gps.position_valid ? 'green' : '#b36b00';

    const pos = gps.position_valid;
    setText('gps-lat', pos ? `${gps.latitude.toFixed(7)}°` : '--');
    setText('gps-lon', pos ? `${gps.longitude.toFixed(7)}°` : '--');
    const map = document.getElementById('gps-map');
    map.innerHTML = '';
    if (pos) {
        const link = document.createElement('a');
        link.href = `https://www.openstreetmap.org/?mlat=${gps.latitude}&mlon=${gps.longitude}#map=18/${gps.latitude}/${gps.longitude}`;
        link.target = '_blank';
        link.rel = 'noopener';
        link.textContent = 'открыть в OpenStreetMap';
        map.appendChild(link);
    } else {
        map.textContent = '--';
    }
    setText('gps-alt', pos ? `${gps.altitude_m.toFixed(1)} м` : '--');
    setText('gps-geoid', pos ? `${gps.geoid_separation_m.toFixed(1)} м` : '--');
    setText('gps-speed', `${gps.speed_m_s.toFixed(2)} м/с (${(gps.speed_m_s * 3.6).toFixed(1)} км/ч)`);
    setText('gps-course', `${gps.course_deg.toFixed(1)}°`);
    setText('gps-time', `${gps.date || '----.--.--'} ${gps.time || '--:--:--'}`);
    setText('gps-sats', `${gps.satellites_used} / ${gps.satellites_in_view}`);
    const dop = v => (v === null ? '--' : v.toFixed(2));
    setText('gps-dop', `${dop(gps.hdop)} / ${dop(gps.pdop)} / ${dop(gps.vdop)}`);
    setText('gps-quality', `${gps.fix_quality} (${GPS_QUALITY[gps.fix_quality] || '?'})`);
    setText('gps-fix-age', formatAge(gps.fix_age_ms));
    setText('gps-sentence-age', formatAge(gps.sentence_age_ms));
    setText('gps-counters', `${gps.sentences_ok} / ${gps.checksum_errors}`);

    const body = document.getElementById('gps-satellites');
    body.innerHTML = '';
    if (!gps.satellites.length) {
        body.innerHTML = '<tr><td colspan="4">Нет данных о спутниках</td></tr>';
        return;
    }
    gps.satellites.forEach(sat => {
        const row = document.createElement('tr');
        const cells = [
            sat.prn,
            sat.elevation === null ? '--' : `${sat.elevation}°`,
            sat.azimuth === null ? '--' : `${sat.azimuth}°`
        ];
        cells.forEach(value => {
            const cell = document.createElement('td');
            cell.textContent = value;
            row.appendChild(cell);
        });
        const snrCell = document.createElement('td');
        if (sat.snr === null) {
            snrCell.textContent = 'не отслеживается';
        } else {
            const bar = document.createElement('span');
            bar.className = 'snr-bar';
            bar.style.width = `${Math.min(sat.snr, 50) * 2}px`;
            snrCell.appendChild(bar);
            snrCell.appendChild(document.createTextNode(`${sat.snr} дБ`));
        }
        row.appendChild(snrCell);
        body.appendChild(row);
    });
}

function requestGps() {
    const button = document.getElementById('gps-refresh');
    button.disabled = true;
    setText('gps-updated', 'запрашиваю...');
    socket.emit('robot.gps', {});
    setTimeout(() => { button.disabled = false; }, 2000);
}

const DISTANCE_MAX_MM = 4000;
const DISTANCE_SENSOR_COUNT = 8;
let distanceSensors = [];
let distanceArrivals = [];

function updateDistance(sensors) {
    distanceSensors = sensors;
    const now = performance.now();
    distanceArrivals.push(now);
    distanceArrivals = distanceArrivals.filter(t => now - t <= 3000);

    const span = (distanceArrivals[distanceArrivals.length - 1] - distanceArrivals[0]) / 1000;
    const rate = span > 0 ? ((distanceArrivals.length - 1) / span).toFixed(1) : '--';
    const ok = sensors.filter(s => s.status === 'ok').length;
    document.getElementById('distance-info').textContent =
        `${rate} Гц · ${ok}/${sensors.length} датчиков с замером · обновлено ${new Date().toLocaleTimeString()}`;

    drawDistanceStem();
}

function initCharts() {
    drawDistanceStem();
    window.addEventListener('resize', drawDistanceStem);
}

function drawDistanceStem() {
    const canvas = document.getElementById('distance-stem');
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);

    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    ctx.font = '12px monospace';

    const pad = { left: 56, right: 12, top: 22, bottom: 30 };
    const plotW = width - pad.left - pad.right;
    const plotH = height - pad.top - pad.bottom;
    const baseY = pad.top + plotH;
    const yOf = mm => baseY - (Math.min(mm, DISTANCE_MAX_MM) / DISTANCE_MAX_MM) * plotH;

    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (let mm = 0; mm <= DISTANCE_MAX_MM; mm += 500) {
        const y = yOf(mm);
        ctx.strokeStyle = mm === 0 ? '#888' : '#e6e6e6';
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(pad.left + plotW, y);
        ctx.stroke();
        ctx.fillStyle = '#666';
        ctx.fillText(`${mm} мм`, pad.left - 6, y);
    }

    const count = Math.max(distanceSensors.length, DISTANCE_SENSOR_COUNT);
    for (let i = 0; i < count; i++) {
        const x = pad.left + (i + 0.5) * plotW / count;
        const sensor = distanceSensors[i] || { mm: null, status: 'none' };

        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillStyle = '#333';
        ctx.fillText(`#${i}`, x, baseY + 8);
        ctx.textBaseline = 'bottom';

        if (sensor.status === 'ok') {
            const y = yOf(sensor.mm);
            ctx.strokeStyle = '#1f5fbf';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(x, baseY);
            ctx.lineTo(x, y);
            ctx.stroke();
            ctx.fillStyle = '#1f5fbf';
            ctx.beginPath();
            ctx.arc(x, y, 5, 0, 2 * Math.PI);
            ctx.fill();
            ctx.fillStyle = '#17202b';
            ctx.fillText(`${sensor.mm}`, x, y - 8);
        } else if (sensor.status === 'far') {
            const y = yOf(DISTANCE_MAX_MM);
            ctx.strokeStyle = '#9aa5b4';
            ctx.lineWidth = 1.5;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.moveTo(x, baseY);
            ctx.lineTo(x, y);
            ctx.stroke();
            ctx.setLineDash([]);
            ctx.beginPath();
            ctx.arc(x, y, 5, 0, 2 * Math.PI);
            ctx.stroke();
            ctx.fillStyle = '#5b6676';
            ctx.fillText('нет эха', x, y - 8);
        } else {
            const color = sensor.status === 'error' ? '#d43a2f' : '#bbb';
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(x - 5, baseY - 11);
            ctx.lineTo(x + 5, baseY - 1);
            ctx.moveTo(x + 5, baseY - 11);
            ctx.lineTo(x - 5, baseY - 1);
            ctx.stroke();
            ctx.fillStyle = color;
            ctx.fillText(sensor.status === 'error' ? 'ошибка' : '--', x, baseY - 14);
        }
        ctx.lineWidth = 1;
    }
}

function sendMotorCommand(command) {
    const speed = parseInt(document.getElementById('motor-speed').value);
    socket.emit('robot.motors', {
        action: command,
        speed: speed
    });
}

function sendPing() {
    document.getElementById('ping-result').textContent = '';
    socket.emit('robot.ping', {});
}

document.getElementById('motor-speed').addEventListener('input', function () {
    document.getElementById('speed-value').textContent = this.value;
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

function renderWakeWord(enabled) {
    const toggle = document.getElementById('wakeword-toggle');
    const label = document.getElementById('wakeword-state');
    const known = typeof enabled === 'boolean';
    toggle.disabled = !known;
    toggle.checked = enabled === true;
    label.textContent = !known ? 'voice-interface не подключён' : (enabled ? 'включён' : 'выключен');
}

async function loadWakeWord() {
    try {
        const response = await fetch('/api/voice/status', {
            headers: { 'Authorization': `Bearer ${getToken()}` }
        });
        const body = await response.json();
        renderWakeWord(body.data ? body.data.wake_word_enabled : null);
    } catch (error) {
        renderWakeWord(null);
    }
}

document.getElementById('wakeword-toggle').addEventListener('change', async function () {
    const wanted = this.checked;
    this.disabled = true;
    try {
        const response = await fetch('/api/voice/wake-word', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${getToken()}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: wanted })
        });
        const body = await response.json();
        if (!response.ok) throw new Error(body.error ? body.error.message : response.statusText);
        renderWakeWord(body.data.wake_word_enabled);
    } catch (error) {
        showMessage(`Wake word: ${error.message}`, 'red');
        await loadWakeWord();
    }
});

document.addEventListener('DOMContentLoaded', function () {
    loadWakeWord();
    loadEmotions();
    initWebSocket();
    initCharts();
    loadCurrentSettings();

});