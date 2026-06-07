// @ Con fines académicos
// por KarolyMaira

const video = document.getElementById('video');
const overlayCanvas = document.getElementById('overlayCanvas');
const overlayCtx = overlayCanvas.getContext('2d');
const videoOverlay = document.getElementById('videoOverlay');
const startCamera = document.getElementById('startCamera');
const stopCamera = document.getElementById('stopCamera');
const fileInput = document.getElementById('fileInput');
const uploadZone = document.getElementById('uploadZone');
const previewContainer = document.getElementById('previewContainer');
const previewImage = document.getElementById('previewImage');
const classifyUploadBtn = document.getElementById('classifyUploadBtn');
const changeImageBtn = document.getElementById('changeImageBtn');
const resultsPanel = document.getElementById('resultsPanel');
const annotatedContainer = document.getElementById('annotatedContainer');
const annotatedImage = document.getElementById('annotatedImage');
const detectionsBody = document.getElementById('detectionsBody');
const countAprovechable = document.getElementById('countAprovechable');
const countNoAprovechable = document.getElementById('countNoAprovechable');
const countOrganico = document.getElementById('countOrganico');
const loadingOverlay = document.getElementById('loadingOverlay');
const mainCategoryBadge = document.getElementById('mainCategoryBadge');
const mainCategoryValue = document.getElementById('mainCategoryValue');
const livePanel = document.getElementById('livePanel');
const livePersonCount = document.getElementById('livePersonCount');
const liveCountAprovechable = document.getElementById('liveCountAprovechable');
const liveCountNoAprovechable = document.getElementById('liveCountNoAprovechable');
const liveCountOrganico = document.getElementById('liveCountOrganico');
const liveMainBadge = document.getElementById('liveMainBadge');
const liveMainCategory = document.getElementById('liveMainCategory');
const liveItemsList = document.getElementById('liveItemsList');
const livePersonsList = document.getElementById('livePersonsList');
const liveItemsCount = document.getElementById('liveItemsCount');
const livePersonsCount = document.getElementById('livePersonsCount');
const snapshotFlash = document.getElementById('snapshotFlash');
const autoStatus = document.getElementById('autoStatus');
const liveContainerSection = document.getElementById('liveContainerSection');
const liveContainerList = document.getElementById('liveContainerList');
const liveValidationBadge = document.getElementById('liveValidationBadge');
const liveValidationMsg = document.getElementById('liveValidationMsg');
const faceRecognitionStatus = document.getElementById('faceRecognitionStatus');
const resultsFaceSection = document.getElementById('resultsFaceSection');
const resultsUserName = document.getElementById('resultsUserName');
const resultsUserDocument = document.getElementById('resultsUserDocument');
const resultsUserEcoPoints = document.getElementById('resultsUserEcoPoints');
const resultsUserEcoFines = document.getElementById('resultsUserEcoFines');
const resultsUserBalance = document.getElementById('resultsUserBalance');
const resultsAddEcoPoint = document.getElementById('resultsAddEcoPoint');
const resultsAddEcoFine = document.getElementById('resultsAddEcoFine');

let stream = null;
let capturedImageData = null;
let detectInterval = null;
let faceDetectInterval = null;
let faceCropCanvas = null;
let recognizedUser = null;
let lastDetectResult = null;
let isDetecting = false;
let isRecognizingFace = false;
let isClassifying = false;
let faceRecognitionFailCount = 0;
const MAX_FACE_FAILURES = 4;
let lastAutoCaptureTime = 0;
const AUTO_CAPTURE_COOLDOWN = 4000;
const DETECT_INTERVAL_MS = 800;
const FACE_RECOGNIZE_INTERVAL_MS = 2000;

