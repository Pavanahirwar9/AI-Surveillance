# AI-Surveillance Full-Stack System

A complete production-ready full-stack AI surveillance system that integrates a React frontend, Node.js backend, and a Python-based AI processing service.

## 🧱 Architecture
- **frontend/**: React app with two modes:
  - Realtime webcam detection (browser `getUserMedia` + interval frame capture + `/detect` API)
  - Batch video upload pipeline (existing flow through backend `/api/upload`)
- **backend/**: Express.js API for batch uploads. Forwards videos/images to the Python AI service and serves output files.
- **ai-service/**: FastAPI service with YOLOv8 inference:
  - `/detect` for realtime base64 frame detection
  - `/process` for batch video processing

## 🚀 How to Run Locally

To run the full stack, you need to open **3 separate terminal windows**.

### Terminal 1: Python AI Service
```bash
cd "C:\Users\princ\Desktop\ai survilence system\AI-Surveillance\ai-service"

# Activate your python virtual environment if you use one
# ..\.venv311\Scripts\activate

pip install -r requirements.txt
python app.py
```
*Runs on http://localhost:8000*

### Terminal 2: Node Backend
```bash
cd "C:\Users\princ\Desktop\ai survilence system\AI-Surveillance\backend"
npm install
npm start
```
*Runs on http://localhost:5000*

### Terminal 3: React Frontend
```bash
cd "C:\Users\princ\Desktop\ai survilence system\AI-Surveillance\frontend"
npm install

# Optional: set API URLs for frontend runtime
# set VITE_AI_API_URL=http://localhost:8000
# set VITE_BACKEND_API_URL=http://localhost:5000

npm run dev
```
*Runs on http://localhost:5173* (or similar). Open this in your browser!

---

## 📥 API Documentation

### POST `/detect` (AI-Service, Realtime Webcam)
Accepts JSON:
- `image`: Base64 data URL (JPEG/PNG)
- `detectionType`: String (`person`, `bottle`, `car`, etc.)

Returns:
```json
{
  "alert": true,
  "message": "Multiple persons detected",
  "persons": 2,
  "target": "person",
  "detections": [
    { "class_name": "person", "confidence": 0.88, "bbox": [44, 30, 170, 220] }
  ],
  "frame_size": { "width": 320, "height": 240 }
}
```

Detection logic:
- 0 persons -> `alert: true`, message `No person detected`
- more than 1 person -> `alert: true`, message `Multiple persons detected`
- exactly 1 person -> `alert: false`, message `Single person detected - normal`

### POST `/api/upload` (Backend)
Accepts `multipart/form-data`:
- `video`: File (mp4/avi)
- `image`: File (jpg/png)
- `detectionType`: String ("person", "bottle", etc.)

### POST `/process` (AI-Service)
Accepts `multipart/form-data`:
- `video`: File (local temp file)
- `image`: File (local temp file)
- `detectionType`: String
- `outputPath`: String (Where the node app wants the final injected video saved)

Returns:
```json
{
  "status": "success",
  "timestamps": [10.5, 14.2],
  "matched_ids": 2
}
```

---

## 📁 Feature-Oriented Folder Structure

```text
AI-Surveillance/
  ai-service/
    app.py                # FastAPI routes: /detect and /process
    requirements.txt      # Includes opencv-python-headless for deployment
    yolov8n.pt            # YOLOv8 model file
    src/                  # Existing video tracking pipeline modules

  backend/
    server.js             # Batch upload API /api/upload

  frontend/
    src/App.jsx           # Realtime webcam + batch upload UI
    src/App.css           # Modern responsive UI styles
```

## ☁️ Render Deployment Notes

- Frontend should set:
  - `VITE_AI_API_URL` = public URL of ai-service
  - `VITE_BACKEND_API_URL` = public URL of backend
- AI service should run with:
  - `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Keep `yolov8n.pt` in `ai-service/` (or provide persistent model path).
- This implementation uses browser webcam only; backend does **not** use `cv2.VideoCapture(0)`.