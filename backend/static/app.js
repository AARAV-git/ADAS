// ═══════════════════════════════════════════════════════════════════════════
//  RoadSense AI — Dashboard Client (Video-Centric Edition)
// ═══════════════════════════════════════════════════════════════════════════

let socket = null;
let currentTelemetry = null;
let lastAlertsJson = "";

// Camera state variables
let cameraStream         = null;
let localVideo           = null;
let isCameraMode         = false;
let sendingFrame         = false;
const captureCanvas      = document.createElement('canvas');
const captureCtx         = captureCanvas.getContext('2d');

// ── DOM References ──────────────────────────────────────────────────────────
const videoSelect        = document.getElementById('video-select');
const streamBtn          = document.getElementById('stream-btn');
const btnIcon            = document.getElementById('btn-icon');
const btnLabel           = document.getElementById('btn-label');
const cameraBtn          = document.getElementById('camera-btn');
const cameraBtnLabel     = document.getElementById('camera-btn-label');
const mobileUrl          = document.getElementById('mobile-url');
const statusDot          = document.getElementById('status-dot');
const statusText         = document.getElementById('status-text');
const placeholderOverlay = document.getElementById('placeholder-overlay');

// Toolbar telemetry
const fpsVal             = document.getElementById('fps-val');

// Floating HUD on video
const videoHud           = document.getElementById('video-hud');
const hudVideoName       = document.getElementById('hud-video-name');
const hudFrame           = document.getElementById('hud-frame');
const hudObjects         = document.getElementById('hud-objects');
const hudRiskBadge       = document.getElementById('hud-risk-badge');
const hudRiskVal         = document.getElementById('hud-risk-val');
const hudChaosFill       = document.getElementById('hud-chaos-fill');
const hudChaosVal        = document.getElementById('hud-chaos-val');

// Chaos Dial
const chaosScoreEl       = document.getElementById('chaos-score');
const chaosLevelEl       = document.getElementById('chaos-level');
const chaosCircle        = document.getElementById('chaos-circle');
const cbVehicles         = document.getElementById('cb-vehicles');
const cbVariance         = document.getElementById('cb-variance');
const cbIntrusion        = document.getElementById('cb-intrusion');
const cbPedestrians      = document.getElementById('cb-pedestrians');

// Alerts
const alertsLog          = document.getElementById('alerts-log');
const alertCountBadge    = document.getElementById('alert-count-badge');

// Explainability
const explainPlaceholder  = document.getElementById('explain-placeholder');
const explainContent      = document.getElementById('explain-content');
const explainLoader       = document.getElementById('explain-loader');
const explainRiskPill     = document.getElementById('explain-risk-pill');
const explainTarget       = document.getElementById('explain-target');
const explainType         = document.getElementById('explain-type');
const explanationText     = document.getElementById('explanation-text');
const explanationActionText = document.getElementById('explanation-action-text');

// Canvases
const streamCanvas = document.getElementById('stream-canvas');
const streamCtx    = streamCanvas.getContext('2d');
const radarCanvas  = document.getElementById('radar-canvas');
const radarCtx     = radarCanvas.getContext('2d');

// Color map
const CLASS_COLORS = {
    "pedestrian":           "#ffff00",
    "rider":                "#00ff66",
    "vulnerable_road_user": "#ff3344",
    "motorcycle":           "#bd00ff",
    "car":                  "#00c800",
    "bus":                  "#c80032",
    "truck":                "#a000a0",
    "auto_rickshaw":        "#00f0ff",
    "bicycle":              "#ffa500",
    "vehicle":              "#8a99ad"
};

// ── Initialize ──────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
    fetchVideoList();
    fetchNetworkInfo();
    initRadar();

    videoSelect.addEventListener('change', () => {
        streamBtn.disabled = !videoSelect.value;
    });

    streamBtn.addEventListener('click', toggleStream);
    cameraBtn.addEventListener('click', toggleCamera);
});

