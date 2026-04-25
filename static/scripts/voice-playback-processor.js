class VoicePlaybackProcessor extends AudioWorkletProcessor {
    constructor(options) {
        super();

        const opts = options.processorOptions || {};
        this._srcRate = opts.targetSampleRate || 8000;
        this._chunkSamples = opts.chunkSamples || 160;
        this._minChunks = opts.minBufferChunks || 3;
        this._maxChunks = opts.maxBufferChunks || 25;
        this._gainRampSamples = opts.gainRampSamples || 64;

        this._ratio = this._srcRate / sampleRate;

        const ringLen = Math.max(
            (opts.ringBufferSeconds || 2) * this._srcRate,
            this._chunkSamples * this._maxChunks * 2
        );
        this._ringSize = 1;
        while (this._ringSize < ringLen) this._ringSize <<= 1;
        this._ringMask = this._ringSize - 1;
        this._ring = new Float32Array(this._ringSize);
        this._writeIdx = 0;
        this._readIdx = 0;

        this._buffered = 0;

        this._state = 'buffering';

        this._gain = 0;
        this._targetGain = 0;
        this._gainStep = 1 / this._gainRampSamples;

        this._fracPos = 0;

        this._alive = true;
        this.port.onmessage = (e) => {
            if (e.data === 'stop') {
                this._alive = false;
                return;
            }
            if (e.data instanceof ArrayBuffer) {
                this._enqueue(e.data);
            }
        };
    }

    _enqueue(ab) {
        const pcm16 = new Int16Array(ab);
        const len = pcm16.length;

        if (this._buffered + len > this._ringSize) {
            const excess = (this._buffered + len) - (this._chunkSamples * this._maxChunks);
            if (excess > 0) {
                this._readIdx = (this._readIdx + excess) & this._ringMask;
                this._buffered -= excess;
                if (this._buffered < 0) this._buffered = 0;
            }
        }

        for (let i = 0; i < len; i++) {
            this._ring[(this._writeIdx + i) & this._ringMask] = pcm16[i] / 32768;
        }
        this._writeIdx = (this._writeIdx + len) & this._ringMask;
        this._buffered += len;

        if (this._state === 'buffering' && this._buffered >= this._chunkSamples * this._minChunks) {
            this._state = 'playing';
            this._targetGain = 1;
        }
    }

    process(inputs, outputs) {
        if (!this._alive) return false;

        const output = outputs[0];
        if (!output || !output[0]) return true;

        const out = output[0];
        const outLen = out.length;

        for (let i = 0; i < outLen; i++) {
            if (this._gain < this._targetGain) {
                this._gain = Math.min(this._gain + this._gainStep, this._targetGain);
            } else if (this._gain > this._targetGain) {
                this._gain = Math.max(this._gain - this._gainStep, this._targetGain);
            }

            if (this._state === 'playing' && this._buffered > 0) {
                const intPos = Math.floor(this._fracPos);
                const frac = this._fracPos - intPos;

                while (intPos > 0 && this._buffered > 0) {
                    this._readIdx = (this._readIdx + 1) & this._ringMask;
                    this._buffered--;
                    this._fracPos -= 1;
                }

                const idx0 = this._readIdx;
                const idx1 = (this._readIdx + 1) & this._ringMask;
                const s0 = this._ring[idx0];
                const s1 = this._buffered > 1 ? this._ring[idx1] : s0;

                out[i] = (s0 + frac * (s1 - s0)) * this._gain;

                this._fracPos += this._ratio;

                const advance = Math.floor(this._fracPos);
                if (advance > 0) {
                    const actualAdvance = Math.min(advance, this._buffered);
                    this._readIdx = (this._readIdx + actualAdvance) & this._ringMask;
                    this._buffered -= actualAdvance;
                    this._fracPos -= advance;

                    if (this._buffered <= 0) {
                        this._buffered = 0;
                        this._state = 'buffering';
                        this._targetGain = 0;
                    }
                }
            } else {
                out[i] = 0;
            }
        }

        for (let ch = 1; ch < output.length; ch++) {
            output[ch].set(out);
        }

        return true;
    }
}

registerProcessor('voice-playback-processor', VoicePlaybackProcessor);