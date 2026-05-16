(function () {
    'use strict';

    const ACTION_INTERVAL_MS = 17;
    const SPEED_INTERVAL_MS = 230;
    const SPEED_CRITICAL_INTERVAL_MS = 50;
    const SPEED_ZONES = 4;
    const STOP_RETRY_MS = 100;
    const MIN_SPEED = 25;
    const MAX_SPEED = 200;
    const MAX_EVENTS = 60;
    const DISTANCE_MAX_CM = 200;

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }

    function getToken() {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('token') || getCookie('token');
    }

    const token = getToken();
    const authHeaders = { 'Authorization': `Bearer ${token}` };

    const $ = (id) => document.getElementById(id);

    const els = {
        dotUplink: $('dot-uplink'),
        dotRobot: $('dot-robot'),
        dotVoice: $('dot-voice'),
        valUplink: $('val-uplink'),
        valRobot: $('val-robot'),
        valVoice: $('val-voice'),
        valDistance: $('val-distance'),
        valEmotion: $('val-emotion'),
        video: $('video'),
        videoStatus: $('video-status'),
        btnReloadVideo: $('btn-reload-video'),
        joystick: $('joystick'),
        curAction: $('cur-action'),
        curSpeed: $('cur-speed'),
        btnTrigger: $('btn-trigger'),
        btnStop: $('btn-stop'),
        btnMic: $('btn-mic'),
        btnSpeaker: $('btn-speaker'),
        voiceBadge: $('voice-status-badge'),
        emotionsGrid: $('emotions-grid'),
        eventList: $('event-list'),
        questionList: $('question-list'),
        btnClearEvents: $('btn-clear-events'),
        btnReloadQuestions: $('btn-reload-questions'),
        manualForm: $('manual-answer-form'),
        manualQuestion: $('manual-question'),
        manualAnswer: $('manual-answer'),
        manualTopic: $('manual-topic'),
        distanceFill: $('distance-fill'),
        distanceLabel: $('distance-label'),
    };

    function pushEvent(tag, message, kind = '') {
        const li = document.createElement('li');
        if (kind) li.classList.add(kind);
        const time = new Date().toTimeString().slice(0, 8);
        li.innerHTML = `<span class="ev-time">${time}</span><span class="ev-tag">${tag}</span><span class="ev-msg"></span>`;
        li.querySelector('.ev-msg').textContent = message;
        els.eventList.prepend(li);
        while (els.eventList.children.length > MAX_EVENTS) {
            els.eventList.removeChild(els.eventList.lastChild);
        }
    }

    function setDot(el, state) {
        el.classList.remove('ok', 'warn', 'err');
        if (state) el.classList.add(state);
    }

    function setVoiceBadge(status) {
        els.voiceBadge.classList.remove('active', 'error', 'idle');
        els.voiceBadge.textContent = status || 'disconnected';
        if (status === 'active') els.voiceBadge.classList.add('active');
        else if (status === 'idle' || status === 'wake_word_detected') els.voiceBadge.classList.add('idle');
        else if (status === 'error') els.voiceBadge.classList.add('error');
    }

    class WSClient {
        constructor() {
            this._ws = null;
            this._reconnectDelay = 1000;
            this._handlers = {};
        }

        on(event, handler) {
            (this._handlers[event] ||= []).push(handler);
        }

        connect() {
            const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
            const url = `${proto}//${location.host}/ws?token=${encodeURIComponent(token)}`;
            const ws = new WebSocket(url);
            this._ws = ws;

            ws.onopen = () => {
                setDot(els.dotUplink, 'ok');
                els.valUplink.textContent = 'ONLINE';
                this._reconnectDelay = 1000;
                this._emit('open');
            };

            ws.onmessage = (e) => {
                let msg;
                try { msg = JSON.parse(e.data); } catch { return; }
                this._emit(msg.event, msg.data || {});
            };

            ws.onclose = () => {
                setDot(els.dotUplink, 'err');
                els.valUplink.textContent = 'OFFLINE';
                setTimeout(() => this.connect(), this._reconnectDelay);
                this._reconnectDelay = Math.min(this._reconnectDelay * 2, 10000);
            };

            ws.onerror = () => { try { ws.close(); } catch (_) {} };
        }

        _emit(event, data) {
            (this._handlers[event] || []).forEach(h => {
                try { h(data); } catch (err) { console.error(err); }
            });
        }

        send(event, data) {
            if (this._ws && this._ws.readyState === WebSocket.OPEN) {
                this._ws.send(JSON.stringify({ event, data }));
            }
        }
    }

    const ws = new WSClient();

    ws.on('system.connection_status', (data) => {
        const connected = !!data.connected;
        setDot(els.dotRobot, connected ? 'ok' : 'err');
        els.valRobot.textContent = connected ? 'ONLINE' : 'OFFLINE';
    });

    ws.on('system.emotion_changed', (data) => {
        const id = (data.emotion || '').toString();
        els.valEmotion.textContent = id.toUpperCase() || '—';
        document.querySelectorAll('.emotion-btn').forEach(b => {
            b.classList.toggle('active', b.dataset.id === id);
        });
    });

    ws.on('sensor.data', (data) => {
        if (data.distance && data.distance.distance_cm != null) {
            const cm = Number(data.distance.distance_cm);
            const pct = Math.max(0, Math.min(100, (cm / DISTANCE_MAX_CM) * 100));
            els.valDistance.textContent = `${cm} см`;
            els.distanceLabel.textContent = `${cm} см`;
            els.distanceFill.style.width = `${pct}%`;
        }
    });

    ws.on('voice.connected', (data) => {
        setDot(els.dotVoice, 'ok');
        els.valVoice.textContent = data.status || 'idle';
        setVoiceBadge(data.status || 'idle');
        pushEvent('VOICE', 'Голосовой интерфейс подключён');
    });

    ws.on('voice.disconnected', () => {
        setDot(els.dotVoice, 'err');
        els.valVoice.textContent = 'OFFLINE';
        setVoiceBadge('disconnected');
        pushEvent('VOICE', 'Голосовой интерфейс отключён', 'error');
    });

    ws.on('voice.status_changed', (data) => {
        const status = data.status || 'idle';
        els.valVoice.textContent = status.toUpperCase();
        setVoiceBadge(status);
        setDot(els.dotVoice, status === 'active' ? 'ok' : status === 'wake_word_detected' ? 'warn' : 'ok');
        pushEvent('VOICE', `Статус: ${status}`);
    });

    ws.on('voice.message', (data) => {
        pushEvent('SAY', `${data.role || 'assistant'}: ${data.text || ''}`);
    });

    ws.on('voice.tool_call', (data) => {
        pushEvent('TOOL', `${data.name || '?'}(${data.args || ''})`, 'tool');
    });

    ws.on('voice.tool_result', (data) => {
        pushEvent('TOOL', `${data.name || '?'} → ${String(data.result || '').slice(0, 120)}`, 'tool');
    });

    ws.on('voice.error', (data) => {
        pushEvent('ERR', data.message || 'Voice error', 'error');
    });

    ws.on('question.logged', (data) => {
        prependQuestion(data);
        pushEvent('Q', data.question || '');
    });

    ws.on('question.cleared', () => {
        renderQuestions([]);
    });

    function angleToAction(angle) {
        if (angle >= 45 && angle < 135) return 'move_forward';
        if (angle >= 135 && angle < 225) return 'turn_left';
        if (angle >= 225 && angle < 315) return 'move_backward';
        return 'turn_right';
    }

    function forceToSpeed(force) {
        const clamped = Math.min(Math.max(force, 0), 2.0);
        const ratio = clamped / 2.0;
        return Math.round(MIN_SPEED + ratio * (MAX_SPEED - MIN_SPEED));
    }

    function getSpeedZone(speed) {
        const zoneSize = (MAX_SPEED - MIN_SPEED) / SPEED_ZONES;
        return Math.min(Math.floor((speed - MIN_SPEED) / zoneSize), SPEED_ZONES - 1);
    }

    class MotorController {
        constructor() {
            this.lastAction = null;
            this.lastSpeed = null;
            this.actionTimer = null;
            this.speedTimer = null;
            this.criticalTimer = null;
            this.stopRetryTimer = null;
            this.tActionSend = 0;
            this.tSpeedSend = 0;
            this.tCriticalSend = 0;
        }

        send(action, speed) {
            ws.send('robot.motors', { action, speed, wait_response: false });
            this.lastAction = action;
            this.lastSpeed = speed;
            els.curAction.textContent = action.toUpperCase();
            els.curSpeed.textContent = speed;
        }

        schedule(action, speed) {
            const now = Date.now();
            const actionChanged = action !== this.lastAction;
            const speedChanged = speed !== this.lastSpeed;
            if (!actionChanged && !speedChanged) return;

            this._cancelStopRetry();

            if (actionChanged) {
                const elapsed = now - this.tActionSend;
                if (elapsed >= ACTION_INTERVAL_MS) {
                    this.send(action, speed);
                    this.tActionSend = now;
                    this.tSpeedSend = now;
                    this._clearTimer('actionTimer');
                    this._clearTimer('speedTimer');
                } else if (!this.actionTimer) {
                    this.actionTimer = setTimeout(() => {
                        this.actionTimer = null;
                        if (action !== this.lastAction || speed !== this.lastSpeed) {
                            this.send(action, speed);
                            this.tActionSend = Date.now();
                            this.tSpeedSend = Date.now();
                        }
                    }, ACTION_INTERVAL_MS - elapsed);
                }
                return;
            }

            if (speedChanged) {
                const prevZone = getSpeedZone(this.lastSpeed ?? MIN_SPEED);
                const newZone = getSpeedZone(speed);
                const isCritical = newZone !== prevZone;

                if (isCritical) {
                    const elapsed = now - this.tCriticalSend;
                    if (elapsed >= SPEED_CRITICAL_INTERVAL_MS) {
                        this.send(action, speed);
                        this.tCriticalSend = now;
                        this.tSpeedSend = now;
                        this._clearTimer('criticalTimer');
                        this._clearTimer('speedTimer');
                    } else if (!this.criticalTimer) {
                        this.criticalTimer = setTimeout(() => {
                            this.criticalTimer = null;
                            if (speed !== this.lastSpeed) {
                                this.send(action, speed);
                                this.tCriticalSend = Date.now();
                                this.tSpeedSend = Date.now();
                            }
                        }, SPEED_CRITICAL_INTERVAL_MS - elapsed);
                    }
                } else {
                    const elapsed = now - this.tSpeedSend;
                    if (elapsed >= SPEED_INTERVAL_MS) {
                        this.send(action, speed);
                        this.tSpeedSend = now;
                        this._clearTimer('speedTimer');
                    } else if (!this.speedTimer) {
                        this.speedTimer = setTimeout(() => {
                            this.speedTimer = null;
                            if (speed !== this.lastSpeed) {
                                this.send(action, speed);
                                this.tSpeedSend = Date.now();
                            }
                        }, SPEED_INTERVAL_MS - elapsed);
                    }
                }
            }
        }

        stop() {
            this._clearTimer('actionTimer');
            this._clearTimer('speedTimer');
            this._clearTimer('criticalTimer');

            if (this.lastAction !== 'stop') {
                this.send('stop', 0);
                this._scheduleStopRetry();
            }
            els.curAction.textContent = 'IDLE';
            els.curSpeed.textContent = 0;
        }

        _clearTimer(key) {
            if (this[key]) { clearTimeout(this[key]); this[key] = null; }
        }

        _cancelStopRetry() {
            if (this.stopRetryTimer) { clearTimeout(this.stopRetryTimer); this.stopRetryTimer = null; }
        }

        _scheduleStopRetry() {
            this._cancelStopRetry();
            this.stopRetryTimer = setTimeout(() => {
                this.stopRetryTimer = null;
                this.send('stop', 0);
            }, STOP_RETRY_MS);
        }
    }

    const motors = new MotorController();

    const joystick = nipplejs.create({
        zone: els.joystick,
        mode: 'static',
        position: { left: '50%', top: '50%' },
        color: '#4a8cff',
        size: 130,
    });

    joystick.on('move', (_e, data) => {
        if (!data.direction) return;
        motors.schedule(angleToAction(data.angle.degree), forceToSpeed(data.force));
    });

    joystick.on('end', () => motors.stop());

    document.querySelectorAll('[data-motor]').forEach(btn => {
        btn.addEventListener('mousedown', () => {
            const action = btn.dataset.motor;
            if (action === 'stop') motors.stop();
            else motors.schedule(action, 150);
        });
        btn.addEventListener('mouseup', () => {
            if (btn.dataset.motor !== 'stop') motors.stop();
        });
        btn.addEventListener('mouseleave', () => {
            if (btn.dataset.motor !== 'stop' && motors.lastAction === btn.dataset.motor) motors.stop();
        });
    });

    const KEY_TO_ACTION = {
        'KeyW': 'move_forward', 'ArrowUp': 'move_forward',
        'KeyS': 'move_backward', 'ArrowDown': 'move_backward',
        'KeyA': 'turn_left', 'ArrowLeft': 'turn_left',
        'KeyD': 'turn_right', 'ArrowRight': 'turn_right',
    };

    const heldKeys = new Set();

    document.addEventListener('keydown', (e) => {
        if (e.repeat) return;
        if (e.target.matches('textarea, input, select')) return;
        const action = KEY_TO_ACTION[e.code];
        if (!action) return;
        e.preventDefault();
        heldKeys.add(e.code);
        motors.schedule(action, 150);
    });

    document.addEventListener('keyup', (e) => {
        if (!KEY_TO_ACTION[e.code]) return;
        heldKeys.delete(e.code);
        if (heldKeys.size === 0) motors.stop();
    });

    let streamController = null;
    let streamWatchdog = null;
    let lastBlobUrl = null;

    async function startVideo() {
        if (streamController) streamController.abort();
        streamController = new AbortController();
        if (streamWatchdog) clearInterval(streamWatchdog);

        let lastPacket = Date.now();
        streamWatchdog = setInterval(() => {
            if (Date.now() - lastPacket > 3000) {
                if (streamController) streamController.abort();
            }
        }, 1000);

        try {
            const res = await fetch(`/api/webcam/stream?token=${encodeURIComponent(token)}`, {
                signal: streamController.signal,
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            els.videoStatus.style.display = 'none';

            const reader = res.body.getReader();
            let buffer = new Uint8Array(0);

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                lastPacket = Date.now();

                const next = new Uint8Array(buffer.length + value.length);
                next.set(buffer);
                next.set(value, buffer.length);
                buffer = next;

                let lastEOI = -1;
                for (let i = buffer.length - 2; i >= 0; i--) {
                    if (buffer[i] === 0xFF && buffer[i + 1] === 0xD9) { lastEOI = i; break; }
                }
                if (lastEOI === -1) continue;

                let lastSOI = -1;
                for (let i = lastEOI - 2; i >= 0; i--) {
                    if (buffer[i] === 0xFF && buffer[i + 1] === 0xD8) { lastSOI = i; break; }
                }
                if (lastSOI === -1) continue;

                const blob = new Blob([buffer.slice(lastSOI, lastEOI + 2)], { type: 'image/jpeg' });
                const url = URL.createObjectURL(blob);
                els.video.src = url;
                if (lastBlobUrl) URL.revokeObjectURL(lastBlobUrl);
                lastBlobUrl = url;

                buffer = buffer.slice(lastEOI + 2);
                if (buffer.length > 5_000_000) buffer = new Uint8Array(0);
            }
        } catch (err) {
            if (err.name === 'AbortError') return;
            els.videoStatus.textContent = 'Видео недоступно, переподключение…';
            els.videoStatus.style.display = '';
            setTimeout(startVideo, 1500);
        }
    }

    els.btnReloadVideo.addEventListener('click', () => {
        els.videoStatus.textContent = 'Перезапуск потока…';
        els.videoStatus.style.display = '';
        startVideo();
    });

    const voice = new VoiceChannel({ token });

    function syncVoiceButtons() {
        els.btnMic.classList.toggle('active', voice.micEnabled);
        els.btnSpeaker.classList.toggle('active', voice.speakerEnabled);
    }
    voice.onStatusChange = syncVoiceButtons;

    els.btnMic.addEventListener('click', async () => {
        els.btnMic.disabled = true;
        try {
            if (voice.micEnabled) {
                await voice.setMic(false);
            } else {
                if (!voice.speakerEnabled) await voice.setSpeaker(true);
                await voice.setMic(true);
            }
        } catch (e) {
            pushEvent('ERR', `Mic: ${e.message || e}`, 'error');
        } finally {
            els.btnMic.disabled = false;
            syncVoiceButtons();
        }
    });

    els.btnSpeaker.addEventListener('click', async () => {
        els.btnSpeaker.disabled = true;
        try {
            if (voice.speakerEnabled) {
                if (voice.micEnabled) await voice.setMic(false);
                await voice.setSpeaker(false);
            } else {
                await voice.setSpeaker(true);
            }
        } catch (e) {
            pushEvent('ERR', `Speaker: ${e.message || e}`, 'error');
        } finally {
            els.btnSpeaker.disabled = false;
            syncVoiceButtons();
        }
    });

    els.btnTrigger.addEventListener('click', async () => {
        els.btnTrigger.disabled = true;
        try {
            const r = await fetch('/api/voice/trigger', { method: 'POST', headers: authHeaders });
            if (!r.ok) {
                const body = await r.json().catch(() => ({}));
                pushEvent('ERR', `Trigger: ${body.error?.message || r.statusText}`, 'error');
            }
        } finally { els.btnTrigger.disabled = false; }
    });

    els.btnStop.addEventListener('click', async () => {
        els.btnStop.disabled = true;
        try {
            const r = await fetch('/api/voice/stop', { method: 'POST', headers: authHeaders });
            if (!r.ok) {
                const body = await r.json().catch(() => ({}));
                pushEvent('ERR', `Stop: ${body.error?.message || r.statusText}`, 'error');
            }
        } finally { els.btnStop.disabled = false; }
    });

    async function loadEmotions() {
        try {
            const r = await fetch('/api/emotions', { headers: authHeaders });
            const body = await r.json();
            if (body.status !== 'success') return;
            const current = body.data.current_emotion;
            els.valEmotion.textContent = (current || '—').toUpperCase();
            els.emotionsGrid.innerHTML = '';
            body.data.emotions.forEach(em => {
                const btn = document.createElement('button');
                btn.className = 'emotion-btn';
                btn.dataset.id = em.id;
                btn.innerHTML = `<span class="emotion-emoji">${em.emoji || '🙂'}</span><span>${em.name || em.id}</span>`;
                if (em.id === current) btn.classList.add('active');
                btn.addEventListener('click', () => setEmotion(em.id));
                els.emotionsGrid.appendChild(btn);
            });
        } catch (e) {
            pushEvent('ERR', `Emotions: ${e.message || e}`, 'error');
        }
    }

    async function setEmotion(id) {
        try {
            await fetch('/api/emotions/current', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', ...authHeaders },
                body: JSON.stringify({ emotion: id }),
            });
        } catch (e) {
            pushEvent('ERR', `Emotion: ${e.message || e}`, 'error');
        }
    }

    function prependQuestion(item) {
        const empty = els.questionList.querySelector('.empty');
        if (empty) empty.remove();
        const li = document.createElement('li');
        const time = new Date(item.created_at || Date.now()).toLocaleTimeString();
        li.innerHTML = `
            <div class="q"></div>
            ${item.answer ? '<div class="a"></div>' : ''}
            <div class="meta">
                <span>${time}</span>
                <span>${item.source || ''}</span>
                ${item.topic ? `<span>· ${item.topic}</span>` : ''}
            </div>`;
        li.querySelector('.q').textContent = item.question;
        if (item.answer) li.querySelector('.a').textContent = item.answer;
        els.questionList.prepend(li);
    }

    function renderQuestions(items) {
        els.questionList.innerHTML = '';
        if (!items.length) {
            const li = document.createElement('li');
            li.className = 'empty';
            li.textContent = 'Журнал пуст';
            els.questionList.appendChild(li);
            return;
        }
        items.forEach(prependQuestion);
    }

    async function loadQuestions() {
        try {
            const r = await fetch('/api/questions/recent?limit=50', { headers: authHeaders });
            const body = await r.json();
            if (body.status === 'success') renderQuestions(body.data.items.reverse());
        } catch (e) {
            pushEvent('ERR', `Questions: ${e.message || e}`, 'error');
        }
    }

    els.btnReloadQuestions.addEventListener('click', loadQuestions);
    els.btnClearEvents.addEventListener('click', () => { els.eventList.innerHTML = ''; });

    els.manualForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const q = els.manualQuestion.value.trim();
        const a = els.manualAnswer.value.trim();
        if (!q && !a) return;
        try {
            const r = await fetch('/api/questions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...authHeaders },
                body: JSON.stringify({
                    question: q || '(вручную)',
                    answer: a || null,
                    topic: els.manualTopic.value || null,
                    source: 'operator',
                }),
            });
            if (r.ok) {
                els.manualQuestion.value = '';
                els.manualAnswer.value = '';
            }
        } catch (err) {
            pushEvent('ERR', `Save: ${err.message || err}`, 'error');
        }
    });

    ws.connect();
    startVideo();
    loadEmotions();
    loadQuestions();
})();
