from __future__ import annotations

import argparse
import os
import sys

import cv2

from detector import YOLODetector
from face_matcher import FaceMatcher, ObjectFeatureMatcher
from tracker import ObjectTracker
from utils import draw_bbox, ensure_parent_dir, format_timestamp, seconds_from_frame, setup_logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI-powered video surveillance search")
    parser.add_argument("--video", type=str, default="input/video.mp4", help="Input video path")
    parser.add_argument("--target", type=str, default="input/target.jpg", help="Target image path")
    parser.add_argument("--output", type=str, default="output/result.mp4", help="Output video path")
    parser.add_argument("--model", type=str, default="yolov8n.pt", help="YOLOv8 model path/name")
    parser.add_argument(
        "--object-class",
        type=str,
        default="person",
        help="Class to detect (person, car, bottle, all, etc.)",
    )
    parser.add_argument("--conf-threshold", type=float, default=0.35, help="Detection confidence threshold")
    parser.add_argument("--iou-threshold", type=float, default=0.5, help="Detection IoU threshold")
    parser.add_argument("--face-tolerance", type=float, default=0.45, help="Face distance tolerance")
    parser.add_argument("--orb-min-matches", type=int, default=15, help="Minimum ORB good matches")
    parser.add_argument("--frame-skip", type=int, default=1, help="Process every Nth frame")
    parser.add_argument("--webcam", action="store_true", help="Use webcam instead of video file")
    return parser.parse_args()


def validate_inputs(args: argparse.Namespace) -> None:
    if args.webcam:
        return

    if not os.path.exists(args.video):
        raise FileNotFoundError(f"Video file not found: {args.video}")

    if not os.path.exists(args.target):
        raise FileNotFoundError(f"Target image not found: {args.target}")


def clamp_bbox(bbox: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    x1 = max(0, min(width - 1, x1))
    y1 = max(0, min(height - 1, y1))
    x2 = max(0, min(width - 1, x2))
    y2 = max(0, min(height - 1, y2))
    if x2 <= x1:
        x2 = min(width - 1, x1 + 1)
    if y2 <= y1:
        y2 = min(height - 1, y1 + 1)
    return x1, y1, x2, y2


def build_matcher(args: argparse.Namespace):
    if args.object_class.lower() == "person":
        return FaceMatcher(args.target, tolerance=args.face_tolerance), "face"
    return ObjectFeatureMatcher(args.target, min_matches=args.orb_min_matches), "object"


def process_video(args) -> dict:
    logger = setup_logger()
    validate_inputs(args)

    cap = cv2.VideoCapture(0 if getattr(args, 'webcam', False) else args.video)
    if not cap.isOpened():
        logger.error("Unable to open input source.")
        return {"status": "error", "message": "Unable to open input source.", "timestamps": []}

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 1:
        fps = 30.0

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    ensure_parent_dir(args.output)
    writer = cv2.VideoWriter(
        args.output,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (frame_width, frame_height),
    )

    detector = YOLODetector(
        model_path=args.model,
        conf_threshold=args.conf_threshold,
        iou_threshold=args.iou_threshold,
    )
    # Only load tracking if needed later, but we use it fully.
    tracker = ObjectTracker()

    try:
        matcher, matcher_type = build_matcher(args)
    except Exception as exc:
        logger.error("Matcher initialization failed: %s", exc)
        cap.release()
        writer.release()
        return {"status": "error", "message": str(exc), "timestamps": []}

    target_classes = None if args.object_class.lower() == "all" else [args.object_class]

    frame_index = 0
    matched_track_ids: set[int] = set()
    found_timestamps: list[float] = []

    logger.info("Processing started. This may take a while depending on video length...")

    
    any_match_found = False

    while True:
        success, frame = cap.read()
        if not success:
            break

        if args.frame_skip > 1 and frame_index % args.frame_skip != 0:
            writer.write(frame)
            frame_index += 1
            continue

        detections = detector.detect(frame, target_classes=target_classes)
        tracks = tracker.update(detections, frame)

        for track in tracks:
            track_id = int(track["track_id"])
            class_name = str(track["class_name"])
            bbox = clamp_bbox(track["bbox"], frame_width, frame_height)
            x1, y1, x2, y2 = bbox
            crop = frame[y1:y2, x1:x2]

            is_match = False
            score_text = ""

            if crop is not None and crop.size > 0:
                if matcher_type == "face":
                    is_match, score = matcher.match_crop(crop)
                    if score is not None:
                        score_text = f" dist={score:.2f}"
                else:
                    is_match, score = matcher.match_crop(crop)
                    if score is not None:
                        score_text = f" kp={int(score)}"

            if is_match:
                any_match_found = True
                if track_id not in matched_track_ids:
                    matched_track_ids.add(track_id)
                    seconds = seconds_from_frame(frame_index, fps)
                    found_timestamps.append(seconds)
                    logger.info(
                        "Match found at frame %d (timestamp %.2f sec) for track ID %d",
                        frame_index,
                        seconds,
                        track_id,
                    )

            has_matched_before = track_id in matched_track_ids
            if has_matched_before:
                label = f"ID {track_id} | {class_name} | MATCH FOUND{score_text}"
                color = (0, 255, 0)
            else:
                label = f"ID {track_id} | {class_name}{score_text}"
                color = (0, 165, 255)

            draw_bbox(frame, bbox, label, color)

        frame_seconds = seconds_from_frame(frame_index, fps)
        stamp_label = f"Frame {frame_index} | {format_timestamp(frame_seconds)}"
        cv2.putText(
            frame,
            stamp_label,
            (15, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        writer.write(frame)
        frame_index += 1

    cap.release()
    writer.release()
    
    logger.info("=" * 50)
    if any_match_found:
        logger.info("RESULT: The person/object in your target image WAS FOUND in the video.")
        logger.info(f"Total unique IDs matched: {len(matched_track_ids)}")
        logger.info("Detailed Match Locations:")
        for idx, ts in enumerate(found_timestamps, 1):
            logger.info(f"  - Match #{idx} appeared at exactly: {format_timestamp(ts)}")
    else:
        logger.info("RESULT: The person/object in your target image WAS NOT FOUND in the video.")
    logger.info("=" * 50)
    
    logger.info("Processing complete. Output saved at: %s", args.output)
    return {
        "status": "success",
        "timestamps": found_timestamps,
        "matched_ids": len(matched_track_ids)
    }

def main() -> None:
    args = parse_args()
    result = process_video(args)
    if result.get("status") == "error":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