const CATEGORY_CONFIG = {
    'aprovechable': { color: '#22c55e', bg: '#dcfce7', label: '\u267b Aprovechable', icon: '\u267b' },
    'no_aprovechable': { color: '#ef4444', bg: '#fee2e2', label: '\u26d4 No aprovechable', icon: '\u26d4' },
    'organico': { color: '#3b82f6', bg: '#dbeafe', label: '\u2618 Org\u00e1nico', icon: '\u2618' },
};

const CONTAINER_COLORS = {
    'verde': { stroke: '#22c55e', fill: 'rgba(34,197,94,0.2)', label: '\u{1F7E2} Caneca verde' },
    'blanca': { stroke: '#e5e7eb', fill: 'rgba(229,231,235,0.3)', label: '\u{2B1C} Caneca blanca' },
    'negra': { stroke: '#374151', fill: 'rgba(55,65,81,0.3)', label: '\u{2B1B} Caneca negra' },
};

document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
        if (btn.dataset.tab !== 'camera' && detectInterval) {
            stopLiveDetection();
        }
        resultsPanel.style.display = 'none';
    });
});

startCamera.addEventListener('click', async () => {
    try {
        stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'environment', width: 640, height: 480 }
        });
        video.srcObject = stream;
        await video.play();
        videoOverlay.style.display = 'none';

        overlayCanvas.width = video.videoWidth || 640;
        overlayCanvas.height = video.videoHeight || 480;
        overlayCanvas.style.width = '100%';
        overlayCanvas.style.height = '100%';

        startCamera.disabled = true;
        stopCamera.disabled = false;
        resultsPanel.style.display = 'none';
        livePanel.style.display = 'block';
        lastAutoCaptureTime = 0;

        startLiveDetection();
        startFaceRecognition();
    } catch (err) {
        alert('No se pudo acceder a la c\u00e1mara: ' + err.message);
    }
});

stopCamera.addEventListener('click', () => {
    stopLiveDetection();
    stopFaceRecognition();
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
    }
    video.srcObject = null;
    overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
    videoOverlay.style.display = 'flex';
    startCamera.disabled = false;
    stopCamera.disabled = true;
    livePanel.style.display = 'none';
    recognizedUser = null;
    faceRecognitionFailCount = 0;
});

if (resultsAddEcoPoint) {
    resultsAddEcoPoint.addEventListener('click', () => applyEcoAction('sumar'));
}

if (resultsAddEcoFine) {
    resultsAddEcoFine.addEventListener('click', () => applyEcoAction('restar'));
}

uploadZone.addEventListener('click', () => fileInput.click());

uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('drag-over');
});

uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('drag-over');
});

uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) handleFile(file);
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files[0]) handleFile(e.target.files[0]);
});

changeImageBtn.addEventListener('click', () => {
    previewContainer.style.display = 'none';
    uploadZone.style.display = 'block';
    resultsPanel.style.display = 'none';
    fileInput.value = '';
});

classifyUploadBtn.addEventListener('click', async () => {
    if (capturedImageData) await classifyBlob(capturedImageData, 'upload');
});

function handleFile(file) {
    capturedImageData = file;
    const reader = new FileReader();
    reader.onload = (e) => {
        previewImage.src = e.target.result;
        uploadZone.style.display = 'none';
        previewContainer.style.display = 'block';
        resultsPanel.style.display = 'none';
    };
    reader.readAsDataURL(file);
}

function startLiveDetection() {
    if (detectInterval) clearInterval(detectInterval);
    detectInterval = setInterval(captureAndDetect, DETECT_INTERVAL_MS);
}

function stopLiveDetection() {
    if (detectInterval) {
        clearInterval(detectInterval);
        detectInterval = null;
    }
    isDetecting = false;
    overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
}

