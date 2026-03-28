from __future__ import annotations

from typing import Iterable

from ultralytics import YOLO


class YOLODetector:
    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        conf_threshold: float = 0.35,
        iou_threshold: float = 0.5,
        device: str | None = None,
    ) -> None:
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.device = device
        self.names = self.model.model.names

    def _is_target(self, class_id: int, class_name: str, target_classes: Iterable[str | int] | None) -> bool:
        if not target_classes:
            return True

        normalized = {str(item).strip().lower() for item in target_classes}
        return str(class_id) in normalized or class_name.lower() in normalized

    def detect(self, frame, target_classes: Iterable[str | int] | None = None) -> list[dict]:
        results = self.model.predict(
            source=frame,
            verbose=False,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            device=self.device,
        )

        detections: list[dict] = []
        if not results:
            return detections

        result = results[0]
        if result.boxes is None:
            return detections

        for box in result.boxes:
            class_id = int(box.cls[0].item())
            confidence = float(box.conf[0].item())
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

            if isinstance(self.names, dict):
                class_name = str(self.names.get(class_id, class_id))
            else:
                class_name = str(self.names[class_id])

            if not self._is_target(class_id, class_name, target_classes):
                continue

            detections.append(
                {
                    "bbox": (x1, y1, x2, y2),
                    "class_id": class_id,
                    "class_name": class_name,
                    "confidence": confidence,
                }
            )

        return detections