// ── Fetch network IP info for mobile testing ───────────────────────────────
async function fetchNetworkInfo() {
    try {
        const resp = await fetch('/api/network-info');
        const data = await resp.json();
        if (data && data.url) {
            if (mobileUrl) {
                mobileUrl.textContent = data.url;
            }
        }
    } catch (err) {
        console.warn("Failed to fetch network info:", err);
    }
}

// ── Fetch available videos ──────────────────────────────────────────────────
async function fetchVideoList() {
    try {
        const resp = await fetch('/api/videos');
        const videos = await resp.json();
        videos.forEach(v => {
            const opt = document.createElement('option');
            opt.value = v;
            opt.textContent = v;
            videoSelect.appendChild(opt);
        });
    } catch (err) {
        console.error("Error fetching video list:", err);
    }
}

// ── Toggle Stream ───────────────────────────────────────────────────────────
function toggleStream() {
    if (socket && socket.readyState === WebSocket.OPEN) {
        stopStream();
    } else {
        startStream();
    }
}

function startStream() {
    if (isCameraMode) {
        stopCamera();
    }

    const selected = videoSelect.value;
    if (!selected) return;

    // Show video HUD, hide placeholder
    placeholderOverlay.classList.add('hidden');
    videoHud.classList.remove('hidden');
    hudVideoName.textContent = selected;

    // Button → Stop mode
    btnIcon.textContent = '■';
    btnLabel.textContent = 'Stop Stream';
    streamBtn.classList.add('streaming');

    // Connection status
    statusDot.className = 'status-dot online';
    statusText.textContent = 'Connecting…';

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws/stream/${selected}`;

    socket = new WebSocket(wsUrl);
    socket.binaryType = 'arraybuffer';

    socket.onopen = () => {
        statusText.textContent = 'Connected';
        console.log('[WS] Stream opened.');
    };

    socket.onmessage = (event) => {
        if (typeof event.data === 'string') {
            // ── Text frame → JSON telemetry ──
            try {
                currentTelemetry = JSON.parse(event.data);
                updateTelemetryUI(currentTelemetry);
            } catch (e) {
                console.warn('[WS] Bad JSON:', e);
            }
        } else {
            // ── Binary frame → JPEG image (Off-thread Decode) ──
            const blob = new Blob([event.data], { type: 'image/jpeg' });
            createImageBitmap(blob).then(bitmap => {
                streamCtx.clearRect(0, 0, streamCanvas.width, streamCanvas.height);
                streamCtx.drawImage(bitmap, 0, 0, streamCanvas.width, streamCanvas.height);
                bitmap.close();
            }).catch(err => {
                console.warn('[WS] Bitmap decode failed, fallback:', err);
                const url  = URL.createObjectURL(blob);
                const img  = new Image();
                img.onload = () => {
                    streamCtx.clearRect(0, 0, streamCanvas.width, streamCanvas.height);
                    streamCtx.drawImage(img, 0, 0, streamCanvas.width, streamCanvas.height);
                    URL.revokeObjectURL(url);
                };
                img.src = url;
            });
        }
    };

    socket.onclose = () => {
        statusText.textContent = 'Disconnected';
        statusDot.className = 'status-dot offline';
        resetStreamUI();
    };

    socket.onerror = (err) => {
        console.error('[WS] Error:', err);
    };
}

function stopStream() {
    if (socket) {
        socket.close();
        socket = null;
    }
    resetStreamUI();
}

function resetStreamUI() {
    // Restore placeholder
    placeholderOverlay.classList.remove('hidden');
    videoHud.classList.add('hidden');

    // Button → Start mode
    btnIcon.textContent = '▶';
    btnLabel.textContent = 'Start Stream';
    streamBtn.classList.remove('streaming');

    if (!isCameraMode) {
        streamBtn.disabled = !videoSelect.value;
        videoSelect.disabled = false;
        cameraBtn.disabled = false;
    }

    statusDot.className = 'status-dot offline';
    statusText.textContent = 'Offline';

    // Reset telemetry
    fpsVal.textContent = '0.0';
    hudFrame.textContent = 'Frame: 0';
    hudObjects.textContent = 'Objects: 0';
    hudRiskVal.textContent = 'LOW';
    hudRiskBadge.className = 'hud-risk-badge low';
    hudChaosVal.textContent = '0';
    hudChaosFill.style.width = '0%';
    hudChaosFill.style.background = 'var(--neon-green)';

    // Reset chaos dial
    updateChaosDial(0, 'Calm');
    cbVehicles.style.width = '0%';
    cbVariance.style.width = '0%';
    cbIntrusion.style.width = '0%';
    cbPedestrians.style.width = '0%';

    // Reset alerts
    lastAlertsJson = "";
    alertCountBadge.textContent = '0';
    alertsLog.innerHTML = `
        <div class="no-alerts">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="icon">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
            </svg>
            <p>No active hazards</p>
        </div>
    `;

    // Reset explainability
    explainPlaceholder.classList.remove('hidden');
    explainContent.classList.add('hidden');
    explainLoader.classList.add('hidden');

    // Clear canvas
    streamCtx.clearRect(0, 0, streamCanvas.width, streamCanvas.height);
    initRadar();
}

// ── Update Telemetry UI ─────────────────────────────────────────────────────
function updateTelemetryUI(data) {
    // Toolbar FPS
    fpsVal.textContent = data.fps;

    // Floating HUD
    hudFrame.textContent   = `Frame: ${data.frame_id}`;
    hudObjects.textContent = `Objects: ${data.tracked.length}`;

    // Risk badge
    let highestRisk = 'LOW';
    if (data.alerts && data.alerts.length > 0) {
        highestRisk = data.alerts[0].risk_level;
    }
    hudRiskVal.textContent = highestRisk;
    hudRiskBadge.className = `hud-risk-badge ${highestRisk.toLowerCase()}`;

    // HUD chaos mini-bar
    const chaosScore = data.chaos.score;
    hudChaosVal.textContent = Math.round(chaosScore);
    hudChaosFill.style.width = `${chaosScore}%`;
    if (chaosScore > 70)      { hudChaosFill.style.background = 'var(--neon-red)'; hudChaosVal.style.color = 'var(--neon-red)'; }
    else if (chaosScore > 40) { hudChaosFill.style.background = 'var(--neon-orange)'; hudChaosVal.style.color = 'var(--neon-orange)'; }
    else                      { hudChaosFill.style.background = 'var(--neon-green)'; hudChaosVal.style.color = 'var(--neon-green)'; }

    // Chaos Dial panel
    updateChaosDial(data.chaos.score, data.chaos.level);
    cbVehicles.style.width    = `${data.chaos.breakdown.vehicle_density}%`;
    cbVariance.style.width    = `${data.chaos.breakdown.speed_variance}%`;
    cbIntrusion.style.width   = `${data.chaos.breakdown.lane_intrusion}%`;
    cbPedestrians.style.width = `${data.chaos.breakdown.pedestrian_density}%`;

    // Radar
    drawRadar(data.tracked);

    // Alerts
    updateAlertsLog(data.alerts, data.chaos);
}

// ── Chaos Score Dial ────────────────────────────────────────────────────────
function updateChaosDial(score, level) {
    chaosScoreEl.textContent = Math.round(score);
    chaosLevelEl.textContent = level;

    if (level === 'Calm') {
        chaosLevelEl.className = 'level text-green';
        chaosCircle.style.stroke = 'var(--neon-green)';
    } else if (level === 'Moderate') {
        chaosLevelEl.className = 'level text-orange';
        chaosCircle.style.stroke = 'var(--neon-orange)';
    } else {
        chaosLevelEl.className = 'level text-red';
        chaosCircle.style.stroke = 'var(--neon-red)';
    }

    const circumference = 251.3;
    const offset = circumference - (circumference * score / 100);
    chaosCircle.style.strokeDasharray  = `${circumference} ${circumference}`;
    chaosCircle.style.strokeDashoffset = offset;
}

// ── Alerts Log ──────────────────────────────────────────────────────────────
function updateAlertsLog(alerts, chaos) {
    const currentJson = JSON.stringify(alerts || []);
    if (currentJson === lastAlertsJson) {
        return;
    }
    lastAlertsJson = currentJson;

    alertCountBadge.textContent = (alerts && alerts.length) || 0;

    if (!alerts || alerts.length === 0) {
        alertsLog.innerHTML = `
            <div class="no-alerts">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="icon">
                    <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
                </svg>
                <p>No active hazards</p>
            </div>
        `;
        return;
    }

    alertsLog.innerHTML = '';
    alerts.forEach(alert => {
        const card = document.createElement('div');
        const lvl  = alert.risk_level.toLowerCase();
        card.className = `alert-card ${lvl}`;

        const labelText = alert.label.replace('_', ' ').toUpperCase();

        card.innerHTML = `
            <div class="alert-header">
                <span class="title">${labelText} #${alert.track_id}</span>
                <span class="risk">${alert.risk_level}</span>
            </div>
            <div class="alert-desc">${alert.message}</div>
            <div class="alert-actions">
                <span class="alert-action-text">${alert.action}</span>
                <button class="explain-btn" data-track-id="${alert.track_id}">Explain</button>
            </div>
        `;

        card.querySelector('.explain-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            requestLLMExplain(alert, chaos);
        });

        card.addEventListener('click', () => {
            requestLLMExplain(alert, chaos);
        });

        alertsLog.appendChild(card);
    });
}

// ── Radar Visualization ─────────────────────────────────────────────────────
function initRadar() {
    const w = radarCanvas.width;
    const h = radarCanvas.height;
    radarCtx.clearRect(0, 0, w, h);

    // Concentric circles
    radarCtx.strokeStyle = 'rgba(0, 240, 255, 0.1)';
    radarCtx.lineWidth = 1;

    [110, 70, 35].forEach(r => {
        radarCtx.beginPath();
        radarCtx.arc(w/2, h/2 + 40, r, 0, 2 * Math.PI);
        radarCtx.stroke();
    });

    // Cross-hair
    radarCtx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
    radarCtx.beginPath();
    radarCtx.moveTo(w/2, h/2 - 70);
    radarCtx.lineTo(w/2, h/2 + 150);
    radarCtx.moveTo(w/2 - 110, h/2 + 40);
    radarCtx.lineTo(w/2 + 110, h/2 + 40);
    radarCtx.stroke();

    // Ego car
    radarCtx.fillStyle = '#ffffff';
    radarCtx.shadowColor = 'rgba(255, 255, 255, 0.8)';
    radarCtx.shadowBlur = 4;
    radarCtx.fillRect(w/2 - 6, h/2 + 32, 12, 18);
    radarCtx.shadowBlur = 0;
}

function drawRadar(tracked) {
    initRadar();
    const w = radarCanvas.width;
    const h = radarCanvas.height;

    tracked.forEach(obj => {
        const frameW = obj.frame_w || 1280;
        const frameH = obj.frame_h || 720;
        const horizonY  = frameH * 0.35;
        const roadH     = frameH - horizonY;

        let normY = (obj.cy - horizonY) / roadH;
        normY = Math.max(0, Math.min(1, normY));

        const dist  = (1 - normY) * 105 + 10;
        const normX = (obj.cx - frameW/2) / (frameW/2);

        const radarX = w/2 + (normX * dist * 0.8);
        const radarY = (h/2 + 40) - dist;

        const dx = radarX - w/2;
        const dy = radarY - (h/2 + 40);
        if (Math.sqrt(dx*dx + dy*dy) > 115) return;

        const color = CLASS_COLORS[obj.label] || '#ffffff';
        radarCtx.fillStyle   = color;
        radarCtx.shadowColor = color;
        radarCtx.shadowBlur  = 8;

        radarCtx.beginPath();
        radarCtx.arc(radarX, radarY, 5, 0, 2 * Math.PI);
        radarCtx.fill();
        radarCtx.shadowBlur = 0;

        radarCtx.fillStyle = 'rgba(255, 255, 255, 0.7)';
        radarCtx.font = '8px Space Grotesk';
        radarCtx.fillText(`${obj.label.substring(0, 3).toUpperCase()}#${obj.track_id}`, radarX + 8, radarY + 3);
    });
}

