from __future__ import annotations

import cv2
import face_recognition
import numpy as np


class FaceMatcher:
    def __init__(self, target_image_path: str, tolerance: float = 0.45) -> None:
        self.tolerance = tolerance
        target_image = face_recognition.load_image_file(target_image_path)
        encodings = face_recognition.face_encodings(target_image)

        if not encodings:
            raise ValueError("No face found in target image. Provide a clear frontal face image.")

        self.target_encoding = encodings[0]

    def match_crop(self, bgr_crop) -> tuple[bool, float | None]:
        if bgr_crop is None or bgr_crop.size == 0:
            return False, None

        rgb_crop = cv2.cvtColor(bgr_crop, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_crop, model="hog")
        if not face_locations:
            return False, None

        encodings = face_recognition.face_encodings(rgb_crop, known_face_locations=face_locations)
        if not encodings:
            return False, None

        distances = [
            float(face_recognition.face_distance([self.target_encoding], encoding)[0])
            for encoding in encodings
        ]
        best_distance = min(distances)
        return best_distance <= self.tolerance, best_distance


class ObjectFeatureMatcher:
    def __init__(self, target_image_path: str, min_matches: int = 15) -> None:
        self.min_matches = min_matches
        self.orb = cv2.ORB_create(nfeatures=1000)
        self.bf_matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

        target_image = cv2.imread(target_image_path)
        if target_image is None:
            raise ValueError(f"Could not read target image: {target_image_path}")

        target_gray = cv2.cvtColor(target_image, cv2.COLOR_BGR2GRAY)
        self.target_keypoints, self.target_descriptors = self.orb.detectAndCompute(target_gray, None)
        if self.target_descriptors is None:
            raise ValueError("No robust features found in target image for object matching.")

    def match_crop(self, bgr_crop) -> tuple[bool, int | None]:
        if bgr_crop is None or bgr_crop.size == 0:
            return False, None

        crop_gray = cv2.cvtColor(bgr_crop, cv2.COLOR_BGR2GRAY)
        _, crop_descriptors = self.orb.detectAndCompute(crop_gray, None)
        if crop_descriptors is None:
            return False, 0

        knn_matches = self.bf_matcher.knnMatch(self.target_descriptors, crop_descriptors, k=2)
        good_matches = [m for m, n in knn_matches if m.distance < 0.75 * n.distance]
        good_count = len(good_matches)
        return good_count >= self.min_matches, good_count