async function captureAndDetect() {
    if (isDetecting || !stream) return;
    isDetecting = true;

    try {
        const cw = video.videoWidth || 640;
        const ch = video.videoHeight || 480;
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = cw;
        tempCanvas.height = ch;
        const tempCtx = tempCanvas.getContext('2d');
        tempCtx.drawImage(video, 0, 0, cw, ch);

        const base64Data = tempCanvas.toDataURL('image/jpeg', 0.7);

        const response = await fetch('/camara/detect_with_container', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: base64Data }),
        });

        if (!response.ok) throw new Error('Error en detecci\u00f3n');

        const result = await response.json();
        lastDetectResult = result;
        drawOverlay(result, cw, ch);
        updateLivePanel(result);
        tryAutoCapture(result, tempCanvas);
    } catch (err) {
        console.error('Detection error:', err);
    } finally {
        isDetecting = false;
    }
}

function showDisposalResult(validation, wasteItems, containers) {
    const el = document.getElementById('disposalResult');
    const icon = document.getElementById('disposalIcon');
    const text = document.getElementById('disposalText');
    const detail = document.getElementById('disposalDetail');

    if (!validation || validation.valid === null) {
        el.style.display = 'none';
        return;
    }

    const isValid = validation.valid;
    el.className = 'disposal-result ' + (isValid ? 'correcto' : 'incorrecto');
    icon.textContent = isValid ? '\u2705' : '\u274C';
    text.textContent = isValid ? '\u00a1Correcto!' : 'Incorrecto';

    let detailText = validation.message || '';
    if (validation.results && validation.results.length > 0) {
        const checks = validation.results[0].checks || [];
        if (checks.length > 0) {
            const wrong = checks.filter(c => !c.is_correct);
            if (wrong.length > 0) {
                detailText = wrong.map(c =>
                    '\u201c' + c.waste_class + '\u201d deber\u00eda ir en ' +
                    (c.expected_category === 'organico' ? 'caneca verde' :
                     c.expected_category === 'aprovechable' ? 'caneca blanca' : 'caneca negra')
                ).join('. ');
            } else if (isValid && checks.length > 0) {
                detailText = checks.map(c =>
                    '\u201c' + c.waste_class + '\u201d va en la caneca correcta'
                ).join(', ');
            }
        }
    }
    detail.textContent = detailText;
    el.style.display = 'flex';

    clearTimeout(window._disposalTimer);
    window._disposalTimer = setTimeout(() => {
        el.style.display = 'none';
    }, 5000);
}

function tryAutoCapture(result, rawCanvas) {
    const now = Date.now();
    const validation = result.validation;
    const hasPerson = result.total_persons > 0;
    const hasWaste = result.waste_items.length > 0;
    const hasContainer = result.containers && result.containers.length > 0;
    const isDepositing = validation && validation.valid !== null;
    const cooldownOk = now - lastAutoCaptureTime >= AUTO_CAPTURE_COOLDOWN;

    if (hasPerson && hasWaste && hasContainer && isDepositing && cooldownOk && !isClassifying) {
        isClassifying = true;
        lastAutoCaptureTime = now;
        showSnapshotFlash();

        showDisposalResult(validation, result.waste_items, result.containers);

        if (recognizedUser) {
            var action = validation.valid ? 'sumar' : 'restar';
            var containerColor = (result.containers && result.containers.length > 0) ? result.containers[0].color : '';
            var frameData = rawCanvas ? rawCanvas.toDataURL('image/jpeg', 0.7) : '';
            fetch('/camara/registrar-clasificacion', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    documento: recognizedUser.numero_documento,
                    action: action,
                    cantidad: 1,
                    waste_items: result.waste_items || [],
                    container_color: containerColor,
                    validation: validation,
                    auto_capture: true,
                    imagen: frameData,
                }),
            }).then(r => r.json()).then(data => {
                if (data.ok && data.user) {
                    recognizedUser = data.user;
                    if (resultsFaceSection.style.display !== 'none') {
                        resultsUserEcoPoints.textContent = recognizedUser.ecopuntos;
                        resultsUserEcoFines.textContent = recognizedUser.ecomultas;
                        resultsUserBalance.textContent = recognizedUser.saldo_ambiental;
                    }
                    faceRecognitionStatus.textContent = action === 'sumar'
                        ? 'Residuo clasificado correctamente. +1 ecopunto'
                        : 'Residuo clasificado incorrectamente. +1 ecomulta';
                }
            }).catch(err => console.error('Register classification error:', err));
        }

        setTimeout(() => { isClassifying = false; }, 2000);
    }
}

