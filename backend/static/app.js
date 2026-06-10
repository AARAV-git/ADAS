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

    // History event listeners
    const historyBtn = document.getElementById('history-btn');
    if (historyBtn) historyBtn.addEventListener('click', toggleHistoryDrawer);

    const closeHistoryBtn = document.getElementById('close-history-btn');
    if (closeHistoryBtn) closeHistoryBtn.addEventListener('click', closeHistoryDrawer);

    const backToSessionsBtn = document.getElementById('back-to-sessions-btn');
    if (backToSessionsBtn) backToSessionsBtn.addEventListener('click', showSessionsListView);
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
let _awaitingResponse = false;   // backpressure: wait for server to reply

function toggleCamera() {
    if (isCameraMode) {
        stopCamera();
    } else {
        startCamera();
    }
}

/**
 * getUserMedia polyfill — works on HTTP for localhost, but on remote IPs
 * the browser blocks it.  We detect that early and show a helpful message.
 */
function _getMediaStream(constraints) {
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        return navigator.mediaDevices.getUserMedia(constraints);
    }
    // Legacy fallback (older Chrome / Firefox)
    const legacyGetUserMedia =
        navigator.getUserMedia ||
        navigator.webkitGetUserMedia ||
        navigator.mozGetUserMedia;
    if (legacyGetUserMedia) {
        return new Promise((resolve, reject) => {
            legacyGetUserMedia.call(navigator, constraints, resolve, reject);
        });
    }
    return Promise.reject(new Error(
        'Camera API not available. Use HTTPS or access via localhost/127.0.0.1.'
    ));
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
        // Lower resolution = faster capture + encode + transfer + YOLO inference
        const constraints = {
            video: {
                width:  { ideal: 640 },
                height: { ideal: 480 },
                facingMode: 'environment',   // rear camera on phones
                frameRate:  { ideal: 15, max: 20 },
            },
            audio: false,
        };

        cameraStream = await _getMediaStream(constraints);

        localVideo = document.createElement('video');
        localVideo.srcObject = cameraStream;
        localVideo.autoplay = true;
        localVideo.playsInline = true;
        localVideo.muted = true;

        // Wait for video metadata
        await new Promise((resolve, reject) => {
            localVideo.onloadedmetadata = resolve;
            setTimeout(() => reject(new Error('Camera timed out')), 8000);
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
            _awaitingResponse = false;
            lastTelemetryTime = Date.now();
            requestAnimationFrame(localRenderLoop);
            sendCameraFramesLoop();
        };

        socket.onmessage = (event) => {
            if (typeof event.data === 'string') {
                try {
                    currentTelemetry = JSON.parse(event.data);
                    lastTelemetryTime = Date.now();
                    updateTelemetryUI(currentTelemetry);
                } catch (e) {
                    console.warn('[WS] Bad JSON:', e);
                }
                // ── Backpressure: now that we got the response, send the next frame
                _awaitingResponse = false;
                sendCameraFramesLoop();
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
        console.error('Failed to access device camera:', err);

        let msg = err.message || String(err);
        if (msg.includes('not available') || msg.includes('getUserMedia')) {
            msg = 'Camera API is blocked. On phones, you must use HTTPS.\n\n'
                + 'To test locally:\n'
                + '• On the same PC: open http://127.0.0.1:8000\n'
                + '• On a phone: use Chrome flags (chrome://flags → Insecure origins treated as secure → add your server URL)';
        }
        alert('Camera error: ' + msg);
        stopCamera();
    }
}

let lastTelemetryTime = 0;

function localRenderLoop() {
    if (!isCameraMode || !localVideo) {
        return;
    }

    const vw = localVideo.videoWidth || 640;
    const vh = localVideo.videoHeight || 480;
    if (streamCanvas.width !== vw || streamCanvas.height !== vh) {
        streamCanvas.width = vw;
        streamCanvas.height = vh;
    }

    // Draw the local camera frame directly to canvas
    streamCtx.drawImage(localVideo, 0, 0, streamCanvas.width, streamCanvas.height);

    // Draw bounding boxes on top
    if (currentTelemetry && currentTelemetry.tracked) {
        const elapsedSec = (Date.now() - lastTelemetryTime) / 1000;
        const elapsedFrames = elapsedSec * 30.0; // Assume 30 FPS playback rate
        const clampedElapsed = Math.min(elapsedFrames, 15.0); // limit drift

        const extrapolatedTracked = currentTelemetry.tracked.map(obj => {
            const vx = (obj.velocity && obj.velocity[0]) || 0.0;
            const vy = (obj.velocity && obj.velocity[1]) || 0.0;
            return {
                ...obj,
                bbox: [
                    obj.bbox[0] + vx * clampedElapsed,
                    obj.bbox[1] + vy * clampedElapsed,
                    obj.bbox[2] + vx * clampedElapsed,
                    obj.bbox[3] + vy * clampedElapsed
                ],
                cx: obj.cx + vx * clampedElapsed,
                cy: obj.cy + vy * clampedElapsed
            };
        });

        drawBoundingBoxes(streamCtx, extrapolatedTracked);
    }

    requestAnimationFrame(localRenderLoop);
}

function drawBoundingBoxes(ctx, tracked) {
    if (!tracked || tracked.length === 0) return;

    tracked.forEach(obj => {
        const frameW = obj.frame_w || 640;
        const frameH = obj.frame_h || 480;
        const scaleX = streamCanvas.width / frameW;
        const scaleY = streamCanvas.height / frameH;

        const x1 = obj.bbox[0] * scaleX;
        const y1 = obj.bbox[1] * scaleY;
        const x2 = obj.bbox[2] * scaleX;
        const y2 = obj.bbox[3] * scaleY;
        const bw = x2 - x1;
        const bh = y2 - y1;

        const color = CLASS_COLORS[obj.label] || '#ffffff';

        // 1. Draw Bounding Box
        ctx.strokeStyle = color;
        ctx.lineWidth = (obj.label === 'vulnerable_road_user' || obj.label === 'auto_rickshaw') ? 4 : 2;
        ctx.strokeRect(x1, y1, bw, bh);

        // 2. Draw Label pill above the box
        const shortLabels = {
            "vulnerable_road_user": "VRU",
            "auto_rickshaw": "AUTO",
            "pedestrian": "PED",
            "motorcycle": "MOTO",
            "bicycle": "BIKE"
        };
        const shortLabel = shortLabels[obj.label] || obj.label.toUpperCase();
        const confText = obj.conf ? ` ${(obj.conf).toFixed(2)}` : '';
        const speedText = obj.speed ? ` ${Math.round(obj.speed)}px/f` : '';
        const tag = `#${obj.track_id} ${shortLabel}${confText}${speedText}`;

        ctx.font = 'bold 11px Space Grotesk';
        const textWidth = ctx.measureText(tag).width;

        ctx.fillStyle = color;
        ctx.fillRect(x1 - 1, y1 - 16, textWidth + 8, 16);

        ctx.fillStyle = '#000000';
        ctx.fillText(tag, x1 + 3, y1 - 4);

        // 3. Draw Trajectory tail (dots/lines)
        if (obj.trajectory && obj.trajectory.length > 1) {
            ctx.beginPath();
            ctx.strokeStyle = color;
            ctx.lineWidth = 1.5;
            for (let i = 0; i < obj.trajectory.length; i++) {
                const tx = obj.trajectory[i][0] * scaleX;
                const ty = obj.trajectory[i][1] * scaleY;
                if (i === 0) {
                    ctx.moveTo(tx, ty);
                } else {
                    ctx.lineTo(tx, ty);
                }
            }
            ctx.stroke();
        }

        // 4. VRU warning ring
        if (obj.label === 'vulnerable_road_user') {
            const cx = obj.cx * scaleX;
            const cy = obj.cy * scaleY;
            const r = Math.max(bw, bh) / 2 + 12;

            ctx.strokeStyle = '#ff3c3c';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(cx, cy, r, 0, 2 * Math.PI);
            ctx.stroke();

            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.arc(cx, cy, r + 6, 0, 2 * Math.PI);
            ctx.stroke();
        }
    });
}

function sendCameraFramesLoop() {
    if (!isCameraMode || !socket || socket.readyState !== WebSocket.OPEN || !localVideo) {
        return;
    }
    // Don't send if we're still waiting for the server to respond (backpressure)
    if (_awaitingResponse) {
        return;
    }
    if (localVideo.readyState < 2) {
        // Video not ready yet, retry shortly
        setTimeout(sendCameraFramesLoop, 50);
        return;
    }

    const w = localVideo.videoWidth  || 640;
    const h = localVideo.videoHeight || 480;

    // Capture at native res (already capped at 640x480 by constraints)
    captureCanvas.width  = w;
    captureCanvas.height = h;
    captureCtx.drawImage(localVideo, 0, 0, w, h);

    _awaitingResponse = true;

    captureCanvas.toBlob((blob) => {
        if (blob && socket && socket.readyState === WebSocket.OPEN) {
            socket.send(blob);
            // The next frame will be sent when we receive the server's response
            // (see socket.onmessage above)  — this is the backpressure mechanism.
        } else {
            _awaitingResponse = false;
            setTimeout(sendCameraFramesLoop, 100);
        }
    }, 'image/jpeg', 0.50);   // 50% quality = fast encode + small payload
}

function stopCamera() {
    isCameraMode = false;
    _awaitingResponse = false;

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


// ── Video Upload ─────────────────────────────────────────────────────────────
const uploadInput        = document.getElementById('upload-input');
const uploadToast        = document.getElementById('upload-toast');
const uploadToastMsg     = document.getElementById('upload-toast-msg');
const uploadToastIcon    = document.getElementById('upload-toast-icon');
const uploadProgressFill = document.getElementById('upload-progress-fill');

if (uploadInput) {
    uploadInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        uploadInput.value = '';

        // Show toast
        if (uploadToast) uploadToast.classList.remove('hidden');
        if (uploadToastIcon) uploadToastIcon.textContent = '⬆';
        if (uploadToastMsg)  uploadToastMsg.textContent  = `Uploading "${file.name}" (${(file.size / 1048576).toFixed(1)} MB)…`;
        if (uploadProgressFill) { uploadProgressFill.style.width = '0%'; uploadProgressFill.style.background = 'var(--neon-cyan)'; }

        let fakePct = 0;
        const fakeTimer = setInterval(() => {
            fakePct = Math.min(fakePct + Math.random() * 8, 85);
            if (uploadProgressFill) uploadProgressFill.style.width = fakePct + '%';
        }, 300);

        try {
            const formData = new FormData();
            formData.append('file', file);
            const resp = await fetch('/api/upload', { method: 'POST', body: formData });
            clearInterval(fakeTimer);

            if (!resp.ok) {
                const err = await resp.json().catch(() => ({ detail: 'Upload failed' }));
                throw new Error(err.detail || `HTTP ${resp.status}`);
            }

            const data = await resp.json();
            if (uploadProgressFill) { uploadProgressFill.style.width = '100%'; uploadProgressFill.style.background = 'var(--neon-green)'; }
            if (uploadToastIcon) uploadToastIcon.textContent = '✓';
            if (uploadToastMsg)  uploadToastMsg.textContent  = data.message || 'Upload complete!';

            await refreshVideoList();
            setTimeout(() => { if (uploadToast) uploadToast.classList.add('hidden'); }, 3000);

        } catch (err) {
            clearInterval(fakeTimer);
            if (uploadProgressFill) { uploadProgressFill.style.width = '100%'; uploadProgressFill.style.background = 'var(--neon-red)'; }
            if (uploadToastIcon) uploadToastIcon.textContent = '✕';
            if (uploadToastMsg)  uploadToastMsg.textContent  = `Upload failed: ${err.message}`;
            setTimeout(() => { if (uploadToast) uploadToast.classList.add('hidden'); }, 5000);
        }
    });
}

