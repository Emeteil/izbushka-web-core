(function (global) {
    'use strict';
    /**
     * Target sample rate for voice transmission (Hz).
     * 8000 Hz is sufficient for speech (telephony quality).
     * Lower = less bandwidth, higher = better quality.
     * Common values: 8000, 11025, 16000.
     */
    const SAMPLE_RATE = 8000;

    /**
     * Duration of a single audio chunk in milliseconds.
     * 20 ms is the industry standard for VoIP (Opus, G.711, etc.).
     * Smaller = lower latency but more overhead.
     * Larger = more efficient but adds latency.
     * Recommended range: 10–60 ms.
     */
    const CHUNK_DURATION_MS = 20;

    /**
     * Number of samples per chunk at the target sample rate.
     * Derived: SAMPLE_RATE * CHUNK_DURATION_MS / 1000
     * At 8000 Hz, 20 ms = 160 samples × 2 bytes = 320 bytes per chunk.
     */
    const CHUNK_SAMPLES = Math.round(SAMPLE_RATE * CHUNK_DURATION_MS / 1000);

    /**
     * Minimum number of chunks to buffer before starting playback.
     * Higher = more resilience to jitter, but adds latency.
     * At 20 ms chunks: 3 chunks = 60 ms initial latency.
     * Recommended: 2–6.
     */
    const MIN_BUFFER_CHUNKS = 60;

    /**
     * Maximum number of chunks to keep in the jitter buffer.
     * If exceeded, oldest chunks are dropped to prevent growing latency.
     * Recommended: 15–30.
     */
    const MAX_BUFFER_CHUNKS = 150;

    /**
     * Ring buffer duration in seconds (playback processor).
     * Should be generous to accommodate burst arrivals.
     * Recommended: 1–3 seconds.
     */
    const RING_BUFFER_SECONDS = 2;

    /**
     * Number of output samples over which gain ramps up/down
     * to eliminate clicks when playback starts/stops or on underrun.
     * At 48000 Hz native: 64 samples ≈ 1.3 ms.
     * Recommended: 32–128.
     */
    const GAIN_RAMP_SAMPLES = 64;

    /**
     * WebSocket reconnect delay (ms) after an unexpected close.
     * Uses exponential backoff: delay * 2^attempt, capped at MAX_RECONNECT_DELAY.
     */
    const RECONNECT_BASE_DELAY_MS = 500;

    /**
     * Maximum reconnect delay (ms).
     */
    const MAX_RECONNECT_DELAY_MS = 10000;

    /**
     * Maximum number of reconnect attempts before giving up.
     * Set to Infinity for unlimited retries.
     */
    const MAX_RECONNECT_ATTEMPTS = 20;

    const WS_ENDPOINT = '/api/broadcast/voice';
    const CAPTURE_WORKLET_URL = '/static/scripts/voice-capture-processor.js';
    const PLAYBACK_WORKLET_URL = '/static/scripts/voice-playback-processor.js';
    const MIC_CONSTRAINTS = {
        audio: {
            channelCount: 1,
            sampleRate: { ideal: SAMPLE_RATE },
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
        },
        video: false,
    };

    const CAPTURE_GAIN = 1.0;

    const PLAYBACK_VOLUME = 1.0;

    function _getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }

    function _getToken() {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('token') || _getCookie('token');
    }

    function _buildWsUrl(token) {
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const base = `${proto}//${location.host}${WS_ENDPOINT}`;
        if (token) return `${base}?token=${encodeURIComponent(token)}`;
        return base;
    }

    function _log(...args) {
        console.log('[VoiceChannel]', ...args);
    }

    function _warn(...args) {
        console.warn('[VoiceChannel]', ...args);
    }

    function _error(...args) {
        console.error('[VoiceChannel]', ...args);
    }

    class VoiceChannel {
        constructor(opts) {
            opts = opts || {};
            this._token = opts.token || _getToken();

            this.micEnabled = false;
            this.speakerEnabled = false;

            this.onStatusChange = null;

            this._ws = null;
            this._reconnectAttempts = 0;
            this._reconnectTimer = null;
            this._destroyed = false;

            this._audioCtx = null;
            this._micStream = null;
            this._micSource = null;
            this._captureGain = null;
            this._captureNode = null;
            this._playbackNode = null;
            this._playbackGain = null;

            this._captureWorkletReady = false;
            this._playbackWorkletReady = false;
        }

        async setMic(enabled) {
            if (this._destroyed) return;
            if (enabled === this.micEnabled) return;

            if (enabled) {
                await this._ensureAudioContext();
                await this._ensureWebSocket();
                await this._startCapture();
                this.micEnabled = true;
            } else {
                this._stopCapture();
                this.micEnabled = false;
            }

            this._notifyStatus();
        }

        async setSpeaker(enabled) {
            if (this._destroyed) return;
            if (enabled === this.speakerEnabled) return;

            if (enabled) {
                await this._ensureAudioContext();
                await this._ensureWebSocket();
                await this._startPlayback();
                this.speakerEnabled = true;
            } else {
                this._stopPlayback();
                this.speakerEnabled = false;
            }

            this._notifyStatus();
        }

        destroy() {
            this._destroyed = true;
            this._stopCapture();
            this._stopPlayback();
            this._closeWebSocket();
            if (this._audioCtx) {
                this._audioCtx.close().catch(() => { });
                this._audioCtx = null;
            }
            this.micEnabled = false;
            this.speakerEnabled = false;
            this._notifyStatus();
        }

        async _ensureAudioContext() {
            if (this._audioCtx && this._audioCtx.state !== 'closed') {
                if (this._audioCtx.state === 'suspended') {
                    await this._audioCtx.resume();
                }
                return;
            }

            this._audioCtx = new (window.AudioContext || window.webkitAudioContext)();

            await Promise.all([
                this._audioCtx.audioWorklet.addModule(CAPTURE_WORKLET_URL),
                this._audioCtx.audioWorklet.addModule(PLAYBACK_WORKLET_URL),
            ]);

            this._captureWorkletReady = true;
            this._playbackWorkletReady = true;

            _log('AudioContext created, worklets loaded. Native SR:', this._audioCtx.sampleRate);
        }

        async _ensureWebSocket() {
            if (this._ws && this._ws.readyState === WebSocket.OPEN) return;
            if (this._ws && this._ws.readyState === WebSocket.CONNECTING) {
                await new Promise((resolve, reject) => {
                    const onOpen = () => { cleanup(); resolve(); };
                    const onErr = (e) => { cleanup(); reject(e); };
                    const cleanup = () => {
                        this._ws.removeEventListener('open', onOpen);
                        this._ws.removeEventListener('error', onErr);
                    };
                    this._ws.addEventListener('open', onOpen);
                    this._ws.addEventListener('error', onErr);
                });
                return;
            }

            return new Promise((resolve, reject) => {
                const url = _buildWsUrl(this._token);
                _log('Connecting WS:', url.replace(/token=.*/, 'token=***'));

                const ws = new WebSocket(url);
                ws.binaryType = 'arraybuffer';

                ws.onopen = () => {
                    _log('WS connected');
                    this._reconnectAttempts = 0;
                    resolve();
                };

                ws.onmessage = (e) => {
                    if (e.data instanceof ArrayBuffer && this._playbackNode) {
                        this._playbackNode.port.postMessage(e.data, []);
                    }
                };

                ws.onclose = (e) => {
                    _log('WS closed, code:', e.code, 'reason:', e.reason);
                    this._ws = null;
                    if (!this._destroyed && (this.micEnabled || this.speakerEnabled)) {
                        this._scheduleReconnect();
                    }
                };

                ws.onerror = (e) => {
                    _error('WS error:', e);
                    if (this._ws === null) reject(e);
                };

                this._ws = ws;
            });
        }

        _closeWebSocket() {
            if (this._reconnectTimer) {
                clearTimeout(this._reconnectTimer);
                this._reconnectTimer = null;
            }
            if (this._ws) {
                this._ws.onclose = null;
                this._ws.onerror = null;
                this._ws.onmessage = null;
                try { this._ws.close(); } catch (_) { }
                this._ws = null;
            }
        }

        _scheduleReconnect() {
            if (this._destroyed) return;
            if (this._reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
                _error('Max reconnect attempts reached, giving up');
                return;
            }

            const delay = Math.min(
                RECONNECT_BASE_DELAY_MS * Math.pow(2, this._reconnectAttempts),
                MAX_RECONNECT_DELAY_MS
            );
            this._reconnectAttempts++;

            _log(`Reconnecting in ${delay}ms (attempt ${this._reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);

            this._reconnectTimer = setTimeout(async () => {
                this._reconnectTimer = null;
                try {
                    await this._ensureWebSocket();
                    _log('Reconnected successfully');
                } catch (e) {
                    _warn('Reconnect failed:', e);
                    this._scheduleReconnect();
                }
            }, delay);
        }

        async _startCapture() {
            if (this._captureNode) return;

            this._micStream = await navigator.mediaDevices.getUserMedia(MIC_CONSTRAINTS);

            const ctx = this._audioCtx;

            this._micSource = ctx.createMediaStreamSource(this._micStream);

            this._captureGain = ctx.createGain();
            this._captureGain.gain.value = CAPTURE_GAIN;

            this._captureNode = new AudioWorkletNode(ctx, 'voice-capture-processor', {
                processorOptions: {
                    targetSampleRate: SAMPLE_RATE,
                    chunkSamples: CHUNK_SAMPLES,
                },
                numberOfInputs: 1,
                numberOfOutputs: 0,
                channelCount: 1,
            });

            this._captureNode.port.onmessage = (e) => {
                if (this._ws && this._ws.readyState === WebSocket.OPEN) {
                    this._ws.send(e.data);
                }
            };

            this._micSource.connect(this._captureGain);
            this._captureGain.connect(this._captureNode);

            _log('Mic capture started');
        }

        _stopCapture() {
            if (this._captureNode) {
                this._captureNode.port.postMessage('stop');
                try { this._captureNode.disconnect(); } catch (_) { }
                this._captureNode = null;
            }
            if (this._captureGain) {
                try { this._captureGain.disconnect(); } catch (_) { }
                this._captureGain = null;
            }
            if (this._micSource) {
                try { this._micSource.disconnect(); } catch (_) { }
                this._micSource = null;
            }
            if (this._micStream) {
                this._micStream.getTracks().forEach(t => t.stop());
                this._micStream = null;
            }
            _log('Mic capture stopped');
        }

        async _startPlayback() {
            if (this._playbackNode) return;

            const ctx = this._audioCtx;

            this._playbackNode = new AudioWorkletNode(ctx, 'voice-playback-processor', {
                processorOptions: {
                    targetSampleRate: SAMPLE_RATE,
                    chunkSamples: CHUNK_SAMPLES,
                    ringBufferSeconds: RING_BUFFER_SECONDS,
                    minBufferChunks: MIN_BUFFER_CHUNKS,
                    maxBufferChunks: MAX_BUFFER_CHUNKS,
                    gainRampSamples: GAIN_RAMP_SAMPLES,
                },
                numberOfInputs: 0,
                numberOfOutputs: 1,
                outputChannelCount: [1],
            });

            this._playbackGain = ctx.createGain();
            this._playbackGain.gain.value = PLAYBACK_VOLUME;

            this._playbackNode.connect(this._playbackGain);
            this._playbackGain.connect(ctx.destination);

            _log('Speaker playback started');
        }

        _stopPlayback() {
            if (this._playbackNode) {
                this._playbackNode.port.postMessage('stop');
                try { this._playbackNode.disconnect(); } catch (_) { }
                this._playbackNode = null;
            }
            if (this._playbackGain) {
                try { this._playbackGain.disconnect(); } catch (_) { }
                this._playbackGain = null;
            }

            if (!this.micEnabled) {
                this._closeWebSocket();
            }

            _log('Speaker playback stopped');
        }

        _notifyStatus() {
            if (typeof this.onStatusChange === 'function') {
                try { this.onStatusChange(); } catch (_) { }
            }
        }
    }

    global.VoiceChannel = VoiceChannel;

})(window);
