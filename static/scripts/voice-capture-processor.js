class VoiceCaptureProcessor extends AudioWorkletProcessor {
    constructor(options) {
        super();

        const opts = options.processorOptions || {};
        this._targetRate = opts.targetSampleRate || 8000;
        this._chunkSamples = opts.chunkSamples || 160;

        this._ratio = sampleRate / this._targetRate;

        this._accum = new Float32Array(this._chunkSamples * 2);
        this._accumLen = 0;

        this._srcPos = 0;

        this._prevSample = 0;

        this._alive = true;
        this.port.onmessage = (e) => {
            if (e.data === 'stop') this._alive = false;
        };
    }

    process(inputs) {
        if (!this._alive) return false;

        const input = inputs[0];
        if (!input || !input[0] || input[0].length === 0) return true;

        const src = input[0];
        const srcLen = src.length;

        let pos = this._srcPos;
        let prev = this._prevSample;

        while (pos < srcLen) {
            const idx = Math.floor(pos);
            const frac = pos - idx;
            const cur = idx < srcLen ? src[idx] : 0;
            const next = (idx + 1) < srcLen ? src[idx + 1] : cur;
            const sample = cur + frac * (next - cur);

            this._accum[this._accumLen++] = sample;

            if (this._accumLen >= this._chunkSamples) {
                this._sendChunk();
            }

            pos += this._ratio;
        }

        this._srcPos = pos - srcLen;
        if (srcLen > 0) {
            this._prevSample = src[srcLen - 1];
        }

        return true;
    }

    _sendChunk() {
        const pcm = new Int16Array(this._chunkSamples);
        for (let i = 0; i < this._chunkSamples; i++) {
            let s = this._accum[i];
            if (s > 1) s = 1;
            else if (s < -1) s = -1;
            pcm[i] = (s * 32767) | 0;
        }

        this.port.postMessage(pcm.buffer, [pcm.buffer]);
        this._accumLen = 0;
    }
}

registerProcessor('voice-capture-processor', VoiceCaptureProcessor);