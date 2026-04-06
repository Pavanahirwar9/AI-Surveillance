import os
import shutil
import uuid
import sys
import base64
from io import BytesIO
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
import cv2
import numpy as np
from ultralytics import YOLO
from datetime import datetime

from src.gaze_tracking import get_head_pose

# Event History Storage (In-Memory for this example)
event_history_db = []

# Add src to python path so we can import our modules
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "src"))

from src.main import process_video

app = FastAPI(title="AI Surveillance Video Processing API")


def parse_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "*")
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or ["*"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DetectRequest(BaseModel):
    image: str
    detectionType: Optional[str] = "person"
    isProctoring: Optional[bool] = False
    audioNoise: Optional[bool] = False

class ChatRequest(BaseModel):
    message: str


def get_model_path() -> str:
    local_model_path = os.path.join(current_dir, "yolov8n.pt")
    if os.path.exists(local_model_path):
        return local_model_path
    return "yolov8n.pt"


_YOLO_MODEL: Optional[YOLO] = None


def get_yolo_model() -> YOLO:
    global _YOLO_MODEL
    if _YOLO_MODEL is None:
        _YOLO_MODEL = YOLO(get_model_path())
    return _YOLO_MODEL


def decode_base64_image(image_data: str):
    if "," in image_data:
        _, image_data = image_data.split(",", 1)

    image_bytes = base64.b64decode(image_data)
    np_data = np.frombuffer(image_bytes, dtype=np.uint8)
    frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)

    if frame is None:
        raise ValueError("Invalid image payload")
    return frame


def build_proctoring_message(persons: int, detected_objects: list, audio_noise: bool, gaze_direction: str = "center") -> dict:
    result = {
        "alert": False,
        "type": "normal",
        "message": "Normal activity",
        "severity": "low"
    }

    if persons == 0:
        result.update({"alert": True, "type": "no_person", "message": "No person detected", "severity": "high"})
    elif persons > 1:
        result.update({"alert": True, "type": "multiple_person", "message": f"Multiple persons detected ({persons})", "severity": "high"})
    elif "cell phone" in detected_objects:
        result.update({"alert": True, "type": "mobile_detected", "message": "Mobile device (cell phone) detected", "severity": "high"})
    elif "laptop" in detected_objects or "camera" in detected_objects:
        result.update({"alert": True, "type": "camera_detected", "message": "Secondary camera/laptop detected", "severity": "high"})
    elif audio_noise:
        result.update({"alert": True, "type": "voice_detected", "message": "Voice/noise of another person detected", "severity": "high"})
    elif gaze_direction != "center":
        result.update({"alert": True, "type": "suspicious_gaze", "message": f"Suspicious gaze direction ({gaze_direction})", "severity": "medium"})

    return result

def build_detection_message(persons: int, target_detected: bool, detection_type: str) -> dict:
    normalized_target = detection_type.lower().strip()

    result = {
        "alert": False,
        "type": "normal",
        "message": "Normal activity",
        "severity": "low"
    }

    if persons == 0:
        result.update({"alert": True, "type": "no_person", "message": "No person detected", "severity": "high"})
    elif persons > 1:
        result.update({"alert": True, "type": "multiple_person", "message": f"Multiple persons detected ({persons})", "severity": "high"})
    elif normalized_target != "person" and target_detected:
        result.update({"alert": True, "type": "target_detected", "message": f"Target object detected: {normalized_target}", "severity": "medium"})

    return result
class ProcessArgs:
    def __init__(self, video, target, output, object_class):
        self.video = video
        self.target = target
        self.output = output
        self.object_class = object_class
        # Default configs
        self.model = "yolov8n.pt"
        self.conf_threshold = 0.35
        self.iou_threshold = 0.5
        self.face_tolerance = 0.60
        self.orb_min_matches = 15
        self.frame_skip = 5
        self.webcam = False

TEMP_DIR = os.path.join(current_dir, "temp")
os.makedirs(TEMP_DIR, exist_ok=True)


@app.get("/events")
async def get_events():
    return JSONResponse(content=event_history_db[-100:])