function showSnapshotFlash() {
    snapshotFlash.classList.remove('flash-anim');
    void snapshotFlash.offsetWidth;
    snapshotFlash.classList.add('flash-anim');
}

function drawOverlay(result, imgW, imgH) {
    const rect = video.getBoundingClientRect();
    overlayCanvas.width = rect.width;
    overlayCanvas.height = rect.height;
    overlayCanvas.style.width = rect.width + 'px';
    overlayCanvas.style.height = rect.height + 'px';

    overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

    const scaleX = overlayCanvas.width / imgW;
    const scaleY = overlayCanvas.height / imgH;

    const allItems = [
        ...result.persons.map(p => ({ ...p, isPerson: true })),
        ...result.waste_items.map(w => ({ ...w, isPerson: false })),
    ];

    for (const item of allItems) {
        const [x1, y1, x2, y2] = item.bbox;
        const rx = x1 * scaleX;
        const ry = y1 * scaleY;
        const rw = (x2 - x1) * scaleX;
        const rh = (y2 - y1) * scaleY;

        let color, label;
        if (item.isPerson) {
            color = '#a855f7';
            label = `Persona ${Math.round(item.confidence * 100)}%`;
        } else {
            color = CATEGORY_CONFIG[item.category]?.color || '#6b7280';
            const icon = CATEGORY_CONFIG[item.category]?.icon || '';
            label = `${item.class} ${icon} ${Math.round(item.confidence * 100)}%`;
        }

        overlayCtx.strokeStyle = color;
        overlayCtx.lineWidth = 3;
        overlayCtx.strokeRect(rx, ry, rw, rh);

        const textMetrics = overlayCtx.measureText(label);
        const textPad = 6;
        const textW = textMetrics.width + textPad * 2;
        const textH = 24;

        overlayCtx.fillStyle = color;
        overlayCtx.beginPath();
        overlayCtx.roundRect(rx, ry - textH, textW, textH, [4, 4, 0, 0]);
        overlayCtx.fill();

        overlayCtx.fillStyle = '#ffffff';
        overlayCtx.font = 'bold 13px Inter, sans-serif';
        overlayCtx.textBaseline = 'middle';
        overlayCtx.fillText(label, rx + textPad, ry - textH / 2);
    }

    if (result.containers) {
        for (const c of result.containers) {
            const [x1, y1, x2, y2] = c.bbox;
            const rx = x1 * scaleX;
            const ry = y1 * scaleY;
            const rw = (x2 - x1) * scaleX;
            const rh = (y2 - y1) * scaleY;

            const cfg = CONTAINER_COLORS[c.color] || { stroke: '#6b7280', fill: 'rgba(107,114,128,0.2)', label: c.label };

            overlayCtx.fillStyle = cfg.fill;
            overlayCtx.fillRect(rx, ry, rw, rh);

            overlayCtx.strokeStyle = cfg.stroke;
            overlayCtx.lineWidth = 4;
            overlayCtx.setLineDash([8, 4]);
            overlayCtx.strokeRect(rx, ry, rw, rh);
            overlayCtx.setLineDash([]);

            const label2 = `${cfg.label} ${Math.round(c.confidence * 100)}%`;
            overlayCtx.fillStyle = cfg.stroke;
            overlayCtx.font = 'bold 12px Inter, sans-serif';
            const tw = overlayCtx.measureText(label2).width + 12;
            overlayCtx.beginPath();
            overlayCtx.roundRect(rx, ry - 22, tw, 22, [4, 4, 0, 0]);
            overlayCtx.fill();

            overlayCtx.fillStyle = '#ffffff';
            overlayCtx.fillText(label2, rx + 6, ry - 6);
        }
    }
}

