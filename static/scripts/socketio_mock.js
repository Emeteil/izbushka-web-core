class MockSocketIO {
    constructor(url) {
        this.ws = new WebSocket(url);
        this.callbacks = {};
        this.connected = false;

        this.ws.onopen = () => {
            this.connected = true;
            this.trigger('connect');
        };

        this.ws.onclose = () => {
            this.connected = false;
            this.trigger('disconnect');
        };

        this.ws.onmessage = (e) => {
            try {
                const msg = JSON.parse(e.data);
                if (msg.event) {
                    this.trigger(msg.event, msg.data);
                }
            } catch (err) {
                console.error("Failed to parse websocket message:", err);
            }
        };

        this.ws.onerror = (e) => {
            this.trigger('error', { message: "WebSocket connection error" });
        };
    }

    on(event, callback) {
        if (!this.callbacks[event]) {
            this.callbacks[event] = [];
        }
        this.callbacks[event].push(callback);
    }

    emit(event, data) {
        if (this.connected) {
            this.ws.send(JSON.stringify({ event: event, data: data }));
        } else {
            console.warn("Attempted to emit", event, "before socket was connected");
        }
    }

    trigger(event, data) {
        if (this.callbacks[event]) {
            this.callbacks[event].forEach(cb => cb(data));
        }
    }
}

window.io = function (options) {
    let url = (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + window.location.host + '/ws';
    if (options && options.query && options.query.token) {
        url += '?token=' + encodeURIComponent(options.query.token);
    }
    return new MockSocketIO(url);
};