async function refreshVideoList() {
    try {
        const resp   = await fetch('/api/videos');
        const videos = await resp.json();
        const current = videoSelect.value;
        while (videoSelect.options.length > 1) videoSelect.remove(1);
        videos.forEach(v => {
            const opt = document.createElement('option');
            opt.value = v; opt.textContent = v;
            if (v === current) opt.selected = true;
            videoSelect.appendChild(opt);
        });
        streamBtn.disabled = !videoSelect.value;
    } catch (err) {
        console.error('Failed to refresh video list:', err);
    }
}

// ── Session History Drawer Logic ─────────────────────────────────────────────
const historyDrawer = document.getElementById('history-drawer');
const historySessionsContainer = document.getElementById('history-sessions-container');
const historySessionsListView = document.getElementById('history-sessions-list-view');
const historySessionDetailsView = document.getElementById('history-session-details-view');

function toggleHistoryDrawer() {
    if (historyDrawer) {
        if (historyDrawer.classList.contains('open')) {
            closeHistoryDrawer();
        } else {
            historyDrawer.classList.add('open');
            loadHistoryData();
        }
    }
}

function closeHistoryDrawer() {
    if (historyDrawer) {
        historyDrawer.classList.remove('open');
    }
}

function showSessionsListView() {
    if (historySessionsListView) historySessionsListView.classList.remove('hidden');
    if (historySessionDetailsView) historySessionDetailsView.classList.add('hidden');
}

