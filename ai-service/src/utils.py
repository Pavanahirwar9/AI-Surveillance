from __future__ import annotations

import logging
import os

import cv2


def setup_logger(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("ai_surveillance")
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def ensure_parent_dir(file_path: str) -> None:
    parent = os.path.dirname(file_path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def seconds_from_frame(frame_index: int, fps: float) -> float:
    if fps <= 0:
        return 0.0
    return frame_index / fps


def format_timestamp(seconds: float) -> str:
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{sec:06.3f}"


def draw_bbox(frame, bbox: tuple[int, int, int, int], label: str, color: tuple[int, int, int]) -> None:
    x1, y1, x2, y2 = bbox
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    text_size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
    text_width, text_height = text_size
    y_text_top = max(0, y1 - text_height - baseline - 4)

    cv2.rectangle(
        frame,
        (x1, y_text_top),
        (x1 + text_width + 6, y_text_top + text_height + baseline + 6),
        color,
        -1,
    )
    cv2.putText(
        frame,
        label,
        (x1 + 3, y_text_top + text_height + 1),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
