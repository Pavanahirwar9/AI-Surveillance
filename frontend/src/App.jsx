import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import './App.css';

const AI_API_URL = import.meta.env.VITE_AI_API_URL || 'http://localhost:8000';  
const BACKEND_API_URL = import.meta.env.VITE_BACKEND_API_URL || 'http://localhost:5000';
const FRAME_WIDTH = 320;
const FRAME_HEIGHT = 240;

export function AlertBanner({ alertState }) {
  const getSeverityClass = (severity) => {
    if (!alertState.alert) return 'banner-safe';
    if (severity === 'high') return 'banner-danger';
    if (severity === 'medium') return 'banner-warning';
    return 'banner-safe';
  };

  return (
    <div className={`alert-banner ${getSeverityClass(alertState.severity)}`}>   
      <span className="alert-dot" />
      <span>
        <strong>{alertState.alert ? 'ALERT: ' : 'STATUS: '}</strong>
        {alertState.message}
      </span>
      {alertState.time && <span className="alert-time">{alertState.time}</span>}
    </div>
  );
}

export function TimelineBar({ events }) {
  if (!events || events.length === 0) return null;

  return (
    <div className="timeline-bar-container">
      <p className="meta-row" style={{margin: '0 0 10px'}}><strong>Live Event Timeline</strong></p>
      <div className="timeline-line">
        {events.map((evt, idx) => {
          const position = events.length > 1 ? (idx / (events.length - 1)) * 100 : 50;
          return (
            <div
               key={idx}
               className={`timeline-marker marker-${evt.severity}`}
               style={{ left: `${position}%` }}
               title={`${evt.time} [ ${evt.event_type || evt.type} ]: ${evt.message}`}
               onClick={() => alert(`Time: ${evt.time}\nType: ${evt.event_type || evt.type}\nSeverity: ${evt.severity}\nMessage: ${evt.message}`)}
            ></div>
          );
        })}
      </div>
    </div>
  );
}

// ========================
// Realtime Detection Component
// ========================
function RealtimeDetection() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const detectionIntervalRef = useRef(null);

  const [isDetecting, setIsDetecting] = useState(false);
  const [detectionType, setDetectionType] = useState('person');
  const [alertState, setAlertState] = useState({ alert: false, message: 'Camera off', severity: 'low', persons: 0 });
  const [history, setHistory] = useState([]);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      videoRef.current.srcObject = stream;
      streamRef.current = stream;
      setIsDetecting(true);
      setAlertState({ alert: false, message: 'Initializing...', severity: 'low', persons: 0 });
    } catch (err) {
      console.error(err);
      alert("Please allow Camera permissions.");
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    setIsDetecting(false);
    setAlertState({ alert: false, message: 'Camera off', severity: 'low', persons: 0 });
    setHistory([]);
  };

  const captureAndDetect = async () => {
    if (!isDetecting || !videoRef.current || !canvasRef.current) return;
    
    const ctx = canvasRef.current.getContext('2d');
    ctx.drawImage(videoRef.current, 0, 0, FRAME_WIDTH, FRAME_HEIGHT);
    const dataUrl = canvasRef.current.toDataURL('image/jpeg', 0.8);
    const base64Image = dataUrl.split(',')[1];

    try {
      const response = await axios.post(`${AI_API_URL}/detect`, {
        image: base64Image,
        detectionType: detectionType,
        isProctoring: false,
        audioNoise: false
      });

      const data = response.data;
      
      setAlertState({
        alert: data.alert,
        message: data.message,
        severity: data.severity,
        persons: data.persons,
        time: data.time
      });

      if (data.alert) {
        setHistory(prev => {
          const last = prev[prev.length - 1];
          if (last && last.event_type === data.type) return prev;
          
          return [...prev, {
            time: data.time,
            event_type: data.type,
            message: data.message,
            severity: data.severity
          }].slice(-20);
        });
      }

    } catch (err) {
      console.error("AI API Error (detect):", err);
    }
  };

  useEffect(() => {
    if (isDetecting) {
      detectionIntervalRef.current = setInterval(captureAndDetect, 1500);
    } else {
      clearInterval(detectionIntervalRef.current);
    }
    return () => clearInterval(detectionIntervalRef.current);
  }, [isDetecting, detectionType]);

  return (
    <div className="workspace-grid">
      <div className="card realtime-card">
        <div className="card-header">
          <h2>Realtime Webcam Detection</h2>
          <div className="controls-row">
            <select value={detectionType} onChange={e => setDetectionType(e.target.value)} disabled={isDetecting}>
              <option value="person">Person</option>
              <option value="bottle">Bottle</option>
              <option value="car">Car</option>
              <option value="cell phone">Cell Phone</option>
            </select>
            <button onClick={isDetecting ? stopCamera : startCamera} className={isDetecting ? 'btn-danger' : 'btn-primary'}>
              {isDetecting ? 'Stop Camera' : 'Start Camera'}
            </button>
          </div>
        </div>
        
        <AlertBanner alertState={alertState} />

        <div className="video-container">
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            style={{ width: '100%', height: 'auto', backgroundColor: '#000', borderRadius: '8px' }}
          />
          <canvas
            ref={canvasRef}
            width={FRAME_WIDTH}
            height={FRAME_HEIGHT}
            style={{ display: 'none' }}
          />
        </div>
        <p className="meta-row">Persons detected: <strong>{alertState.persons || 0}</strong> | Frame interval: <strong>1.5s</strong> | Capture size: <strong>320x240</strong></p>
      </div>

      <div className="card timeline-card">
        <div className="card-header">
          <h2>Timeline & Events</h2>
          <span className="badge">History</span>
        </div>
        
        <TimelineBar events={history} />

        <div className="event-list">
          {history.length === 0 ? (
            <div className="empty-state">No recorded events</div>
          ) : (
             history.slice().reverse().map((evt, i) => (
               <div key={i} className={`event-item event-${evt.severity}`}>
                 <span className="event-time">{evt.time}</span>
                 <span className="event-type">{evt.event_type.toUpperCase()}</span>
                 <span className="event-desc">{evt.message}</span>
               </div>
             ))
          )}
        </div>
      </div>
    </div>
  );
}

