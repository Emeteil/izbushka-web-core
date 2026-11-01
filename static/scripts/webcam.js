class WebcamAdaptation {
    constructor() {
        this.level = 0;
        this.goodSince = null;
        this.slowFrames = 0;
    }

    settings(base) {
        const factor = Math.pow(0.72, this.level);
        return {
            quality: base.auto_adjust ? Math.max(Math.min(10, base.quality), Math.round(base.quality * factor)) : base.quality,
            fps: base.network_adaptation ? Math.max(1, base.fps * factor) : base.fps,
        };
    }

    observe(duration, targetFps, now) {
        const interval = 1000 / targetFps;
        if (duration > interval * 1.2) {
            this.goodSince = null;
            if (++this.slowFrames >= 2) this.degrade();
        } else {
            this.slowFrames = 0;
            if (duration < interval * 0.65) {
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
        const generation = this.generation;
        this.running = this.run(generation);
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

    async settings(signal) {
        const response = await fetch('/api/webcam/quality', {
            headers: { Authorization: `Bearer ${this.token}` }, signal, cache: 'no-store',
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return (await response.json()).data.quality;
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
                const base = await this.settings(controller.signal);
                if (base.auto_adjust || base.network_adaptation) {
                    await this.snapshots(base, controller.signal, generation, touch);
                } else {
                    await this.stream(controller.signal, generation, touch);
                }
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

    async snapshots(base, signal, generation, touch) {
        let sequence = null;
        while (!signal.aborted && generation === this.generation) {
            const target = this.adaptation.settings(base);
            const started = performance.now();
            let url = `/api/webcam/snapshot?token=${encodeURIComponent(this.token)}&quality=${target.quality}`;
            if (sequence !== null) url += `&after=${sequence}`;
            const response = await fetch(url, { signal, cache: 'no-store' });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            base = {
                quality: Number(response.headers.get('X-Webcam-Quality')) || base.quality,
                fps: Number(response.headers.get('X-Webcam-Fps')) || base.fps,
                auto_adjust: response.headers.get('X-Webcam-Auto') === '1',
                network_adaptation: response.headers.get('X-Webcam-Network') === '1',
            };
            if (!base.auto_adjust && !base.network_adaptation) {
                if (response.body) await response.body.cancel();
                return;
            }
            if (response.status !== 204) {
                await this.show(await response.blob(), generation, signal);
                sequence = response.headers.get('X-Frame-Sequence');
                const now = performance.now();
                this.adaptation.observe(now - started, target.fps, now);
                touch();
            }
            await this.pause(Math.max(10, 1000 / target.fps - (performance.now() - started)), signal);
        }
    }

    async stream(signal, generation, touch) {
        const response = await fetch(`/api/webcam/stream?token=${encodeURIComponent(this.token)}`, {
            signal, cache: 'no-store',
        });
        if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);
        const reader = response.body.getReader();
        let buffer = new Uint8Array(0);
        let checked = performance.now();
        try {
            while (!signal.aborted && generation === this.generation) {
                const { done, value } = await reader.read();
                if (done) throw new Error('Video stream ended');
                if (buffer.length + value.length > 5_000_000) throw new Error('Video frame too large');
                const next = new Uint8Array(buffer.length + value.length);
                next.set(buffer);
                next.set(value, buffer.length);
                buffer = next;
                let end = -1;
                for (let i = buffer.length - 2; i >= 0; i--) {
                    if (buffer[i] === 255 && buffer[i + 1] === 217) { end = i; break; }
                }
                if (end < 0) continue;
                let start = -1;
                for (let i = end - 2; i >= 0; i--) {
                    if (buffer[i] === 255 && buffer[i + 1] === 216) { start = i; break; }
                }
                if (start < 0) throw new Error('Invalid video frame');
                await this.show(new Blob([buffer.slice(start, end + 2)], { type: 'image/jpeg' }), generation, signal);
                buffer = buffer.slice(end + 2);
                touch();
                if (performance.now() - checked > 5000) {
                    const base = await this.settings(signal);
                    if (base.auto_adjust || base.network_adaptation) return;
                    checked = performance.now();
                }
            }
        } finally {
            await reader.cancel().catch(() => {});
            reader.releaseLock();
        }
    }
}

if (typeof module !== 'undefined') module.exports = { WebcamAdaptation, WebcamPlayer };
