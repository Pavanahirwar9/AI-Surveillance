import cv2
import mediapipe as mp
import numpy as np

# Initialize MediaPipe Face Mesh
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
    max_num_faces=1,
    refine_landmarks=True
)

def get_head_pose(frame):
    """
    Calculates the head pose direction (center, up, down, left, right)
    using MediaPipe Face Mesh on the input frame.
    """
    # Convert the BGR image to RGB before processing
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Process the image to find faces/landmarks
    results = face_mesh.process(rgb_frame)
    
    direction = "center"
    
    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:
            img_h, img_w, _ = frame.shape
            
            face_3d = []
            for idx, lm in enumerate(face_landmarks.landmark):
                if idx in [33, 263, 1, 61, 291, 199]:  # Important landmarks for pose estimation
                    if idx == 1:
                        nose_2d = (lm.x * img_w, lm.y * img_h)
                        nose_3d = (lm.x * img_w, lm.y * img_h, lm.z * 3000)
                    
                    x, y = int(lm.x * img_w), int(lm.y * img_h)
                    face_3d.append([x, y, lm.z])

            # Get 2D and 3D Coordinates
            face_2d = np.array([
                v[:2] for v in face_3d
            ], dtype=np.float64)
            face_3d = np.array(face_3d, dtype=np.float64)
            
            # The camera matrix
            focal_length = 1 * img_w
            cam_matrix = np.array([[focal_length, 0, img_h / 2],
                                   [0, focal_length, img_w / 2],
                                   [0, 0, 1]])

            # The distortion parameters
            dist_matrix = np.zeros((4, 1), dtype=np.float64)

            # Solve PnP
            success, rot_vec, trans_vec = cv2.solvePnP(face_3d, face_2d, cam_matrix, dist_matrix)
            
            if success:
                # Get rotational matrix
                rmat, _ = cv2.Rodrigues(rot_vec)

                # Get angles
                angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)

                x = angles[0] * 360
                y = angles[1] * 360
                
                # Threshold for center bounding (e.g., +/- 15 degrees)
                THRESHOLD = 15

                if y < -THRESHOLD:
                    direction = "left"
                elif y > THRESHOLD:
                    direction = "right"
                elif x < -THRESHOLD:
                    direction = "down"
                elif x > THRESHOLD:
                    direction = "up"
                else:
                    direction = "center"
            
            break # Only process the first face for this application

    return direction