// ========================
// Proctoring Component
// ========================
function ProctoringSystem() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const detectionIntervalRef = useRef(null);
  
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const audioNoiseRef = useRef(false);

  const [isDetecting, setIsDetecting] = useState(false);
  const [alertState, setAlertState] = useState({ alert: false, message: 'Proctoring off', severity: 'low', persons: 0 });
  const [history, setHistory] = useState([]);
  const [audioLevel, setAudioLevel] = useState(0);
  const [liveStats, setLiveStats] = useState({ persons: 0, objects: [], audioNoise: false });

  const startAudioMonitoring = async (stream) => {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const analyser = audioCtx.createAnalyser();
      const source = audioCtx.createMediaStreamSource(stream);
      source.connect(analyser);
      analyser.fftSize = 256;
      
      audioContextRef.current = audioCtx;
      analyserRef.current = analyser;
      
      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      
      const checkAudio = () => {
        if (!streamRef.current) return;
        analyser.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) sum += dataArray[i];
        let average = sum / bufferLength;
        
        setAudioLevel(average.toFixed(1));
        
        if (average > 30) {
          audioNoiseRef.current = true;
        } else {
          audioNoiseRef.current = false;
        }
        requestAnimationFrame(checkAudio);
      };
      checkAudio();
    } catch (err) {
      console.error("Audio block failed", err);
    }
  };

  const startProctoring = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      videoRef.current.srcObject = stream;
      streamRef.current = stream;
      setIsDetecting(true);
      setAlertState({ alert: false, message: 'Initializing Proctoring Session...', severity: 'low', persons: 0 });
      setLiveStats({ persons: 1, objects: [], audioNoise: false });
      startAudioMonitoring(stream);
    } catch (err) {
      console.error(err);
      alert("Please allow Camera and Microphone permissions for proctoring.");
    }
  };

  const stopProctoring = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    setIsDetecting(false);
    setAlertState({ alert: false, message: 'Proctoring off', severity: 'low', persons: 0 });
    setLiveStats({ persons: 0, objects: [], audioNoise: false });
    if (audioContextRef.current) {
      audioContextRef.current.close();
    }
  };

  const captureAndDetect = async () => {
    if (!isDetecting || !videoRef.current || !canvasRef.current) return;
    
    const ctx = canvasRef.current.getContext('2d');
    ctx.drawImage(videoRef.current, 0, 0, FRAME_WIDTH, FRAME_HEIGHT);
    const dataUrl = canvasRef.current.toDataURL('image/jpeg', 0.8);
    const base64Image = dataUrl.split(',')[1];
    const audioNoise = audioNoiseRef.current;

    try {
      const response = await axios.post(`${AI_API_URL}/detect`, {
        image: base64Image,
        detectionType: "person",
        isProctoring: true,
        audioNoise: audioNoise
      });

      const data = response.data;
      
      setLiveStats({
        persons: data.persons || 0,
        objects: data.objects || [],
        audioNoise: audioNoise
      });

      setAlertState({
        alert: data.alert,
        message: data.message,
        severity: data.severity,
        persons: data.persons,
        time: data.time
      });

      if (data.alert) {
        setHistory(prev => {
          const last = prev[prev.length - 1];
          if (last && last.event_type === data.type) return prev;
          
          return [...prev, {
            time: data.time,
            event_type: data.type,
            message: data.message,
            severity: data.severity
          }].slice(-20);
        });
      }

    } catch (err) {
      console.error("AI API Error (detect):", err);
    }
  };

  useEffect(() => {
    if (isDetecting) {
      detectionIntervalRef.current = setInterval(captureAndDetect, 1500);
    } else {
      clearInterval(detectionIntervalRef.current);
    }
    return () => clearInterval(detectionIntervalRef.current);
  }, [isDetecting]);

  return (
    <div className="workspace-grid">
      <div className="card realtime-card" style={{ padding: '0' }}>
        <div className="card-header" style={{ padding: '20px 20px 0' }}>
          <h2>Exam Proctoring System</h2>
          <button onClick={isDetecting ? stopProctoring : startProctoring} className={isDetecting ? 'btn-danger' : 'btn-primary'}>
            {isDetecting ? 'Stop Exam' : 'Start Exam'}
          </button>
        </div>
        
        <div style={{ padding: '0 20px' }}>
          <AlertBanner alertState={alertState} />
        </div>

        <div className="video-container" style={{ position: 'relative', margin: '0 20px', borderRadius: '8px', overflow: 'hidden' }}>
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            style={{ width: '100%', height: 'auto', backgroundColor: '#000', borderRadius: '8px' }}
          />
          <canvas
            ref={canvasRef}
            width={FRAME_WIDTH}
            height={FRAME_HEIGHT}
            style={{ display: 'none' }}
          />
          {isDetecting && (
             <div style={{ position: 'absolute', bottom: '10px', right: '10px', background: 'rgba(0,0,0,0.6)', padding: '4px 8px', color: '#fff', borderRadius: '4px', fontSize: '0.8rem' }}>
                Mic Level: {audioLevel}
             </div>
          )}
        </div>

      </div>

      <div className="card side-panel" style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '0', backgroundColor: 'transparent', boxShadow: 'none' }}>
        <div className="telemetry-panel card" style={{ margin: '0' }}>
          <h3>Live Telemetry Dashboard</h3>
          <div className="metrics-grid col-metrics" style={{ display: 'flex', flexDirection: 'column' }}>
            
            <div className={`metric-card ${!isDetecting ? '' : (liveStats.persons === 1 ? 'ok' : 'alert')}`}>
              <span className="metric-icon">👤</span>
              <div className="metric-content">
                <span className="metric-title">Face Verification</span>
                <span className="metric-value">{!isDetecting ? '--' : (liveStats.persons === 0 ? 'NO FACE' : (liveStats.persons > 1 ? 'MULTIPLE FACES' : 'VERIFIED'))}</span>
              </div>
            </div>

            <div className={`metric-card ${!isDetecting ? '' : (liveStats.objects.includes('cell phone') ? 'alert' : 'ok')}`}>
              <span className="metric-icon">📱</span>
              <div className="metric-content">
                <span className="metric-title">Mobile Device</span>
                <span className="metric-value">{!isDetecting ? '--' : (liveStats.objects.includes('cell phone') ? 'DETECTED' : 'CLEAR')}</span>
              </div>
            </div>

            <div className={`metric-card ${!isDetecting ? '' : ((liveStats.objects.includes('laptop') || liveStats.objects.includes('camera') || liveStats.objects.includes('tv')) ? 'alert' : 'ok')}`}>
              <span className="metric-icon">💻</span>
              <div className="metric-content">
                <span className="metric-title">Hardware Checks</span>
                <span className="metric-value">{!isDetecting ? '--' : ((liveStats.objects.includes('laptop') || liveStats.objects.includes('camera') || liveStats.objects.includes('tv')) ? 'VIOLATION' : 'CLEAR')}</span>
              </div>
            </div>

            <div className={`metric-card ${!isDetecting ? '' : (liveStats.audioNoise ? 'alert' : 'ok')}`}>
              <span className="metric-icon">🗣️</span>
              <div className="metric-content">
                <span className="metric-title">Voice Print</span>
                <span className="metric-value">{!isDetecting ? '--' : (liveStats.audioNoise ? 'ANOMALY DETECTED' : 'SILENT')}</span>
              </div>
            </div>

          </div>
        </div>

        <div className="card timeline-card" style={{ flexGrow: 1, margin: 0, paddingBottm: '20px' }}>
          <div className="card-header">
            <h2>Proctoring Violations Log</h2>
          <span className="badge">History</span>
        </div>
        
        <TimelineBar events={history} />

        <div className="event-list" style={{ maxHeight: 'max(400px, calc(100vh - 550px))', overflowY: 'auto' }}>
          {history.length === 0 ? (
            <div className="empty-state">No violations recorded</div>
          ) : (
             history.slice().reverse().map((evt, i) => (
               <div key={i} className={`event-item event-${evt.severity}`}>
                 <span className="event-time">{evt.time}</span>
                 <span className="event-type">{evt.event_type.toUpperCase()}</span>
                 <span className="event-desc">{evt.message}</span>
               </div>
             ))
          )}
        </div>
        </div>
      </div>
    </div>
  );
}