async function loadHistoryData() {
    showSessionsListView();
    await Promise.all([
        loadOverviewStats(),
        loadSessionsList()
    ]);
}

async function loadOverviewStats() {
    try {
        const resp = await fetch('/api/stats/overview');
        if (!resp.ok) return;
        const stats = await resp.json();

        document.getElementById('history-total-sessions').textContent = stats.total_sessions || 0;
        document.getElementById('history-avg-chaos').textContent = (stats.avg_chaos_score || 0).toFixed(1);
        document.getElementById('history-total-alerts').textContent = stats.total_alerts || 0;
        document.getElementById('history-top-class').textContent = stats.top_risk_level || 'LOW';

        const topRiskEl = document.getElementById('history-top-class');
        if (topRiskEl) {
            topRiskEl.className = 'value ' + getRiskClass(stats.top_risk_level);
        }
    } catch (err) {
        console.error('Failed to load overview stats:', err);
    }
}

function getRiskClass(lvl) {
    if (!lvl) return 'risk-low';
    const l = lvl.toUpperCase();
    if (l === 'CRITICAL') return 'text-red';
    if (l === 'HIGH') return 'text-orange';
    if (l === 'MEDIUM') return 'text-orange';
    return 'text-green';
}

async function loadSessionsList() {
    if (!historySessionsContainer) return;
    historySessionsContainer.innerHTML = '<div class="no-history-msg">Loading records...</div>';

    try {
        const resp = await fetch('/api/sessions?limit=50');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const sessions = await resp.json();

        if (sessions.length === 0) {
            historySessionsContainer.innerHTML = '<div class="no-history-msg">No recorded runs yet. Stream a video to create a session record!</div>';
            return;
        }

        historySessionsContainer.innerHTML = '';
        sessions.forEach(sess => {
            const row = document.createElement('div');
            row.className = 'session-row';

            const localDate = new Date(sess.started_at).toLocaleString();
            const riskLvl = sess.peak_risk_level || 'LOW';

            row.innerHTML = `
                <div class="session-row-info">
                    <div class="session-row-title">${sess.video_name}</div>
                    <div class="session-row-meta">
                        <span class="date">${localDate}</span>
                        <span>Frames: ${sess.total_frames}</span>
                    </div>
                    <div class="session-row-badges">
                        <span class="session-badge chaos">Avg Chaos: ${sess.avg_chaos_score}</span>
                        <span class="session-badge risk-${riskLvl.toLowerCase()}">Peak Risk: ${riskLvl}</span>
                    </div>
                </div>
                <div class="session-actions">
                    <button class="row-delete-btn" title="Delete record" data-id="${sess.id}">🗑</button>
                </div>
            `;

            // Row click to view detail
            row.addEventListener('click', (e) => {
                if (e.target.classList.contains('row-delete-btn')) {
                    e.stopPropagation();
                    deleteSessionRecord(sess.id, sess.video_name);
                } else {
                    viewSessionDetails(sess.id);
                }
            });

            historySessionsContainer.appendChild(row);
        });
    } catch (err) {
        historySessionsContainer.innerHTML = `<div class="no-history-msg">Failed to load sessions: ${err.message}</div>`;
    }
}

