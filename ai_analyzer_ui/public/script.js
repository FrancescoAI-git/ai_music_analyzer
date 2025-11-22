// Initialize Wavesurfer
let wavesurfer;
let wsRegions;
let audioFile = null;

document.addEventListener('DOMContentLoaded', () => {
    initWavesurfer();
    setupEventListeners();
});

function initWavesurfer() {
    wavesurfer = WaveSurfer.create({
        container: '#waveform',
        waveColor: '#4b5563',
        progressColor: '#6366f1',
        cursorColor: '#818cf8',
        barWidth: 2,
        barGap: 3,
        barRadius: 3,
        height: 128,
        normalize: true,
        minPxPerSec: 50,
        plugins: [
            WaveSurfer.Regions.create()
        ]
    });

    wsRegions = wavesurfer.registerPlugin(WaveSurfer.Regions.create());

    // Update time display on audioprocess
    wavesurfer.on('audioprocess', () => {
        updateTimeDisplay();
    });

    // Update time display on seek
    wavesurfer.on('seek', () => {
        updateTimeDisplay();
    });

    // Enable/Disable controls on ready
    wavesurfer.on('ready', () => {
        document.getElementById('playPauseBtn').disabled = false;
        document.getElementById('stopBtn').disabled = false;
        document.getElementById('zoomSlider').disabled = false;
        document.getElementById('analyzeBtn').disabled = false;
        
        // Create a default region if none exists
        wsRegions.clearRegions();
        const duration = wavesurfer.getDuration();
        wsRegions.addRegion({
            start: 0,
            end: Math.min(duration, 30), // Default 30s or full track
            color: 'rgba(99, 102, 241, 0.2)',
            drag: true,
            resize: true
        });
        
        updateRegionInfo(0, Math.min(duration, 30));
    });

    // Region updates
    wsRegions.on('region-updated', (region) => {
        updateRegionInfo(region.start, region.end);
    });

    wsRegions.on('region-created', (region) => {
        // Ensure only one region exists (optional, but good for this use case)
        const regions = wsRegions.getRegions();
        if (regions.length > 1) {
            regions[0].remove();
        }
        updateRegionInfo(region.start, region.end);
    });
}

function setupEventListeners() {
    // File Upload
    const dropArea = document.getElementById('dropArea');
    const fileInput = document.getElementById('audioFileInput');

    dropArea.addEventListener('click', () => fileInput.click());

    dropArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropArea.classList.add('dragover');
    });

    dropArea.addEventListener('dragleave', () => {
        dropArea.classList.remove('dragover');
    });

    dropArea.addEventListener('drop', (e) => {
        e.preventDefault();
        dropArea.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileUpload(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    // Transport Controls
    document.getElementById('playPauseBtn').addEventListener('click', () => {
        wavesurfer.playPause();
        updatePlayButton();
    });

    wavesurfer.on('play', updatePlayButton);
    wavesurfer.on('pause', updatePlayButton);

    document.getElementById('stopBtn').addEventListener('click', () => {
        wavesurfer.stop();
        updatePlayButton();
    });

    // Zoom
    document.getElementById('zoomSlider').addEventListener('input', (e) => {
        wavesurfer.zoom(Number(e.target.value));
    });

    // Analyze
    document.getElementById('analyzeBtn').addEventListener('click', performAnalysis);
}

function handleFileUpload(file) {
    if (!file.type.startsWith('audio/')) {
        alert('Please upload an audio file.');
        return;
    }
    
    audioFile = file;
    const objectUrl = URL.createObjectURL(file);
    wavesurfer.load(objectUrl);
    
    // Update status
    document.getElementById('statusBadge').textContent = 'Track Loaded';
    document.getElementById('statusBadge').style.color = '#6366f1';
    document.getElementById('statusBadge').style.borderColor = 'rgba(99, 102, 241, 0.2)';
    document.getElementById('statusBadge').style.background = 'rgba(99, 102, 241, 0.1)';
}

function updatePlayButton() {
    const btn = document.getElementById('playPauseBtn');
    const icon = btn.querySelector('i');
    if (wavesurfer.isPlaying()) {
        icon.className = 'fa-solid fa-pause';
    } else {
        icon.className = 'fa-solid fa-play';
    }
}

function updateTimeDisplay() {
    const current = formatTime(wavesurfer.getCurrentTime());
    const total = formatTime(wavesurfer.getDuration());
    document.getElementById('timeDisplay').textContent = `${current} / ${total}`;
}

function formatTime(seconds) {
    const min = Math.floor(seconds / 60);
    const sec = Math.floor(seconds % 60);
    return `${min}:${sec.toString().padStart(2, '0')}`;
}

function updateRegionInfo(start, end) {
    document.getElementById('regionStart').textContent = start.toFixed(2) + 's';
    document.getElementById('regionEnd').textContent = end.toFixed(2) + 's';
    document.getElementById('regionDuration').textContent = (end - start).toFixed(2) + 's';
}

async function performAnalysis() {
    if (!audioFile) return;

    const regions = wsRegions.getRegions();
    let start = 0;
    let end = wavesurfer.getDuration();

    if (regions.length > 0) {
        start = regions[0].start;
        end = regions[0].end;
    }

    // UI Loading State
    document.getElementById('loadingOverlay').style.display = 'flex';
    document.getElementById('resultsContainer').style.display = 'none';

    const formData = new FormData();
    formData.append('file', audioFile);
    formData.append('trim_start', start);
    formData.append('trim_end', end);

    try {
        // Assuming backend is running on port 8000
        const response = await fetch('http://localhost:8000/analyze', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Analysis failed');
        }

        const data = await response.json();
        displayResults(data);

    } catch (error) {
        console.error('Error:', error);
        alert('Analysis failed. Make sure the backend server is running on port 8000.');
    } finally {
        document.getElementById('loadingOverlay').style.display = 'none';
    }
}

function displayResults(data) {
    document.getElementById('resultsContainer').style.display = 'flex';
    
    // Helper to render markdown-like text (simple replacement for bold/headers)
    const renderMD = (text) => {
        if (!text) return 'No data';
        return text
            .replace(/### (.*)/g, '<h3>$1</h3>')
            .replace(/\*\*(.*)\*\*/g, '<strong>$1</strong>')
            .replace(/- (.*)/g, '<li>$1</li>');
    };

    document.getElementById('resultGenre').textContent = data.genre || 'Unknown';
    
    document.getElementById('resultMix').innerHTML = renderMD(data.mix_agent);
    document.getElementById('resultTheory').innerHTML = renderMD(data.theory_agent);
    document.getElementById('resultCreative').innerHTML = renderMD(data.creative_agent);
    document.getElementById('resultPlan').innerHTML = renderMD(data.final_plan);

    // Scroll to results
    document.getElementById('resultsContainer').scrollIntoView({ behavior: 'smooth' });
}
