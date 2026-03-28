import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import './App.css';

const AI_API_URL = import.meta.env.VITE_AI_API_URL || 'http://localhost:8000';
const BACKEND_API_URL = import.meta.env.VITE_BACKEND_API_URL || 'http://localhost:5000';
const FRAME_WIDTH = 320;
const FRAME_HEIGHT = 240;

function AlertBanner({ alertState }) {
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

function App() {
  const [detectionType, setDetectionType] = useState('person');
  const [alertState, setAlertState] = useState({ 
    message: 'Starting camera...', 
    alert: false, 
    type: 'normal',
    severity: 'low',
    persons: 0,
    time: ''
  });
  const [alertHistory, setAlertHistory] = useState([]);
  const [detections, setDetections] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const [cameraError, setCameraError] = useState('');

  const [videoFile, setVideoFile] = useState(null);
  const [imageFile, setImageFile] = useState(null);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadResults, setUploadResults] = useState(null);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const intervalRef = useRef(null);
  const audioRef = useRef(new Audio('/alert.mp3'));
  const isSendingFrameRef = useRef(false);
  const lastAlertTypeRef = useRef(null);
  const lastAlertTimeRef = useRef(0);

  const playAlertSound = () => {
    try {
      const audio = audioRef.current;
      audio.currentTime = 0;
      audio.play().catch((err) => console.log('Audio auto-play prevented by browser:', err));
    } catch (e) {
      // Ignore audio errors
    }
  };

  const fetchAlertHistory = async () => {
    try {
      const resp = await fetch(`${AI_API_URL}/alerts`);
      const data = await resp.json();
      setAlertHistory(data.alerts || []);
    } catch (e) {
      console.error("Failed to fetch alert history");
    }
  };

  // Poll for alert history every 5 seconds to sync with backend changes
  useEffect(() => {
    const histInterval = setInterval(fetchAlertHistory, 5000);
    fetchAlertHistory();
    return () => clearInterval(histInterval);
  }, []);

  const stopCamera = () => {
    if (intervalRef.current) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    setStreaming(false);
  };

  const sendFrameForDetection = async () => {
    if (!videoRef.current || !canvasRef.current || isSendingFrameRef.current) {
      return;
    }

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const context = canvas.getContext('2d');

    if (!context || video.videoWidth === 0 || video.videoHeight === 0) {
      return;
    }

    canvas.width = FRAME_WIDTH;
    canvas.height = FRAME_HEIGHT;
    context.drawImage(video, 0, 0, FRAME_WIDTH, FRAME_HEIGHT);
    const imageBase64 = canvas.toDataURL('image/jpeg', 0.75);

    isSendingFrameRef.current = true;
    try {
      const response = await fetch(`${AI_API_URL}/detect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: imageBase64, detectionType }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.message || 'Detection request failed');
      }

      setAlertState({
        message: data.message || 'Detection complete',
        alert: Boolean(data.alert),
        type: data.type || 'normal',
        severity: data.severity || 'low',
        persons: data.persons || 0,
        time: data.time || ''
      });
      setDetections(data.detections || []);
      setCameraError('');

      // Play alert sound if it's a new high-severity alert within the last 5 seconds (debounce)
      const now = Date.now();
      if (
        data.alert && 
        data.severity === 'high' && 
        (lastAlertTypeRef.current !== data.type || now - lastAlertTimeRef.current > 5000)
      ) {
        playAlertSound();
        lastAlertTypeRef.current = data.type;
        lastAlertTimeRef.current = now;
      } else if (!data.alert) {
        // Reset last alert state if things return to normal
        lastAlertTypeRef.current = null;
      }
      
    } catch (err) {
      setCameraError(err.message || 'Unable to detect objects right now.');
    } finally {
      isSendingFrameRef.current = false;
    }
  };

  const startCamera = async () => {
    try {
      stopCamera();
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });

      if (!videoRef.current) {
        return;
      }

      videoRef.current.srcObject = stream;
      streamRef.current = stream;
      setStreaming(true);
      setCameraError('');

      intervalRef.current = window.setInterval(sendFrameForDetection, 1500);
    } catch (err) {
      setCameraError('Camera access denied or not available.');
      setStreaming(false);
    }
  };

  useEffect(() => {
    startCamera();
    return () => {
      stopCamera();
    };
  }, []);

  useEffect(() => {
    if (streaming) {
      sendFrameForDetection();
    }
  }, [detectionType, streaming]);

  const handleUpload = async (event) => {
    event.preventDefault();
    if (!videoFile || !imageFile) {
      setUploadError('Please select both a location video and a target image.');
      return;
    }

    setUploadLoading(true);
    setUploadError('');
    setUploadResults(null);

    const formData = new FormData();
    formData.append('video', videoFile);
    formData.append('image', imageFile);
    formData.append('detectionType', detectionType);

    try {
      const response = await axios.post(`${BACKEND_API_URL}/api/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setUploadResults(response.data);
    } catch (err) {
      setUploadError(err.response?.data?.error || 'Upload processing failed.');
    } finally {
      setUploadLoading(false);
    }
  };

  const boxStyle = (bbox) => {
    const [x1, y1, x2, y2] = bbox;
    return {
      left: `${(x1 / FRAME_WIDTH) * 100}%`,
      top: `${(y1 / FRAME_HEIGHT) * 100}%`,
      width: `${((x2 - x1) / FRAME_WIDTH) * 100}%`,
      height: `${((y2 - y1) / FRAME_HEIGHT) * 100}%`,
    };
  };

  return (
    <div className="page-shell">
      <header className="hero-panel">
        <p className="eyebrow">Live Monitoring</p>
        <h1>AI Surveillance Command Center</h1>
        <p className="subtitle">
          Real-time webcam detection with interval-based frame analysis and alerting.
        </p>
      </header>

      <section className="workspace-grid">
        <article className="card card-primary">
          <div className="card-header">
            <h2>Realtime Webcam Detection</h2>
            <div className="actions-row">
              <select value={detectionType} onChange={(e) => setDetectionType(e.target.value)}>
                <option value="person">Person</option>
                <option value="bottle">Bottle</option>
                <option value="car">Car</option>
                <option value="backpack">Backpack</option>
              </select>
              <button className="btn-secondary" onClick={streaming ? stopCamera : startCamera}>
                {streaming ? 'Stop Camera' : 'Start Camera'}
              </button>
            </div>
          </div>

          <AlertBanner alertState={alertState} />

          <div className="video-frame">
            <video ref={videoRef} autoPlay muted playsInline className="camera-video" />
            <div className="overlay-layer">
              {detections.map((det, index) => (
                <div key={`${det.class_name}-${index}`} className="bbox" style={boxStyle(det.bbox)}>
                  <span className="bbox-label">
                    {det.class_name} {(det.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          </div>

          <canvas ref={canvasRef} className="hidden-canvas" />

          {cameraError && <p className="error-text">{cameraError}</p>}

          <p className="meta-row">
            Persons detected: <strong>{alertState.persons}</strong> | Frame interval: <strong>1.5s</strong> |
            Capture size: <strong>320x240</strong>
          </p>
        </article>

        <article className="card">
          <div className="card-header">
            <h2>Recent Security Alerts</h2>
            <span className="chip">History</span>
          </div>
          
          <div className="alert-history-list">
            {alertHistory.length === 0 ? (
              <p className="meta-row">No alerts recorded yet.</p>
            ) : (
              alertHistory.slice().reverse().map((hist, idx) => (
                <div key={idx} className={`history-item history-${hist.severity}`}>
                  <span className="history-time">{hist.time}</span>
                  <span className="history-msg">{hist.message}</span>
                </div>
              ))
            )}
          </div>
        </article>

        <article className="card">
          <div className="card-header">
            <h2>Batch Video Analysis</h2>
            <span className="chip">Existing backend pipeline</span>
          </div>

          <form onSubmit={handleUpload} className="form-grid">
            <label>
              Target Image
              <input type="file" accept="image/*" onChange={(e) => setImageFile(e.target.files?.[0] || null)} />
            </label>

            <label>
              Location Video
              <input type="file" accept="video/*" onChange={(e) => setVideoFile(e.target.files?.[0] || null)} />
            </label>

            <button type="submit" className="btn-primary" disabled={uploadLoading}>
              {uploadLoading ? 'Processing...' : 'Analyze Video'}
            </button>
          </form>

          {uploadError && <p className="error-text">{uploadError}</p>}

          {uploadResults && (
            <div className="result-box">
              <p>
                Status: <strong>{uploadResults.status || 'success'}</strong>
              </p>
              <p>
                Matches: <strong>{uploadResults.timestamps?.length || 0}</strong>
              </p>
              {uploadResults.outputVideoUrl && (
                <video controls src={`${BACKEND_API_URL}${uploadResults.outputVideoUrl}`} className="result-video" />
              )}
            </div>
          )}
        </article>
      </section>
    </div>
  );
}

export default App;