function updateLivePanel(result) {
    livePersonCount.textContent = result.total_persons || 0;
    liveCountAprovechable.textContent = result.categories_count.aprovechable;
    liveCountNoAprovechable.textContent = result.categories_count.no_aprovechable;
    liveCountOrganico.textContent = result.categories_count.organico;

    if (result.main_category) {
        liveMainBadge.style.display = 'flex';
        const cfg = CATEGORY_CONFIG[result.main_category];
        liveMainCategory.textContent = cfg.label;
        liveMainCategory.style.background = cfg.color;
    } else {
        liveMainBadge.style.display = 'none';
    }

    liveItemsList.innerHTML = '';
    liveItemsCount.textContent = result.waste_items.length;
    if (result.waste_items.length > 0) {
        result.waste_items.forEach(w => {
            const cfg = CATEGORY_CONFIG[w.category] || {};
            const div = document.createElement('div');
            div.className = 'live-item-row';
            div.innerHTML = `
                <span class="live-item-class">${w.class}</span>
                <span class="live-item-cat" style="background:${cfg.bg};color:${cfg.color}">${cfg.icon} ${cfg.label || w.category_label}</span>
                <span class="live-item-conf">${Math.round(w.confidence * 100)}%</span>
            `;
            liveItemsList.appendChild(div);
        });
    } else {
        liveItemsList.innerHTML = '<div class="live-empty">No se detectaron residuos</div>';
    }

    livePersonsList.innerHTML = '';
    livePersonsCount.textContent = result.persons.length;
    if (result.persons.length > 0) {
        result.persons.forEach((p, i) => {
            const div = document.createElement('div');
            div.className = 'live-person-row';
            div.innerHTML = `
                <span class="person-icon">&#128100;</span>
                <span>Persona ${i + 1}</span>
                <span class="live-item-conf">${Math.round(p.confidence * 100)}%</span>
            `;
            livePersonsList.appendChild(div);
        });
    } else {
        livePersonsList.innerHTML = '<div class="live-empty">No se detectaron personas</div>';
    }

    const hasContainer = result.containers && result.containers.length > 0;
    liveContainerSection.style.display = hasContainer ? 'block' : 'none';
    liveContainerList.innerHTML = '';
    if (hasContainer) {
        result.containers.forEach(c => {
            const cfg = CONTAINER_COLORS[c.color] || {};
            const div = document.createElement('div');
            div.className = 'live-item-row';
            div.innerHTML = `
                <span class="live-item-class">${cfg.label || c.label}</span>
                <span class="live-item-cat" style="background:${cfg.fill || '#f3f4f6'};color:${cfg.stroke || '#374151'}">${c.expected_category === 'organico' ? '\u2618 Org\u00e1nico' : c.expected_category === 'aprovechable' ? '\u267b Aprovechable' : '\u26d4 No aprovech.'}</span>
                <span class="live-item-conf">${Math.round(c.confidence * 100)}%</span>
            `;
            liveContainerList.appendChild(div);
        });
    }

    if (result.validation && result.validation.valid !== null) {
        liveValidationBadge.style.display = 'flex';
        const isValid = result.validation.valid;
        liveValidationMsg.textContent = result.validation.message;
        liveValidationBadge.className = 'validation-badge ' + (isValid ? 'valid' : 'invalid');
        liveValidationMsg.className = 'validation-msg ' + (isValid ? 'valid' : 'invalid');
    } else {
        liveValidationBadge.style.display = 'none';
    }

    let statusMsg = '';
    if (result.total_persons > 0 && result.waste_items.length > 0 && hasContainer) {
        statusMsg = '\u231B Verificando disposici\u00f3n...';
    } else if (!hasContainer) {
        statusMsg = '\u{1FAA3} Buscando caneca...';
    } else if (result.total_persons === 0) {
        statusMsg = '\u{1F464} Espere a que aparezca una persona';
    } else if (result.waste_items.length === 0) {
        statusMsg = '\u{1F4E6} Espere residuo para clasificar';
    }
    if (statusMsg) {
        autoStatus.textContent = statusMsg;
        autoStatus.style.display = 'inline';
    } else {
        autoStatus.style.display = 'none';
    }
}

