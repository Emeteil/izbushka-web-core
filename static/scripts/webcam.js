class WebcamAdaptation {
    constructor() {
        this.level = 0;
        this.goodSince = null;
        this.slowFrames = 0;
        this.lastLag = 0;
    }

    settings(base) {
        const factor = Math.pow(0.72, this.level);
        const fpsLevel = base.auto_adjust ? Math.max(0, this.level - 2) : this.level;
        return {
            quality: base.auto_adjust ? Math.max(Math.min(10, base.quality), Math.round(base.quality * factor)) : base.quality,
            fps: base.network_adaptation ? Math.max(Math.min(5, base.fps), base.fps * Math.pow(0.75, fpsLevel)) : base.fps,
        };
    }

    observe({ fps, lagMs, decodeMs }, targetFps, now) {
        const growingQueue = lagMs > 150 && (lagMs > this.lastLag + 20 || fps < targetFps * 0.8);
        const slowDecoder = decodeMs > 850 / targetFps;
        this.lastLag = lagMs;
        if (growingQueue || slowDecoder) {
            this.goodSince = null;
            if (++this.slowFrames >= 2 || lagMs > 500) this.degrade();
        } else {
            this.slowFrames = 0;
            if (lagMs < 100 && decodeMs < 600 / targetFps && fps >= targetFps * 0.7) {
                if (this.goodSince === null) this.goodSince = now;
                if (now - this.goodSince >= 5000) {
                    this.level = Math.max(0, this.level - 1);
                    this.goodSince = now;
                }
            } else {
                this.goodSince = null;
            }
        }
    }

    degrade() {
        this.level = Math.min(10, this.level + 1);
        this.goodSince = null;
        this.slowFrames = 0;
    }
}

class WebcamMultipartParser {
    constructor() {
        this.buffer = new Uint8Array(0);
        this.decoder = new TextDecoder();
    }

    push(value) {
        if (this.buffer.length + value.length > 5_000_000) throw new Error('Video buffer too large');
        const next = new Uint8Array(this.buffer.length + value.length);
        next.set(this.buffer);
        next.set(value, this.buffer.length);
        this.buffer = next;
        let latest = null;
        let count = 0;
        while (this.buffer.length) {
            if (this.buffer[0] === 13 && this.buffer[1] === 10) this.buffer = this.buffer.slice(2);
            let headerEnd = -1;
            for (let i = 0; i + 3 < this.buffer.length; i++) {
                if (this.buffer[i] === 13 && this.buffer[i + 1] === 10 &&
                    this.buffer[i + 2] === 13 && this.buffer[i + 3] === 10) { headerEnd = i; break; }
            }
            if (headerEnd < 0) {
                if (this.buffer.length > 8192) throw new Error('Invalid video headers');
                break;
            }
            const lines = this.decoder.decode(this.buffer.subarray(0, headerEnd)).split('\r\n');
            if (lines.shift() !== '--frame') throw new Error('Invalid video boundary');
            const headers = {};
            for (const line of lines) {
                const colon = line.indexOf(':');
                if (colon > 0) headers[line.slice(0, colon).toLowerCase()] = line.slice(colon + 1).trim();
            }
            const size = Number(headers['content-length']);
            if (!Number.isInteger(size) || size < 1 || size > 4_000_000) throw new Error('Invalid frame size');
            const end = headerEnd + 4 + size;
            if (this.buffer.length < end) break;
            latest = { data: this.buffer.slice(headerEnd + 4, end), headers };
            this.buffer = this.buffer.slice(end);
            count++;
        }
        return { latest, count };
    }
}

class WebcamPlayer {
    constructor({ image, token, onState = () => {} }) {
        this.image = image;
        this.token = token;
        this.onState = onState;
        this.adaptation = new WebcamAdaptation();
        this.controller = null;
        this.blobUrl = null;
        this.generation = 0;
    }

    start() {
        this.stop();
        this.running = this.run(this.generation);
        return this.running;
    }

    stop() {
        this.generation++;
        if (this.controller) this.controller.abort();
        this.controller = null;
        this.image.removeAttribute('src');
        if (this.blobUrl) URL.revokeObjectURL(this.blobUrl);
        this.blobUrl = null;
    }

    async pause(ms, signal) {
        if (signal.aborted) return;
        await new Promise(resolve => {
            const finish = () => {
                clearTimeout(timer);
                signal.removeEventListener('abort', finish);
                resolve();
            };
            const timer = setTimeout(finish, ms);
            signal.addEventListener('abort', finish, { once: true });
        });
    }

