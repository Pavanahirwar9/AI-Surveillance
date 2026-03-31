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


def build_detection_message(persons: int, target_detected: bool, detection_type: str) -> dict:
    normalized_target = detection_type.lower().strip()

    result = {
        "alert": False,
        "type": "normal",
        "message": "Normal activity",
        "severity": "low"
    }

    if persons == 0:
        result.update({
            "alert": True,
            "type": "no_person",
            "message": "No person detected",
            "severity": "high"
        })
    elif persons > 1:
        result.update({
            "alert": True,
            "type": "multiple_person",
            "message": f"Multiple persons detected ({persons})",
            "severity": "high"
        })
    elif normalized_target != "person" and target_detected:
        result.update({
            "alert": True,
            "type": "target_detected",
            "message": f"Target object detected: {normalized_target}",
            "severity": "medium"
        })

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