async function classifyBlob(blob, source) {
    loadingOverlay.style.display = 'flex';
    try {
        const formData = new FormData();
        formData.append('image', blob, `${source}.jpg`);
        const response = await fetch('/camara/classify', { method: 'POST', body: formData });
        if (!response.ok) throw new Error('Error en la clasificaci\u00f3n');
        const result = await response.json();
        displayResults(result);
    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        loadingOverlay.style.display = 'none';
    }
}

var lastEvidencePath = null;

function displayResults(result) {
    resultsPanel.style.display = 'block';
    resultsPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });

    if (recognizedUser) {
        resultsFaceSection.style.display = 'block';
        resultsUserName.textContent = `${recognizedUser.nombres} ${recognizedUser.apellidos}`;
        resultsUserDocument.textContent = `Documento: ${recognizedUser.numero_documento}`;
        resultsUserEcoPoints.textContent = recognizedUser.ecopuntos;
        resultsUserEcoFines.textContent = recognizedUser.ecomultas;
        resultsUserBalance.textContent = recognizedUser.saldo_ambiental;
    } else {
        resultsFaceSection.style.display = 'none';
    }

    countAprovechable.textContent = result.categories_count.aprovechable;
    countNoAprovechable.textContent = result.categories_count.no_aprovechable;
    countOrganico.textContent = result.categories_count.organico;

    if (result.main_category) {
        mainCategoryBadge.style.display = 'flex';
        const cfg = CATEGORY_CONFIG[result.main_category];
        mainCategoryValue.textContent = cfg ? cfg.label : result.main_category;
        mainCategoryValue.style.background = cfg ? cfg.color : '#6b7280';
    } else {
        mainCategoryBadge.style.display = 'none';
    }

    lastEvidencePath = result.evidence_path || null;

    if (result.annotated_image) {
        annotatedContainer.style.display = 'block';
        annotatedImage.src = `data:image/jpeg;base64,${result.annotated_image}`;
    } else {
        annotatedContainer.style.display = 'none';
    }

    detectionsBody.innerHTML = '';
    if (result.detections.length > 0) {
        result.detections.forEach(d => {
            const tr = document.createElement('tr');
            const cfg = CATEGORY_CONFIG[d.category] || {};
            const catLabel = cfg.label || d.category_label;
            tr.innerHTML = `
                <td><strong>${d.class}</strong></td>
                <td><span class="category-tag ${d.category}">${catLabel}</span></td>
                <td>
                    <div class="confidence-bar">
                        <div class="confidence-fill" style="width:${d.confidence * 100}%;background:${cfg.color || '#22c55e'}"></div>
                        <span class="confidence-text">${Math.round(d.confidence * 100)}%</span>
                    </div>
                </td>
            `;
            detectionsBody.appendChild(tr);
        });
    } else {
        detectionsBody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:var(--gray-400);padding:24px;">No se detectaron objetos</td></tr>';
    }
}

function startFaceRecognition() {
    if (faceDetectInterval) clearInterval(faceDetectInterval);
    if (!faceCropCanvas) {
        faceCropCanvas = document.createElement('canvas');
        faceCropCanvas.width = 224;
        faceCropCanvas.height = 224;
    }

    fetch('/camara/modelo-facial').then(r => r.json()).then(status => {
        if (!status.available) {
            faceRecognitionStatus.textContent = 'Reconocimiento facial no disponible.';
            return;
        }
        faceRecognitionStatus.textContent = 'Reconocimiento facial activo.';
        faceDetectInterval = setInterval(recognizeFaceFromVideo, FACE_RECOGNIZE_INTERVAL_MS);
    }).catch(() => {
        faceRecognitionStatus.textContent = 'Error al verificar reconocimiento facial.';
    });
}