@app.post("/chat")
async def chat_endpoint(payload: ChatRequest):
    msg = payload.message.lower()
    
    # Rule-based simple responses
       # Rule-based simple responses
    
    # --- Greetings & Pleasantries ---
    if msg in ["hi", "hello", "hey", "greetings"]:
        reply = "Hello! I am your AI Surveillance assistant. How can I help you today?"
    elif "how are you" in msg:
        reply = "I'm operating efficiently and monitoring the system. How can I assist you?"
    elif "who are you" in msg or "what are you" in msg:
        reply = "I am the AI assistant for the Surveillance and Proctoring dashboard, here to help you monitor activity and understand system features."
    elif msg in ["bye", "goodbye", "exit"]:
        reply = "Goodbye! Stay vigilant. Let me know if you need assistance later."
    elif "thank you" in msg or "thanks" in msg:
        reply = "You're welcome! Let me know if you need anything else."
    elif "good morning" in msg:
        reply = "Good morning! The system is ready for monitoring."
    elif "good afternoon" in msg:
        reply = "Good afternoon! I'm here to assist with your proctoring needs."
    elif "good evening" in msg:
        reply = "Good evening! Monitoring is still active."
        
    # --- Core System & Status ---
    elif "status" in msg or "system check" in msg:
        reply = "The system is running smoothly. Proctoring and surveillance endpoints are active."
    elif "version" in msg:
        reply = "Currently running the latest version of the AI Surveillance framework."
    elif "uptime" in msg:
        reply = "The AI service is running and actively processing requests."
    elif "ping" in msg:
        reply = "Pong! Connections to the AI backend are stable."
    elif "dashboard" in msg:
        reply = "The dashboard provides real-time event logging, video tracking, and exam proctoring views."
    
    # --- Proctoring & Cheating Rules ---
    elif "cheating" in msg:
        reply = "Cheating is flagged when multiple people, no person, phones, secondary screens, or unauthorized audio are detected."
    elif "rules" in msg:
        reply = "Rules include: 1. Keep face visible. 2. No phones. 3. No talking. 4. No other people in the room."
    elif "phone" in msg or "mobile" in msg:
        reply = "Mobile phones are strictly prohibited during proctored sessions. If detected, an alert is triggered immediately."
    elif "multiple people" in msg or "someone else" in msg:
        reply = "Having more than one person in the camera frame is a high-severity violation."
    elif "no person" in msg or "away" in msg:
        reply = "If the user leaves the camera frame, a 'no person detected' alert is logged."
    elif "voice" in msg or "audio" in msg or "talking" in msg:
        reply = "Audio monitoring detects talking or background noise. Candidates must remain quiet."
    elif "lighting" in msg or "dark" in msg:
        reply = "Ensure the room is well-lit. Poor lighting can reduce the AI's ability to track facial features."
    elif "headphones" in msg or "earbuds" in msg:
        reply = "Headphones and earbuds are typically not allowed during proctored exams."
    elif "books" in msg or "notes" in msg:
        reply = "Browsing notes or books off-screen may trigger 'gaze tracking' or 'secondary object' alerts."
    
    # --- Hardware & Permissions ---
    elif "camera" in msg or "webcam" in msg:
        reply = "A working webcam is required. The system processes video frames locally for analysis."
    elif "microphone" in msg or "mic" in msg:
        reply = "Microphone access is used to detect unauthorized conversations or background noise."
    elif "permissions" in msg:
        reply = "Your browser must allow Camera and Microphone permissions for the proctoring to function."
    elif "resolution" in msg:
        reply = "We recommend a minimum camera resolution of 720p for accurate AI detection."
    elif "internet" in msg or "bandwidth" in msg:
        reply = "A stable internet connection is required to send frames to the AI backend seamlessly."
    
    # --- AI & Detection Capabilities ---
    elif "yolo" in msg or "model" in msg:
        reply = "The system utilizes YOLOv8 models for fast, accurate real-time object detection."
    elif "detect" in msg:
        reply = "I can detect persons, cell phones, laptops, and custom target objects depending on the mode."
    elif "face" in msg or "recognition" in msg:
        reply = "Face detection is used to ensure the authenticated user remains at the screen."
    elif "latency" in msg or "lag" in msg:
        reply = "Frames are resized to 320x240 for rapid processing, keeping latency low."
    elif "accuracy" in msg:
        reply = "The YOLO model has a base confidence threshold of 0.35 to balance speed and accuracy."
    elif "false positive" in msg:
        reply = "If you see false positives, ensure the background is clear of clutter like posters with faces on them."
    
    # --- Alerts & Notifications ---
    elif "alerts" in msg or "violation" in msg:
        if event_history_db:
            latest_alert = event_history_db[-1]
            reply = f"The latest alert is: '{latest_alert['event_type']}' - {latest_alert['message']} at {latest_alert['time']}."
        else:
            reply = "There are currently no alerts or violations recorded."
    elif "history" in msg or "past events" in msg:
        reply = f"The system holds up to 100 recent events in memory. There are currently {len(event_history_db)} events recorded."
    elif "clear alerts" in msg:
        reply = "Alerts are automatically managed in a rolling buffer. Restarting the backend will clear the history."
    elif "severity" in msg:
        reply = "Alerts are categorized into low, medium, and high severity depending on the infraction."
    elif "sound" in msg or "beep" in msg:
        reply = "The dashboard can play audio cues when a high-severity alert occurs."
        
    # --- Video Processing ---
    elif "process video" in msg or "upload" in msg:
        reply = "You can upload a video and a target image on the Video Analysis page to track a specific person over a timeline."
    elif "timeline" in msg:
        reply = "The Video Analysis output provides a timestamped timeline of when the target was detected."
    elif "frames" in msg:
        reply = "Video is processed by skipping frames to optimize performance without losing tracking data."
    elif "format" in msg:
        reply = "MP4 is the recommended video format for offline processing."
    
    # --- Privacy & Data ---
    elif "privacy" in msg or "data" in msg:
        reply = "Video frames are processed in memory and immediately discarded. Video analysis files are stored in a temporary folder and cleaned up."
    elif "recordings" in msg:
        reply = "Proctoring doesn't save complete recordings by default unless specified by your institution's configuration."
    elif "security" in msg:
        reply = "Connections should run over HTTPS to secure camera feeds and API payloads."
    elif "gdpr" in msg:
        reply = "System administrators can configure data retention policies to comply with local privacy laws."
    
    # --- Troubleshooting & Support ---
    elif "error" in msg:
        reply = "If you're seeing errors, ensure both the backend (FastAPI) and frontend (React) servers are running."
    elif "camera blocked" in msg:
        reply = "Click the lock icon in your browser's address bar to unblock camera access and refresh the page."
    elif "backend down" in msg:
        reply = "If the frontend can't connect, ensure the Python backend is running on port 8000."
    elif "slow" in msg:
        reply = "If detection is lagging, close other heavy applications. AI inference requires CPU/GPU resources."
    elif "help" in msg:
        reply = "I'm your AI Surveillance assistant. Ask me about 'status', 'rules', 'camera', 'alerts', or 'privacy'."
        
    # --- General/Fallback specific keywords ---
    elif "developer" in msg or "created" in msg:
        reply = "This dashboard was developed to combine AI computer vision with modern web technologies."
    elif "exam" in msg or "test" in msg:
        reply = "During exams, remain focused on the screen. Do not look away frequently as it may flag suspicion."
    elif "student" in msg:
        reply = "Students must comply with the setup rules: ID verification, room scan, and continuous presence."
    elif "admin" in msg:
        reply = "Admins can view real-time feeds, monitor alert histories, and configure system thresholds."
    elif "contact" in msg or "support" in msg:
        reply = "Please contact your system administrator or exam coordinator for explicit permissions or technical support."
        
    # --- Miscellaneous conversational & extra variations ---
    elif "what can you do" in msg:
        reply = "I can check system status, explain proctoring rules, report recent violations, and troubleshoot camera issues."
    elif "lol" in msg or "haha" in msg:
        reply = "Glad you're in a good mood! Let me know if you need to check the surveillance status."
    elif "joke" in msg:
        reply = "Why did the AI cross the road? To optimize its pathfinding algorithm!"
    elif "weather" in msg:
        reply = "I can only see what the webcam sees! No weather reports from me."
    elif "bored" in msg:
        reply = "Focus on your exam! Proctoring is strictly monitoring your activity."
    elif "drink" in msg or "water" in msg:
        reply = "Clear water bottles are sometimes allowed, but verify with your exam coordinator's specific rules."
    elif "bathroom" in msg or "restroom" in msg:
        reply = "Leaving the camera view to use the restroom will trigger a 'No Person Detected' alert. Check if breaks are permitted."
    elif "glasses" in msg:
        reply = "Wearing normal glasses is fine. Sunglasses or heavy glare might disrupt eye-tracking."
    elif "mask" in msg:
        reply = "Medical masks may interfere with facial recognition authentication. Follow your institution's guidelines."
    elif "hat" in msg:
        reply = "Hats and hoodies can obscure your face and may cause the AI to flag you. Please remove them during the exam."
    elif "dark mode" in msg:
        reply = "The dashboard supports visual styling. Check your browser or system preferences."
    elif "mobile app" in msg:
        reply = "This relies on web technologies and is best viewed on a desktop browser for proctoring."
    elif "api" in msg:
        reply = "The backend runs a local FastAPI server containing endpoints for /detect, /process, and /events."
    elif "cors" in msg:
        reply = "CORS is configured on the backend to accept requests from your frontend dashboard."
    elif "port" in msg:
        reply = "The backend usually runs on port 8000, and the React frontend normally on 5173 or 3000."
    elif "database" in msg:
        reply = "We are currently using an in-memory event array. It clears upon server restart."
    elif "github" in msg:
        reply = "The code resides in the AI-Surveillance repository."
    elif "python" in msg:
        reply = "The backend is powered by Python, utilizing OpenCV and Ultralytics YOLOv8."
    elif "react" in msg:
        reply = "The frontend monitoring interface is built with React."
    elif "gpu" in msg or "cuda" in msg:
        reply = "If available and configured, YOLOv8 can utilize CUDA for accelerated GPU processing."
    elif "cpu" in msg:
        reply = "The model can run on standard CPUs, though performance drops compared to a dedicated GPU."
    elif "stop" in msg:
        reply = "You can stop proctoring by toggling the switch on your dashboard to 'Off'."
    elif "start" in msg:
        reply = "Turn on the proctoring toggle to begin camera feed analysis."
    elif "refresh" in msg:
        reply = "Refreshing the page will clear your local frontend state, but backend events remain active."
    elif "update" in msg:
        reply = "Keep your browser updated to the latest version for the best camera APIs."
    elif "apple" in msg or "mac" in msg or "safari" in msg:
        reply = "On macOS, ensure Safari or Chrome has explicit System Preferences permission for the camera."
    elif "windows" in msg:
        reply = "On Windows, check your Privacy Settings to allow desktop apps to access the camera."
    elif "linux" in msg:
        reply = "Linux users generally don't have driver issues, but make sure your video group permissions are set."
    elif "dog" in msg or "cat" in msg or "pet" in msg:
        reply = "Pets wandering into the camera frame shouldn't trigger multiple-person alerts, but keep them away to avoid noise alerts."
    elif "clock" in msg or "time" in msg:
        reply = "Alerts are strictly timestamped with your local system's time."
    elif "sleep" in msg:
        reply = "If your computer goes to sleep, the video feed will halt and connections will fail."
    elif "light" in msg:
        reply = "Ensure the light source is in front of you, not behind you (backlighting), to avoid shadowy silhouettes."
    elif "id" in msg or "verification" in msg:
        reply = "Hold your ID card clearly to the camera if the proctor requires manual or automated verification."
    elif "wifi" in msg:
        reply = "Connecting via hardwired ethernet is recommended over wifi to prevent dropped frames."
    elif "vpn" in msg:
        reply = "Using a VPN may increase latency between the frontend and the local backend server."
    elif "proxy" in msg:
        reply = "Ensure your proxy settings aren't blocking local requests to port 8000."
    elif "firewall" in msg:
        reply = "Windows Defender or other firewalls shouldn't block localhost connections, but check them if API calls fail."
    elif "cache" in msg:
        reply = "Clearing browser cache is recommended if you notice stale UI components."
    elif "zoom" in msg or "teams" in msg:
        reply = "Ensure Zoom or Teams is closed so they don't lock control of your webcam."
    elif "chrome" in msg:
        reply = "Google Chrome is fully supported and recommended for WebRTC camera access."
    elif "firefox" in msg:
        reply = "Firefox is supported. Ensure you select 'Remember this decision' when granting camera access."
    elif "edge" in msg:
        reply = "Microsoft Edge is fully supported, being Chromium-based."
    elif "brave" in msg:
        reply = "Brave browser users must lower their 'Shields' to allow full API requests to the local backend."
    elif "opera" in msg:
        reply = "Opera works, but ensure gaming features (like GX Control) aren't artificially throttling the browser."
    elif "recording" in msg:
        reply = "A red indicator usually signals when the camera is being actively accessed."
    elif "screen" in msg:
        reply = "Screen sharing APIs might be enabled alongside camera APIs for full strict proctoring."
    elif "extensions" in msg:
        reply = "Disable grammar correction or ad-blocker extensions if the dashboard acts unexpectedly."
    elif "incognito" in msg:
        reply = "Incognito limits access to some local storage properties, but camera access can still be granted manually."
    elif "javascript" in msg:
        reply = "JavaScript must be enabled in your browser to run this application."
    elif "crash" in msg:
        reply = "If the tab crashes, you may be out of memory. Try closing other tabs."
    
    # --- Default fallback ---
    else:
        reply = "I understand. If you need details on specific alerts, the system status, or help with proctoring rules, just ask!"
    return JSONResponse(content={"reply": reply})

