const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { WebcamAdaptation, WebcamMultipartParser, WebcamPlayer } = require('../static/scripts/webcam.js');

const base = { quality: 30, fps: 23, auto_adjust: true, network_adaptation: true };

function part(sequence = 1, data = new Uint8Array([255, 216, sequence, 255, 217])) {
    const headers = new TextEncoder().encode(
        `--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ${data.length}\r\n` +
        `X-Frame-Sequence: ${sequence}\r\nX-Frame-Time: ${performance.now() / 1000}\r\n` +
        'X-Webcam-Quality: 30\r\nX-Webcam-Fps: 23\r\nX-Stream-Fps: 23\r\n' +
        'X-Capture-Fps: 23\r\nX-Webcam-Auto: 1\r\nX-Webcam-Network: 1\r\n\r\n');
    return Buffer.concat([headers, data, Buffer.from('\r\n')]);
}

function setup(t, options = {}, fastTimers = true) {
    const liveUrls = new Set();
    let urlId = 0;
    const image = { src: '', removeAttribute() { this.src = ''; }, async decode() {} };
    t.mock.method(URL, 'createObjectURL', () => {
        const url = `blob:test-${++urlId}`;
        liveUrls.add(url);
        return url;
    });
    t.mock.method(URL, 'revokeObjectURL', url => liveUrls.delete(url));
    const realTimeout = setTimeout;
    const timers = new Set();
    const realClear = clearTimeout;
    t.mock.method(global, 'setTimeout', (callback, delay) => {
        if (!fastTimers && ![5000, 1500, 1000].includes(delay)) return realTimeout(callback, delay);
        const timer = realTimeout(() => { timers.delete(timer); callback(); },
            fastTimers ? (delay === 5000 ? 50 : 1) : delay);
        timers.add(timer);
        return timer;
    });
    t.mock.method(global, 'clearTimeout', timer => { timers.delete(timer); realClear(timer); });
    const player = new WebcamPlayer({ image, token: 'test token', ...options });
    t.after(() => { player.stop(); for (const timer of timers) realClear(timer); });
    return { player, image, liveUrls, timers };
}

function videoResponse(signal, chunks = []) {
    return new Response(new ReadableStream({
        start(controller) {
            chunks.forEach(chunk => controller.enqueue(chunk));
            signal.addEventListener('abort', () => controller.error(new DOMException('Aborted', 'AbortError')),
                { once: true });
        },
    }), { headers: { 'X-Stream-Id': 'session-id' } });
}

test('multipart parser handles every chunk boundary and binary JPEG marker sequences', () => {
    const jpeg = new Uint8Array([255, 216, 1, 255, 217, 2, 255, 216, 3, 255, 217]);
    const bytes = Buffer.concat([part(1, jpeg), part(2, jpeg)]);
    const parser = new WebcamMultipartParser();
    const frames = [];
    for (const byte of bytes) {
        const result = parser.push(new Uint8Array([byte]));
        if (result.latest) frames.push(result.latest);
    }
    assert.equal(frames.length, 2);
    assert.deepEqual(frames[0].data, jpeg);
    assert.equal(frames[1].headers['x-frame-sequence'], '2');
    const grouped = new WebcamMultipartParser().push(bytes);
    assert.equal(grouped.count, 2);
    assert.equal(grouped.latest.headers['x-frame-sequence'], '2');
});

test('parser rejects invalid lengths and bounds its buffer', () => {
    const parser = new WebcamMultipartParser();
    assert.throws(() => parser.push(new TextEncoder().encode('--frame\r\nContent-Length: 5000000\r\n\r\n')));
    assert.throws(() => new WebcamMultipartParser().push(new Uint8Array(5_000_001)));
});