// ── LLM Explainability ──────────────────────────────────────────────────────
async function requestLLMExplain(alert, chaos) {
    explainPlaceholder.classList.add('hidden');
    explainContent.classList.add('hidden');
    explainLoader.classList.remove('hidden');

    let position = 'front';
    if (currentTelemetry && currentTelemetry.tracked) {
        const match = currentTelemetry.tracked.find(o => o.track_id === alert.track_id);
        if (match) {
            const cx = match.cx;
            const w  = match.frame_w || 1280;
            if (cx < w * 0.35)      position = 'left';
            else if (cx > w * 0.65) position = 'right';
        }
    }

    try {
        const resp = await fetch('/api/explain', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                event: alert,
                chaos: {
                    score: chaos.score,
                    level: chaos.level,
                    breakdown: chaos.breakdown,
                    object_count: currentTelemetry ? currentTelemetry.tracked.length : 0
                },
                position: position
            })
        });

        const result = await resp.json();

        explainLoader.classList.add('hidden');
        explainContent.classList.remove('hidden');

        const riskLevel = result.risk_level || alert.risk_level;
        explainRiskPill.textContent = riskLevel;
        explainRiskPill.className   = `risk-pill ${riskLevel.toLowerCase()}`;

        explainTarget.textContent = `${alert.label.replace('_', ' ').toUpperCase()} #${alert.track_id}`;
        explainType.textContent   = alert.risk_type.replace('_', ' ').toUpperCase();

        explanationText.textContent       = result.message || alert.message;
        explanationActionText.textContent = result.action  || alert.action;

    } catch (err) {
        console.error('[LLM] Error:', err);

        explainLoader.classList.add('hidden');
        explainContent.classList.remove('hidden');

        explainRiskPill.textContent = alert.risk_level;
        explainRiskPill.className   = `risk-pill ${alert.risk_level.toLowerCase()}`;
        explainTarget.textContent   = `${alert.label.replace('_', ' ').toUpperCase()} #${alert.track_id}`;
        explainType.textContent     = alert.risk_type.replace('_', ' ').toUpperCase();

        explanationText.textContent       = alert.message + ' (Offline fallback)';
        explanationActionText.textContent = alert.action;
    }
}