@app.post("/detect")
async def detect_realtime(payload: DetectRequest):
    try:
        frame = decode_base64_image(payload.image)
        frame = cv2.resize(frame, (320, 240), interpolation=cv2.INTER_AREA)

        model = get_yolo_model()
        result = model.predict(source=frame, verbose=False, conf=0.35)[0]

        persons = 0
        target_detected = False
        detections = []
        detected_objects = []

        names = result.names
        if result.boxes is not None:
            for box in result.boxes:
                class_id = int(box.cls[0].item())
                confidence = float(box.conf[0].item())
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                if isinstance(names, dict):
                    class_name = str(names.get(class_id, class_id))
                elif isinstance(names, list) and class_id < len(names):
                    class_name = str(names[class_id])
                else:
                    class_name = str(class_id)

                class_name_normalized = class_name.lower().strip()
                detected_objects.append(class_name_normalized)

                if class_name_normalized == "person":
                    persons += 1

                if class_name_normalized == payload.detectionType.lower().strip():
                    target_detected = True

                detections.append(
                    {
                        "class_name": class_name_normalized,
                        "confidence": round(confidence, 4),
                        "bbox": [x1, y1, x2, y2],
                    }
                )

        gaze_direction = "center"
        if payload.isProctoring:
            gaze_direction = get_head_pose(frame)
            alert_info = build_proctoring_message(persons, detected_objects, payload.audioNoise, gaze_direction)
        else:
            alert_info = build_detection_message(persons, target_detected, payload.detectionType or "person")
        timestamp = datetime.now().strftime("%H:%M:%S")

        response_data = {
            "time": timestamp,
            "alert": alert_info["alert"],
            "type": alert_info["type"],
            "message": alert_info["message"],
            "severity": alert_info["severity"],
            "persons": persons,
            "objects": list(set(detected_objects)),
            "detections": detections,
            "gaze_direction": gaze_direction,
            "frame_size": {"width": 320, "height": 240},
        }

        if alert_info["alert"]:
            # Store in history if it's an alert
            event_record = {
                "time": timestamp,
                "event_type": alert_info["type"],
                "message": alert_info["message"],
                "severity": alert_info["severity"]
            }
            # Avoid duplicate consecutive events
            if not event_history_db or event_history_db[-1]["event_type"] != alert_info["type"]:
                event_history_db.append(event_record)
            if len(event_history_db) > 100:
                event_history_db.pop(0)

        return JSONResponse(content=response_data)
    except Exception as exc:
        return JSONResponse(
            status_code=400,
            content={
                "alert": True,
                "type": "error",
                "severity": "high",
                "message": f"Detection failed: {str(exc)}",
                "persons": 0,
                "objects": [],
                "detections": [],
            },
        )