function stopFaceRecognition() {
    if (faceDetectInterval) {
        clearInterval(faceDetectInterval);
        faceDetectInterval = null;
    }
    isRecognizingFace = false;
}

function cropFaceRegion() {
    const vw = video.videoWidth || 640;
    const vh = video.videoHeight || 480;
    if (vw <= 0 || vh <= 0) return null;
    const ctx = faceCropCanvas.getContext('2d');
    ctx.clearRect(0, 0, 224, 224);
    const scale = Math.min(224 / vw, 224 / vh);
    const dw = Math.round(vw * scale);
    const dh = Math.round(vh * scale);
    const dx = Math.floor((224 - dw) / 2);
    const dy = Math.floor((224 - dh) / 2);
    ctx.drawImage(video, 0, 0, vw, vh, dx, dy, dw, dh);
    return faceCropCanvas.toDataURL('image/jpeg', 0.8);
}

async function recognizeFaceFromVideo() {
    if (isRecognizingFace || !stream) return;
    isRecognizingFace = true;

    try {
        const imageData = cropFaceRegion();
        if (!imageData) {
            faceRecognitionStatus.textContent = 'Buscando rostro...';
            return;
        }

        const response = await fetch('/camara/reconocer-rostro', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: imageData }),
        });

        const data = await response.json();
        if (!response.ok || !data.ok) {
            faceRecognitionFailCount++;
            if (recognizedUser && faceRecognitionFailCount >= MAX_FACE_FAILURES) {
                recognizedUser = null;
                faceRecognitionStatus.textContent = 'Buscando rostro registrado...';
            } else if (!recognizedUser && faceRecognitionStatus.textContent !== 'Buscando rostro...') {
                faceRecognitionStatus.textContent = 'Buscando rostro registrado...';
            }
            return;
        }

        faceRecognitionFailCount = 0;

        if (recognizedUser && recognizedUser.numero_documento === data.user.numero_documento) return;

        recognizedUser = data.user;
        resultsFaceSection.style.display = 'block';
        resultsUserName.textContent = `${recognizedUser.nombres} ${recognizedUser.apellidos}`;
        resultsUserDocument.textContent = `Documento: ${recognizedUser.numero_documento}`;
        resultsUserEcoPoints.textContent = recognizedUser.ecopuntos;
        resultsUserEcoFines.textContent = recognizedUser.ecomultas;
        resultsUserBalance.textContent = recognizedUser.saldo_ambiental;
        faceRecognitionStatus.textContent = `Usuario: ${recognizedUser.nombres} ${recognizedUser.apellidos} (${Math.round(data.confidence * 100)}%)`;
    } catch (error) {
        console.error('Face recognition error:', error);
        faceRecognitionFailCount++;
    } finally {
        isRecognizingFace = false;
    }
}

async function applyEcoAction(action) {
    if (!recognizedUser) {
        alert('Primero debes ser reconocido facialmente.');
        return;
    }

    try {
        const response = await fetch('/camara/ecoaccion', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                documento: recognizedUser.numero_documento,
                accion: action,
                cantidad: 1,
            }),
        });
        const data = await response.json();
        if (!response.ok || !data.ok) {
            throw new Error(data.error || 'No fue posible actualizar el puntaje.');
        }
        recognizedUser = data.user;
        resultsUserEcoPoints.textContent = recognizedUser.ecopuntos;
        resultsUserEcoFines.textContent = recognizedUser.ecomultas;
        resultsUserBalance.textContent = recognizedUser.saldo_ambiental;
        faceRecognitionStatus.textContent = action === 'sumar'
            ? 'Ecopunto agregado correctamente.'
            : 'Ecomulta registrada correctamente.';
    } catch (error) {
        alert(error.message);
    }
}