// ── Camera Streaming Functions ───────────────────────────────────────────────
function toggleCamera() {
    if (isCameraMode) {
        stopCamera();
    } else {
        startCamera();
    }
}

async function startCamera() {
    // Show loading status
    statusDot.className = 'status-dot online';
    statusText.textContent = 'Starting camera…';
    placeholderOverlay.classList.add('hidden');
    videoHud.classList.remove('hidden');
    hudVideoName.textContent = 'Device Camera';
    
    // Stop regular stream if running
    if (socket && !isCameraMode) {
        stopStream();
    }
    
    isCameraMode = true;
    cameraBtn.classList.add('streaming');
    cameraBtnLabel.textContent = 'Stop Camera';
    
    // Disable video streaming buttons while camera runs
    streamBtn.disabled = true;
    videoSelect.disabled = true;
    
    try {
        const constraints = {
            video: {
                width: { ideal: 1280 },
                height: { ideal: 720 },
                facingMode: "environment" // Prefer rear-facing camera on mobile phones!
            },
            audio: false
        };
        
        cameraStream = await navigator.mediaDevices.getUserMedia(constraints);
        
        localVideo = document.createElement('video');
        localVideo.srcObject = cameraStream;
        localVideo.autoplay = true;
        localVideo.playsInline = true;
        
        // Wait for video metadata to load
        await new Promise((resolve) => {
            localVideo.onloadedmetadata = () => {
                resolve();
            };
        });
        
        localVideo.play();
        
        // Connect to /ws/camera WebSocket
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${location.host}/ws/camera`;
        
        socket = new WebSocket(wsUrl);
        socket.binaryType = 'arraybuffer';
        
        socket.onopen = () => {
            statusText.textContent = 'Connected (Camera)';
            console.log('[WS] Camera Stream WebSocket opened.');
            // Start sending frames
            sendCameraFramesLoop();
        };
        
        socket.onmessage = (event) => {
            if (typeof event.data === 'string') {
                try {
                    currentTelemetry = JSON.parse(event.data);
                    updateTelemetryUI(currentTelemetry);
                } catch (e) {
                    console.warn('[WS] Bad JSON:', e);
                }
            } else {
                const blob = new Blob([event.data], { type: 'image/jpeg' });
                createImageBitmap(blob).then(bitmap => {
                    streamCtx.clearRect(0, 0, streamCanvas.width, streamCanvas.height);
                    streamCtx.drawImage(bitmap, 0, 0, streamCanvas.width, streamCanvas.height);
                    bitmap.close();
                }).catch(err => {
                    console.warn('[Camera] Bitmap decode failed, fallback:', err);
                    const url  = URL.createObjectURL(blob);
                    const img  = new Image();
                    img.onload = () => {
                        streamCtx.clearRect(0, 0, streamCanvas.width, streamCanvas.height);
                        streamCtx.drawImage(img, 0, 0, streamCanvas.width, streamCanvas.height);
                        URL.revokeObjectURL(url);
                    };
                    img.src = url;
                });
            }
        };
        
        socket.onclose = () => {
            console.log('[WS] Camera Stream WebSocket closed.');
            if (isCameraMode) {
                stopCamera();
            }
        };
        
        socket.onerror = (err) => {
            console.error('[WS] Camera Error:', err);
        };
        
    } catch (err) {
        console.error("Failed to access device camera:", err);
        alert("Could not access device camera: " + err.message);
        stopCamera();
    }
}

function sendCameraFramesLoop() {
    if (!isCameraMode || !socket || socket.readyState !== WebSocket.OPEN || !localVideo) {
        return;
    }
    
    if (!sendingFrame && localVideo.readyState >= 2) {
        sendingFrame = true;
        
        // Match size
        const w = localVideo.videoWidth || 640;
        const h = localVideo.videoHeight || 480;
        
        const targetW = w > 854 ? 854 : w;
        const targetH = Math.round(targetW * (h / w));
        
        captureCanvas.width = targetW;
        captureCanvas.height = targetH;
        
        captureCtx.drawImage(localVideo, 0, 0, targetW, targetH);
        
        captureCanvas.toBlob((blob) => {
            if (blob && socket && socket.readyState === WebSocket.OPEN) {
                socket.send(blob);
                sendingFrame = false;
                setTimeout(sendCameraFramesLoop, 40); // Target ~25 FPS loop
            } else {
                sendingFrame = false;
                setTimeout(sendCameraFramesLoop, 100);
            }
        }, 'image/jpeg', 0.60); // 0.60 quality is highly compact and processes faster
    } else {
        setTimeout(sendCameraFramesLoop, 33);
    }
}

function stopCamera() {
    isCameraMode = false;
    
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
    }
    
    if (localVideo) {
        localVideo.pause();
        localVideo.srcObject = null;
        localVideo = null;
    }
    
    if (socket) {
        socket.close();
        socket = null;
    }
    
    // Reset camera button
    cameraBtn.classList.remove('streaming');
    cameraBtnLabel.textContent = 'Use Camera';
    
    // Enable stream buttons again
    streamBtn.disabled = !videoSelect.value;
    videoSelect.disabled = false;
    
    resetStreamUI();
}