@app.post("/process")
async def process_video_endpoint(
    video: UploadFile = File(...),
    image: UploadFile = File(...),
    detectionType: str = Form("person"),
    outputPath: str = Form(...)
):
    job_id = str(uuid.uuid4())
    temp_video_path = os.path.join(TEMP_DIR, f"{job_id}_{video.filename}")
    temp_image_path = os.path.join(TEMP_DIR, f"{job_id}_{image.filename}")
    
    # Save uploaded files temporarily
    with open(temp_video_path, "wb") as buffer:
        shutil.copyfileobj(video.file, buffer)
        
    with open(temp_image_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    # Build Arguments
    args = ProcessArgs(
        video=temp_video_path,
        target=temp_image_path,
        output=outputPath,
        object_class=detectionType
    )

    try:
        # Run AI processing
        result = process_video(args)
    except Exception as e:
        result = {"status": "error", "message": str(e), "timestamps": []}
    finally:
        # Cleanup temporary input files
        if os.path.exists(temp_video_path):
            os.remove(temp_video_path)
        if os.path.exists(temp_image_path):
            os.remove(temp_image_path)

    return JSONResponse(content={
        "status": result.get("status", "success"),
        "timestamps": result.get("timestamps", []),
        "matched_ids": result.get("matched_ids", 0),
        "message": result.get("message", "")
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