test('constant network latency does not reduce FPS; each viewer adapts independently', () => {
    const fast = new WebcamAdaptation();
    const slow = new WebcamAdaptation();
    for (let now = 500; now < 10000; now += 500) {
        fast.observe({ fps: 23, lagMs: 0, decodeMs: 2 }, 23, now);
    }
    assert.deepEqual(fast.settings(base), { quality: 30, fps: 23 });
    slow.observe({ fps: 8, lagMs: 250, decodeMs: 2 }, 23, 500);
    slow.observe({ fps: 8, lagMs: 400, decodeMs: 2 }, 23, 1000);
    assert.equal(slow.level, 1);
    assert.equal(slow.settings(base).fps, 23);
    assert.ok(slow.settings(base).quality < 30);
    assert.equal(fast.level, 0);
    assert.deepEqual(slow.settings({ ...base, auto_adjust: false, network_adaptation: false }), { quality: 30, fps: 23 });
});

test('continuous bandwidth model adapts to 500 kbit/s and recovers with delayed feedback', () => {
    const adaptation = new WebcamAdaptation();
    let applied = adaptation.settings(base);
    let queue = [];
    let feedback = [];
    let nextSend = 0;
    let networkFree = 0;
    let minOffset = Infinity;
    let sampleStart = 0;
    let received = 0;
    let lag = 0;
    let atSlow;
    for (let now = 0; now < 100000; now++) {
        const bandwidth = now >= 5000 && now < 25000 ? 500 : 100000;
        while (feedback.length && feedback[0].at <= now) applied = feedback.shift().settings;
        if (now >= nextSend && queue.reduce((sum, frame) => sum + frame.size, 0) < 65536) {
            const size = 1000 + applied.quality * 400;
            networkFree = Math.max(now, networkFree) + size * 8 / bandwidth;
            queue.push({ sent: now, arrival: networkFree + 80, size });
            nextSend = now + 1000 / applied.fps;
        }
        while (queue.length && queue[0].arrival <= now) {
            const frame = queue.shift();
            const offset = now - frame.sent;
            minOffset = Math.min(minOffset, offset);
            lag = offset - minOffset;
            received++;
        }
        if (now - sampleStart >= 500) {
            adaptation.observe({ fps: received * 1000 / (now - sampleStart), lagMs: lag, decodeMs: 2 }, applied.fps, now);
            feedback.push({ at: now + 200, settings: adaptation.settings(base) });
            sampleStart = now;
            received = 0;
        }
        if (now === 24000) atSlow = { ...applied };
    }
    assert.ok(atSlow.quality < base.quality);
    assert.ok(atSlow.fps >= 5);
    assert.ok((1000 + atSlow.quality * 400) * atSlow.fps * 8 < 600000);
    assert.deepEqual(applied, { quality: 30, fps: 23 });
});

test('watchdog reconnects a stalled MJPEG stream and releases resources on stop', async t => {
    const states = [];
    const { player, liveUrls, timers } = setup(t, {
        onState(state) { states.push(state); if (state === 'playing') player.stop(); },
    });
    let requests = 0;
    t.mock.method(global, 'fetch', async (url, options) => {
        assert.ok(url.startsWith('/api/webcam/stream?'));
        return videoResponse(options.signal, ++requests === 1 ? [] : [part()]);
    });
    await player.start();
    assert.equal(requests, 2);
    assert.ok(states.includes('retrying'));
    assert.equal(liveUrls.size, 0);
    assert.equal(timers.size, 0);
});

test('EOF reconnects in automatic mode without requesting snapshots', async t => {
    const { player } = setup(t, { onState(state) { if (state === 'playing') player.stop(); } });
    let requests = 0;
    t.mock.method(global, 'fetch', async (url, options) => {
        assert.ok(url.startsWith('/api/webcam/stream?'));
        if (++requests === 1) return new Response(new ReadableStream({ start(controller) { controller.close(); } }));
        return videoResponse(options.signal, [part()]);
    });
    await player.start();
    assert.equal(requests, 2);
});