    async run(generation) {
        while (generation === this.generation) {
            const controller = new AbortController();
            this.controller = controller;
            let watchdog = setTimeout(() => controller.abort(), 5000);
            const touch = () => {
                clearTimeout(watchdog);
                watchdog = setTimeout(() => controller.abort(), 5000);
            };
            try {
                this.onState('connecting');
                await this.stream(controller.signal, generation, touch);
            } catch (error) {
                if (generation === this.generation) {
                    this.adaptation.degrade();
                    this.onState('retrying');
                }
            } finally {
                clearTimeout(watchdog);
                controller.abort();
            }
            if (generation !== this.generation) break;
            this.controller = new AbortController();
            await this.pause(1000, this.controller.signal);
        }
    }

    async show(blob, generation, signal) {
        if (generation !== this.generation || signal.aborted) return;
        const url = URL.createObjectURL(blob);
        const previous = this.blobUrl;
        this.blobUrl = url;
        this.image.src = url;
        try {
            await new Promise((resolve, reject) => {
                const abort = () => reject(new DOMException('Aborted', 'AbortError'));
                signal.addEventListener('abort', abort, { once: true });
                this.image.decode().then(resolve, reject).finally(() => signal.removeEventListener('abort', abort));
            });
            if (generation === this.generation && !signal.aborted) this.onState('playing');
        } finally {
            if (previous) URL.revokeObjectURL(previous);
        }
    }

    async feedback(streamId, settings, signal) {
        const controller = new AbortController();
        const abort = () => controller.abort();
        const timer = setTimeout(abort, 1500);
        signal.addEventListener('abort', abort, { once: true });
        try {
            if (signal.aborted) return;
            const response = await fetch(`/api/webcam/stream/${encodeURIComponent(streamId)}/feedback`, {
                method: 'POST', signal: controller.signal, cache: 'no-store',
                headers: { Authorization: `Bearer ${this.token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify(settings),
            });
            if (response.body) await response.body.cancel();
        } finally {
            clearTimeout(timer);
            signal.removeEventListener('abort', abort);
        }
    }

    async stream(signal, generation, touch) {
        const response = await fetch(`/api/webcam/stream?token=${encodeURIComponent(this.token)}`, {
            signal, cache: 'no-store',
        });
        if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);
        const streamId = response.headers.get('X-Stream-Id');
        const reader = response.body.getReader();
        const parser = new WebcamMultipartParser();
        let pending = null;
        let rendering = null;
        let feedbackTask = null;
        let decodeMs = 0;
        let sampleStart = performance.now();
        let frames = 0;
        let minOffset = Infinity;
        const render = () => {
            if (rendering) return;
            rendering = (async () => {
                while (pending && !signal.aborted && generation === this.generation) {
                    const frame = pending;
                    pending = null;
                    const started = performance.now();
                    await this.show(new Blob([frame.data], { type: 'image/jpeg' }), generation, signal);
                    decodeMs = performance.now() - started;
                }
            })().catch(() => {
                if (generation === this.generation && this.controller) this.controller.abort();
            }).finally(() => {
                rendering = null;
                if (pending && !signal.aborted && generation === this.generation) render();
            });
        };
        try {
            while (!signal.aborted && generation === this.generation) {
                const { done, value } = await reader.read();
                if (done) throw new Error('Video stream ended');
                const result = parser.push(value);
                if (!result.latest) continue;
                touch();
                pending = result.latest;
                render();
                frames += result.count;
                const now = performance.now();
                const headers = result.latest.headers;
                const sent = Number(headers['x-frame-time']) * 1000;
                if (!Number.isFinite(sent)) throw new Error('Invalid frame timestamp');
                const offset = now - sent;
                minOffset = Math.min(minOffset, offset);
                const lagMs = Math.max(0, offset - minOffset);
                if (streamId && now - sampleStart >= 500 && !feedbackTask) {
                    const base = {
                        quality: Number(headers['x-webcam-quality']), fps: Number(headers['x-webcam-fps']),
                        auto_adjust: headers['x-webcam-auto'] === '1',
                        network_adaptation: headers['x-webcam-network'] === '1',
                    };
                    const targetFps = Math.min(Number(headers['x-stream-fps']), Number(headers['x-capture-fps']));
                    this.adaptation.observe({ fps: frames * 1000 / (now - sampleStart), lagMs, decodeMs }, targetFps, now);
                    feedbackTask = this.feedback(streamId, this.adaptation.settings(base), signal)
                        .catch(() => {}).finally(() => { feedbackTask = null; });
                    frames = 0;
                    sampleStart = now;
                }
            }
        } finally {
            pending = null;
            if (generation === this.generation && this.controller) this.controller.abort();
            await reader.cancel().catch(() => {});
            reader.releaseLock();
            if (rendering) await rendering;
            if (feedbackTask) await feedbackTask;
        }
    }
}

if (typeof module !== 'undefined') module.exports = { WebcamAdaptation, WebcamMultipartParser, WebcamPlayer };
