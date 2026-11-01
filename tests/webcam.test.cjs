const test = require('node:test');
const assert = require('node:assert/strict');
const { WebcamAdaptation, WebcamPlayer } = require('../static/scripts/webcam.js');

const base = { quality: 60, fps: 23, auto_adjust: true, network_adaptation: true };

test('bandwidth drop reduces load and a stable recovery restores quality gradually', () => {
    const adaptation = new WebcamAdaptation();
    let now = 0;
    const simulate = (seconds, bandwidth, latency) => {
        const end = now + seconds * 1000;
        let samples = 0;
        let bytes = 0;
        while (now < end) {
            const target = adaptation.settings(base);
            const size = 5000 + target.quality * 600;
            const duration = latency + size * 8 / bandwidth;
            now += Math.max(1000 / target.fps, duration);
            adaptation.observe(duration, target.fps, now);
            samples++;
            bytes += size;
        }
        return { samples, bytes, target: adaptation.settings(base) };
    };
    const fast = simulate(10, 100000, 5);
    assert.equal(fast.target.quality, 60);
    const slow = simulate(20, 500, 80);
    assert.ok(slow.target.fps < 8);
    assert.ok(slow.target.quality < 30);
    assert.ok(slow.bytes / 20 < fast.bytes / 10 / 3);
    const level = adaptation.level;
    simulate(1, 100000, 5);
    assert.equal(adaptation.level, level);
    const recovered = simulate(70, 100000, 5);
    assert.equal(recovered.target.quality, 60);
    assert.equal(recovered.target.fps, 23);
});

test('one slow frame does not oscillate quality; viewers and manual settings are independent', () => {
    const slow = new WebcamAdaptation();
    const fast = new WebcamAdaptation();
    slow.observe(500, 23, 500);
    assert.equal(slow.level, 0);
    slow.observe(500, 23, 1000);
    assert.equal(slow.level, 1);
    assert.equal(fast.level, 0);
    for (let i = 0; i < 100; i++) slow.degrade();
    assert.equal(slow.level, 10);
    assert.equal(slow.settings(base).fps, 1);
    assert.equal(slow.settings(base).quality, 10);
    assert.equal(slow.settings({ ...base, quality: 5 }).quality, 5);
    assert.deepEqual(slow.settings({ ...base, auto_adjust: false, network_adaptation: false }), { quality: 60, fps: 23 });
});

function setup(t, options = {}) {
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
        const timer = realTimeout(() => { timers.delete(timer); callback(); }, delay === 5000 ? 30 : 1);
        timers.add(timer);
        return timer;
    });
    t.mock.method(global, 'clearTimeout', timer => { timers.delete(timer); realClear(timer); });
    const player = new WebcamPlayer({ image, token: 'test token', ...options });
    t.after(() => { player.stop(); for (const timer of timers) realClear(timer); });
    return { player, image, liveUrls, timers };
}

function settingsResponse(settings = base) {
    return Response.json({ status: 'success', data: { quality: settings } });
}

function snapshotResponse(sequence = 1, status = 200) {
    return new Response(status === 204 ? null : new Uint8Array([255, 216, 255, 217]), {
        status,
        headers: {
            'Content-Type': 'image/jpeg', 'X-Frame-Sequence': String(sequence),
            'X-Webcam-Quality': '60', 'X-Webcam-Fps': '23', 'X-Webcam-Auto': '1', 'X-Webcam-Network': '1',
        },
    });
}

test('watchdog AbortError reconnects, and stop releases URLs and timers', async t => {
    const states = [];
    const { player, image, liveUrls, timers } = setup(t, {
        onState(state) { states.push(state); if (state === 'playing') player.stop(); },
    });
    let requests = 0;
    t.mock.method(global, 'fetch', async (url, options) => {
        assert.equal(options.cache, 'no-store');
        if (url === '/api/webcam/quality') return settingsResponse();
        requests++;
        if (requests === 1) {
            return new Promise((resolve, reject) => {
                options.signal.addEventListener('abort', () => reject(new DOMException('Timeout', 'AbortError')));
            });
        }
        return snapshotResponse();
    });
    await player.start();
    assert.equal(requests, 2);
    assert.ok(states.includes('retrying'));
    assert.ok(states.includes('playing'));
    assert.equal(image.src, '');
    assert.equal(liveUrls.size, 0);
    assert.equal(timers.size, 0);
});

test('snapshots use sequence IDs, do not overlap, and keep the configured quality ceiling', async t => {
    let displayed = 0;
    const { player, liveUrls, timers } = setup(t, {
        onState(state) { if (state === 'playing' && ++displayed === 3) player.stop(); },
    });
    player.adaptation.level = 2;
    const qualities = [];
    let inFlight = 0;
    let requests = 0;
    t.mock.method(global, 'fetch', async (url, options) => {
        if (url === '/api/webcam/quality') return settingsResponse();
        assert.equal(++inFlight, 1);
        const params = new URL(url, 'http://local').searchParams;
        qualities.push(Number(params.get('quality')));
        if (requests > 0) assert.equal(params.get('after'), String(requests));
        await Promise.resolve();
        inFlight--;
        return snapshotResponse(++requests);
    });
    await player.start();
    assert.deepEqual(qualities, [31, 31, 31]);
    assert.equal(liveUrls.size, 0);
    assert.equal(timers.size, 0);
});

test('unchanged frames neither improve adaptation nor reset the freshness watchdog', async t => {
    const { player } = setup(t);
    const controller = new AbortController();
    let requests = 0;
    let observations = 0;
    let touches = 0;
    player.adaptation.observe = () => observations++;
    t.mock.method(global, 'fetch', async () => {
        if (++requests === 2) controller.abort();
        return snapshotResponse(1, 204);
    });
    await player.snapshots(base, controller.signal, player.generation, () => touches++);
    assert.equal(requests, 2);
    assert.equal(observations, 0);
    assert.equal(touches, 0);
});

test('manual mode uses MJPEG, retries EOF, and displays the latest complete JPEG', async t => {
    const { player, liveUrls, timers } = setup(t, {
        onState(state) { if (state === 'playing') player.stop(); },
    });
    let requests = 0;
    t.mock.method(global, 'fetch', async url => {
        if (url === '/api/webcam/quality') {
            return settingsResponse({ ...base, auto_adjust: false, network_adaptation: false });
        }
        assert.ok(url.startsWith('/api/webcam/stream?'));
        requests++;
        return new Response(new ReadableStream({
            start(controller) {
                if (requests > 1) controller.enqueue(new Uint8Array([255, 216, 1, 255, 217, 255, 216, 2, 255, 217]));
                controller.close();
            },
        }));
    });
    const show = player.show.bind(player);
    player.show = async (blob, ...args) => {
        assert.deepEqual([...new Uint8Array(await blob.arrayBuffer())], [255, 216, 2, 255, 217]);
        await show(blob, ...args);
    };
    await player.start();
    assert.equal(requests, 2);
    assert.equal(liveUrls.size, 0);
    assert.equal(timers.size, 0);
});

test('stop while an image decode is pending cancels the player without reconnecting', async t => {
    const { player, image, liveUrls, timers } = setup(t);
    image.decode = () => { player.stop(); return new Promise(() => {}); };
    let requests = 0;
    t.mock.method(global, 'fetch', async url => {
        if (url === '/api/webcam/quality') return settingsResponse();
        requests++;
        return snapshotResponse();
    });
    await player.start();
    assert.equal(requests, 1);
    assert.equal(liveUrls.size, 0);
    assert.equal(timers.size, 0);
});

test('every camera page loads the common player before its own script', () => {
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