test('slow image decoding does not block network reads and retains only the latest frame', async t => {
    const { player, image, liveUrls, timers } = setup(t);
    let finishDecode;
    let decodes = 0;
    let source;
    const displayed = [];
    image.decode = () => ++decodes === 1 ? new Promise(resolve => { finishDecode = resolve; }) : Promise.resolve();
    const show = player.show.bind(player);
    player.show = async (blob, ...args) => {
        displayed.push(new Uint8Array(await blob.arrayBuffer())[2]);
        await show(blob, ...args);
        if (displayed.length === 2) player.stop();
    };
    t.mock.method(global, 'fetch', async (url, options) => new Response(new ReadableStream({
        start(controller) {
            source = controller;
            controller.enqueue(part(1));
            options.signal.addEventListener('abort', () => controller.error(new DOMException('Aborted', 'AbortError')));
        },
    })));
    const running = player.start();
    while (!finishDecode) await new Promise(setImmediate);
    source.enqueue(Buffer.concat(Array.from({ length: 19 }, (_, i) => part(i + 2))));
    await new Promise(setImmediate);
    finishDecode();
    await running;
    assert.deepEqual(displayed, [1, 20]);
    assert.equal(liveUrls.size, 0);
    assert.equal(timers.size, 0);
});

test('23 FPS continuous HTTP stream survives 200 ms startup latency and 600 ms feedback delay', { timeout: 10000 }, async t => {
    const originalFetch = fetch;
    let streamRequests = 0;
    let feedbackRequests = 0;
    let framesDuringFeedback = 0;
    let feedbackPending = false;
    const server = http.createServer((req, res) => {
        if (req.method === 'POST') {
            feedbackRequests++;
            feedbackPending = true;
            req.resume();
            const timer = setTimeout(() => { feedbackPending = false; res.writeHead(204).end(); }, 600);
            res.on('close', () => clearTimeout(timer));
            return;
        }
        assert.ok(req.url.startsWith('/api/webcam/stream?'));
        streamRequests++;
        let sequence = 0;
        let interval;
        const timer = setTimeout(() => {
            res.writeHead(200, { 'Content-Type': 'multipart/x-mixed-replace; boundary=frame', 'X-Stream-Id': 'live' });
            res.flushHeaders();
            interval = setInterval(() => res.write(part(++sequence)), 1000 / 23);
        }, 200);
        res.on('close', () => { clearTimeout(timer); clearInterval(interval); });
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    t.after(() => { server.closeAllConnections(); server.close(); });
    let first;
    let last;
    let displayed = 0;
    const { player, liveUrls, timers } = setup(t, {
        onState(state) {
            if (state !== 'playing') return;
            first ??= performance.now();
            last = performance.now();
            if (feedbackPending) framesDuringFeedback++;
            if (++displayed === 30) player.stop();
        },
    }, false);
    t.mock.method(global, 'fetch', (url, options) => originalFetch(`http://127.0.0.1:${server.address().port}${url}`, options));
    await player.start();
    const fps = (displayed - 1) * 1000 / (last - first);
    assert.ok(fps > 18, `measured FPS: ${fps}`);
    assert.equal(streamRequests, 1);
    assert.ok(feedbackRequests >= 1);
    assert.ok(framesDuringFeedback >= 8);
    assert.equal(player.adaptation.level, 0);
    assert.equal(liveUrls.size, 0);
    assert.equal(timers.size, 0);
    t.diagnostic(`measured ${fps.toFixed(1)} FPS; ${framesDuringFeedback} frames while feedback was delayed`);
});

test('stop during image decode cancels the stream without reconnecting', async t => {
    const { player, image, liveUrls, timers } = setup(t);
    image.decode = () => { player.stop(); return new Promise(() => {}); };
    let requests = 0;
    t.mock.method(global, 'fetch', async (url, options) => {
        requests++;
        return videoResponse(options.signal, [part()]);
    });
    await player.start();
    assert.equal(requests, 1);
    assert.equal(liveUrls.size, 0);
    assert.equal(timers.size, 0);
});

test('every camera page uses the common continuous player', () => {
    const fs = require('node:fs');
    const path = require('node:path');
    for (const [template, script] of [['control', 'control'], ['operator', 'operator'], ['admin_panel', 'admin']]) {
        const html = fs.readFileSync(path.join(__dirname, '../templates', `${template}.html`), 'utf8');
        assert.ok(html.indexOf('/static/scripts/webcam.js') < html.indexOf(`/static/scripts/${script}.js`));
        const js = fs.readFileSync(path.join(__dirname, '../static/scripts', `${script}.js`), 'utf8');
        assert.ok(js.includes('new WebcamPlayer('));
        assert.ok(js.includes("'pagehide'"));
    }
});