async function deleteSessionRecord(id, name) {
    if (!confirm(`Are you sure you want to delete session #${id} (${name}) and all its historical telemetry/alerts?`)) {
        return;
    }
    try {
        const resp = await fetch(`/api/sessions/${id}`, { method: 'DELETE' });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        await loadHistoryData();
    } catch (err) {
        alert(`Failed to delete session: ${err.message}`);
    }
}

async function viewSessionDetails(sessionId) {
    if (historySessionsListView) historySessionsListView.classList.add('hidden');
    if (historySessionDetailsView) historySessionDetailsView.classList.remove('hidden');

    // Clear details screen first
    document.getElementById('details-session-title').textContent = 'Loading Session #' + sessionId + '...';
    document.getElementById('det-started-at').textContent = '—';
    document.getElementById('det-total-frames').textContent = '—';
    document.getElementById('det-avg-fps').textContent = '—';
    document.getElementById('det-peak-risk').textContent = '—';
    document.getElementById('det-avg-chaos').textContent = '—';
    document.getElementById('det-peak-chaos').textContent = '—';
    document.getElementById('det-total-detections').textContent = '—';

    const alertsContainer = document.getElementById('details-alerts-container');
    if (alertsContainer) alertsContainer.innerHTML = '<div class="no-history-msg">Loading alerts...</div>';

    try {
        // 1. Fetch Session Details
        const sessResp = await fetch(`/api/sessions/${sessionId}`);
        if (!sessResp.ok) throw new Error(`HTTP ${sessResp.status}`);
        const sess = await sessResp.json();

        document.getElementById('details-session-title').textContent = sess.video_name;
        document.getElementById('det-started-at').textContent = new Date(sess.started_at).toLocaleString();
        document.getElementById('det-total-frames').textContent = sess.total_frames;
        document.getElementById('det-avg-fps').textContent = sess.avg_fps.toFixed(1) + ' FPS';

        const peakRiskEl = document.getElementById('det-peak-risk');
        peakRiskEl.textContent = sess.peak_risk_level;
        peakRiskEl.className = 'session-badge risk-' + sess.peak_risk_level.toLowerCase();

        document.getElementById('det-avg-chaos').textContent = sess.avg_chaos_score.toFixed(1);
        document.getElementById('det-peak-chaos').textContent = sess.max_chaos_score.toFixed(1);

        let totalDets = 0;
        if (sess.detection_summary) {
            totalDets = Object.values(sess.detection_summary).reduce((a, b) => a + b, 0);
        }
        document.getElementById('det-total-detections').textContent = totalDets;

        // 2. Fetch Timeline & draw timeline chart
        const teleResp = await fetch(`/api/sessions/${sessionId}/telemetry`);
        if (teleResp.ok) {
            const telemetry = await teleResp.json();
            drawTimelineChart(telemetry);
        }

        // 3. Fetch Alerts
        const alertsResp = await fetch(`/api/sessions/${sessionId}/alerts`);
        if (alertsResp.ok && alertsContainer) {
            const alerts = await alertsResp.json();
            if (alerts.length === 0) {
                alertsContainer.innerHTML = '<div class="no-history-msg">No alerts generated during this run.</div>';
            } else {
                alertsContainer.innerHTML = '';
                alerts.forEach(alert => {
                    const item = document.createElement('div');
                    item.className = 'detail-alert-item ' + alert.risk_level.toLowerCase();

                    const labelText = alert.label ? alert.label.replace('_', ' ').toUpperCase() : 'VEHICLE';

                    item.innerHTML = `
                        <div class="detail-alert-meta">
                            <span>Frame ${alert.frame_id} : ${labelText} #${alert.track_id}</span>
                            <span class="session-badge risk-${alert.risk_level.toLowerCase()}">${alert.risk_level}</span>
                        </div>
                        <div class="detail-alert-msg">${alert.message} (Risk: ${alert.risk_score})</div>
                    `;
                    alertsContainer.appendChild(item);
                });
            }
        }

    } catch (err) {
        document.getElementById('details-session-title').textContent = 'Error Loading Details';
        console.error('Error fetching session details:', err);
    }
}

