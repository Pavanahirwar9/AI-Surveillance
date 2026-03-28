from __future__ import annotations

from deep_sort_realtime.deepsort_tracker import DeepSort


class ObjectTracker:
    def __init__(self, max_age: int = 30, n_init: int = 3, nn_budget: int = 100) -> None:
        self.tracker = DeepSort(
            max_age=max_age,
            n_init=n_init,
            nn_budget=nn_budget,
            max_iou_distance=0.7,
        )

    def update(self, detections: list[dict], frame) -> list[dict]:
        deepsort_detections = []
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            width = max(0, x2 - x1)
            height = max(0, y2 - y1)
            if width == 0 or height == 0:
                continue

            deepsort_detections.append(
                ([x1, y1, width, height], det["confidence"], det["class_name"])
            )

        tracks = self.tracker.update_tracks(deepsort_detections, frame=frame)

        tracked_objects: list[dict] = []
        for track in tracks:
            if not track.is_confirmed():
                continue

            left, top, right, bottom = map(int, track.to_ltrb())
            tracked_objects.append(
                {
                    "track_id": int(track.track_id),
                    "bbox": (left, top, right, bottom),
                    "class_name": str(getattr(track, "det_class", "unknown")),
                    "confidence": float(getattr(track, "det_conf", 0.0) or 0.0),
                }
            )

        return tracked_objects