// ========================
// Batch Processing
// ========================
function BatchProcessing() {
  const [file, setFile] = useState(null);
  const [image, setImage] = useState(null);
  const [detectionType, setDetectionType] = useState('person');
  const [uploadStatus, setUploadStatus] = useState('');
  const [resultData, setResultData] = useState(null);
  const [uploading, setUploading] = useState(false);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file || !image) {
      alert("Please select both a video and target image file.");
      return;
    }

    const formData = new FormData();
    formData.append('video', file);
    formData.append('image', image);
    formData.append('detectionType', detectionType);

    setUploading(true);
    setUploadStatus('Uploading and processing on AI Service...');
    setResultData(null);

    try {
      const response = await axios.post(`${BACKEND_API_URL}/api/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setUploadStatus('Process Complete!');
      setResultData(response.data);
    } catch (err) {
      console.error(err);
      setUploadStatus('Error during processing. See console.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="card batch-card">
      <div className="card-header">
        <h2>Batch Video Processing</h2>
      </div>
      <p className="meta-row" style={{marginBottom: '20px'}}>Upload a pre-recorded video and target object image for deep temporal analysis.</p>

      <form onSubmit={handleUpload} className="upload-form">
        <div className="form-group">
          <label>Target Object Class</label>
          <select value={detectionType} onChange={e => setDetectionType(e.target.value)}>
            <option value="person">Person</option>
            <option value="bottle">Bottle</option>
            <option value="car">Car</option>
          </select>
        </div>

        <div className="form-group file-drop-area">
          <label>Target Reference Image</label>
          <input type="file" accept="image/*" onChange={(e) => setImage(e.target.files[0])} />
          {image && <span className="file-name">{image.name}</span>}
        </div>

        <div className="form-group file-drop-area">
          <label>Surveillance Video Input</label>
          <input type="file" accept="video/*" onChange={(e) => setFile(e.target.files[0])} />
          {file && <span className="file-name">{file.name}</span>}
        </div>

        <button type="submit" disabled={uploading || !file || !image} className={`btn-primary ${uploading ? 'loading' : ''}`} style={{width: '100%', marginTop: '10px'}}>
          {uploading ? 'Processing in AI Engine...' : 'Run Pipeline Analysis'}
        </button>
      </form>

      {uploadStatus && (
        <div className="status-message">
          <strong>Status:</strong> {uploadStatus}
        </div>
      )}

      {resultData && resultData.aiResult && (
        <div className="results-container">
           <h3>AI Processing Results</h3>
           <div className="results-grid">
               <div className="result-stat">
                  <span className="stat-value">{resultData.aiResult.matched_ids}</span>
                  <span className="stat-label">Unique Matches</span>
               </div>
               <div className="result-stat">
                  <span className="stat-value">{resultData.aiResult.timestamps.length}</span>
                  <span className="stat-label">Timestamps Found</span>
               </div>
           </div>
           
           {resultData.outputVideoUrl && (
             <div className="output-video">
               <p><strong>Processed Output File:</strong></p>
               <a href={`http://localhost:5000${resultData.outputVideoUrl}`} target="_blank" rel="noreferrer" className="download-link">
                 Download Annotated Video
               </a>
             </div>
           )}
        </div>
      )}
    </div>
  );
}

// ========================
// Main App Shell
// ========================
function App() {
  return (
    <BrowserRouter>
      <div className="app-container">
        <header className="app-header">
          <div className="logo-section">
            <div className="pulse-dot"></div>
            <h1>AI Surveillance Hub</h1>
          </div>
          <p className="subtitle">Real-time inference & batch processing engine</p>
          <nav className="main-nav">
             <Link to="/" className="nav-link">Basic Surveillance</Link>
             <Link to="/proctor" className="nav-link">Exam Proctoring</Link>
             <Link to="/batch" className="nav-link">Batch Uploads</Link>
          </nav>
        </header>

        <main className="app-main">
          <Routes>
            <Route path="/" element={<RealtimeDetection />} />
            <Route path="/proctor" element={<ProctoringSystem />} />
            <Route path="/batch" element={
              <div className="workspace-grid" style={{ gridTemplateColumns: '1fr', maxWidth: '800px', margin: '0 auto' }}>
                <BatchProcessing />
              </div>
            } />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
