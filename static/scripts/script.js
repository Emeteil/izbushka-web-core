class RobotEmotions {
    constructor() {
        this.face = document.querySelector('.face-container');
        this.leftEye = document.querySelector('.left-eye');
        this.rightEye = document.querySelector('.right-eye');
        this.mouth = document.querySelector('.mouth');
        this.leftEyebrow = document.querySelector('.left-eyebrow');
        this.rightEyebrow = document.querySelector('.right-eyebrow');
        this.pupils = document.querySelectorAll('.pupil');
        
        this.socket = null;
        this.shakeInterval = null;
        this.currentEmotion = 'neutral';
        this.token = this.getTokenFromURL() || this.getCookie('token');

        this.init();
    }

    init() {
        this.followCursor();
        this.setEmotion('neutral');
        this.initWebSocket();
        this.updateTokenInUI();
    }

    getTokenFromURL() {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('token');
    }

    getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }

    updateTokenInUI() {
        if (this.token && window.location.pathname === '/') {
            console.log('Token loaded:', this.token.substring(0, 10) + '...');
        }
    }

    initWebSocket() {
        const options = {};
        
        if (this.token) {
            options.query = { token: this.token };
        }
        
        this.socket = io(options);
        
        this.socket.on('connect', () => {
            console.log('Connected to WebSocket server');
        });
        
        this.socket.on('system.emotion_changed', (data) => {
            console.log('Emotion changed via WebSocket:', data.emotion);
            this.setEmotion(data.emotion);
        });
        
        this.socket.on('emotion.current', (data) => {
            console.log('Current emotion:', data.emotion);
            this.setEmotion(data.emotion);
        });
        
        this.socket.on('error', (data) => {
            console.error('WebSocket error:', data.message);
            alert('Ошибка: ' + data.message);
        });
        
        this.socket.on('disconnect', () => {
            console.log('Disconnected from WebSocket server');
        });
    }

    getAuthHeaders() {
        const headers = {
            'Content-Type': 'application/json'
        };
        
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        
        return headers;
    }

    setEmotionViaAPI(emotion) {
        if (this.socket && this.socket.connected) {
            this.socket.emit('emotion.set', { emotion: emotion });
        } else {
            this.setEmotionViaHTTP(emotion);
        }
    }

    setEmotionViaHTTP(emotion) {
        fetch('/api/emotions/current', {
            method: 'PUT',
            headers: this.getAuthHeaders(),
            body: JSON.stringify({ emotion: emotion })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                this.setEmotion(emotion);
            } else {
                console.error('Error setting emotion:', data);
            }
        })
        .catch(error => {
            console.error('HTTP request failed:', error);
            this.setEmotion(emotion);
        });
    }

    happyEffect() {
        this.face.style.transform = 'scale(1.05)';
    }

    sadEffect() {
        this.face.style.transform = 'scale(0.95)';
        this.pupils.forEach(pupil => {
            pupil.style.transform = 'translate(-50%, -30%)';
        });
    }

    angryEffect() {
        let shakeCount = 0;
        const shakeInterval = setInterval(() => {
            this.face.style.transform = `scale(1.02) translateX(${shakeCount % 2 === 0 ? -3 : 3}px)`;
            shakeCount++;
            if (shakeCount > 6) {
                clearInterval(shakeInterval);
                this.face.style.transform = 'scale(1.02)';
            }
        }, 50);
    }

    surprisedEffect() {
        this.face.style.transform = 'scale(1.1)';
    }

    winkEffect() {
        this.face.style.transform = 'scale(1.03)';
        setTimeout(() => {
            this.rightEye.style.height = '100%';
            this.rightEye.querySelector('.pupil').style.display = 'block';
            setTimeout(() => {
                this.face.style.transform = 'scale(1)';
            }, 500);
        }, 300);
    }

    aggressiveEffect() {
        document.body.classList.add('aggressive-mode');
        this.face.style.transform = 'scale(1.05)';

        if (this.shakeInterval) {
            clearInterval(this.shakeInterval);
        }

        let shakeCount = 0;
        this.shakeInterval = setInterval(() => {
            const offsetX = (shakeCount % 2 === 0 ? -4 : 4);
            const offsetY = (Math.random() - 0.5) * 2;
            this.face.style.transform = `scale(1.05) translate(${offsetX}px, ${offsetY}px)`;
            shakeCount++;
        }, 60);

        setTimeout(() => {
            this.pupils.forEach(pupil => {
                pupil.style.transform = 'translate(-50%, -50%) scale(1.2)';
            });
        }, 100);
    }

    confusedEffect() {
        let shakeCount = 0;
        const shakeInterval = setInterval(() => {
            const rotation = shakeCount % 2 === 0 ? -5 : -3;
            this.face.style.transform = `scale(1.02) rotate(${rotation}deg)`;
            shakeCount++;
            if (shakeCount > 4) {
                clearInterval(shakeInterval);
                this.face.style.transform = 'scale(1.02) rotate(-5deg)';
            }
        }, 150);

        setTimeout(() => {
            this.pupils[0].style.transform = 'translate(-70%, -50%)';
            this.pupils[1].style.transform = 'translate(-30%, -50%)';
        }, 100);
    }

    setEmotion(emotion) {
        if (this.currentEmotion === emotion) return;
        this.currentEmotion = emotion;

        document.body.classList.remove('aggressive-mode');
        if (this.shakeInterval) {
            clearInterval(this.shakeInterval);
            this.shakeInterval = null;
        }

        this.face.style.transform = 'scale(1)';
        this.face.className = 'face-container';

        setTimeout(() => {
            this.face.classList.add(emotion);
        }, 10);

        switch (emotion) {
            case 'happy':
                this.happyEffect();
                break;
            case 'sad':
                this.sadEffect();
                break;
            case 'angry':
                this.angryEffect();
                break;
            case 'surprised':
                this.surprisedEffect();
                break;
            case 'wink':
                this.winkEffect();
                break;
            case 'neutral':
                this.face.style.transform = 'scale(1)';
                break;
            case 'aggressive':
                this.aggressiveEffect();
                break;
            case 'confused':
                this.confusedEffect();
                break;
        }
    }

    followCursor() {
        document.addEventListener('mousemove', (e) => {
            const eyes = document.querySelectorAll('.eye');
            eyes.forEach(eye => {
                const eyeRect = eye.getBoundingClientRect();
                const eyeCenterX = eyeRect.left + eyeRect.width / 2;
                const eyeCenterY = eyeRect.top + eyeRect.height / 2;

                const angle = Math.atan2(e.clientY - eyeCenterY, e.clientX - eyeCenterX);

                const maxDistance = this.currentEmotion === 'aggressive' ? 55 : 10;
                const distance = Math.min(maxDistance,
                    Math.sqrt(Math.pow(e.clientX - eyeCenterX, 2) + Math.pow(e.clientY - eyeCenterY, 2)) / 20
                );

                const pupil = eye.querySelector('.pupil');
                const pupilX = Math.cos(angle) * distance;
                const pupilY = Math.sin(angle) * distance;

                pupil.style.transform = `translate(calc(-50% + ${pupilX}px), calc(-50% + ${pupilY}px))`;
            });
        });
    }
}

function setEmotion(emotion) {
    if (window.robot) {
        window.robot.setEmotionViaAPI(emotion);
    }
}

function startDemoMode() {
    const emotions = ['happy', 'sad', 'angry', 'surprised', 'neutral', 'wink', 'aggressive', 'confused'];
    let currentEmotion = 0;

    setInterval(() => {
        setEmotion(emotions[currentEmotion]);
        currentEmotion = (currentEmotion + 1) % emotions.length;
    }, 3000);
}

let robot;
document.addEventListener('DOMContentLoaded', () => {
    robot = new RobotEmotions();
    window.robot = robot;
});