function drawTimelineChart(telemetry) {
    const canvas = document.getElementById('chaos-timeline-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    if (telemetry.length === 0) {
        ctx.fillStyle = '#6b7a8d';
        ctx.font = '12px Space Grotesk';
        ctx.fillText('No timeline data available', w/2 - 70, h/2);
        return;
    }

    // Grid Lines (Moderate 40, Chaotic 70)
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.03)';
    ctx.lineWidth = 1;
    [0.3, 0.6, 0.9].forEach(p => {
        ctx.beginPath();
        ctx.moveTo(30, h * p);
        ctx.lineTo(w - 10, h * p);
        ctx.stroke();
    });

    // Label guidelines
    ctx.fillStyle = 'rgba(255, 255, 255, 0.2)';
    ctx.font = '9px JetBrains Mono';
    ctx.fillText('70', 10, h * 0.3 + 3);
    ctx.fillText('40', 10, h * 0.6 + 3);

    // Draw timeline line
    const paddingLeft = 35;
    const paddingRight = 15;
    const chartW = w - paddingLeft - paddingRight;
    const chartH = h - 30;
    const maxVal = 100;

    const count = telemetry.length;

    ctx.beginPath();
    telemetry.forEach((t, i) => {
        const x = paddingLeft + (i / (count - 1)) * chartW;
        const y = h - 20 - (t.chaos_score / maxVal) * chartH;

        if (i === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });

    ctx.strokeStyle = 'var(--neon-cyan)';
    ctx.lineWidth = 2;
    ctx.shadowColor = 'rgba(0, 240, 255, 0.5)';
    ctx.shadowBlur = 8;
    ctx.stroke();
    ctx.shadowBlur = 0; // reset

    // Gradient fill under the line
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, 'rgba(0, 240, 255, 0.15)');
    grad.addColorStop(1, 'rgba(0, 240, 255, 0)');

    ctx.beginPath();
    ctx.moveTo(paddingLeft, h - 20);
    telemetry.forEach((t, i) => {
        const x = paddingLeft + (i / (count - 1)) * chartW;
        const y = h - 20 - (t.chaos_score / maxVal) * chartH;
        ctx.lineTo(x, y);
    });
    ctx.lineTo(paddingLeft + chartW, h - 20);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // Draw labels at the start and end of x-axis
    ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
    ctx.fillText('Start', paddingLeft, h - 5);
    ctx.fillText('End', w - paddingRight - 20, h - 5);
}

