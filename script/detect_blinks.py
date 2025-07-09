from scipy.spatial import distance as dist
from collections import OrderedDict
from datetime import datetime, timedelta
import numpy as np
import time
import dlib
import cv2
import os

ear = {'value': 0}
blinks = {'value': 0}

FACIAL_LANDMARKS_68_IDXS = OrderedDict([
    ("mouth", (48, 68)),
    ("right_eyebrow", (17, 22)),
    ("left_eyebrow", (22, 27)),
    ("right_eye", (36, 42)),
    ("left_eye", (42, 48)),
    ("nose", (27, 36)),
    ("jaw", (0, 17))
])

def eye_aspect_ratio(eye):
    A = dist.euclidean(eye[1], eye[5])
    B = dist.euclidean(eye[2], eye[4])
    C = dist.euclidean(eye[0], eye[3])
    return (A + B) / (2.0 * C)

def shape_to_np(shape, dtype="int"):
    coords = np.zeros((shape.num_parts, 2), dtype=dtype)
    for i in range(shape.num_parts):
        coords[i] = (shape.part(i).x, shape.part(i).y)
    return coords

def run_blink_detection(stop_event=None, video_source=''):
    args = {
        "shape_predictor": "./script/shape_predictor_68_face_landmarks.dat",
        "video": video_source
    }

    EYE_AR_THRESH = 0.2 #判断闭眼的阈值
    EYE_AR_CONSEC_FRAMES = 12 #连续EYE_AR_CONSEC_FRAMES帧EAR低于阈值才计为一次有效眨眼
    COUNTER = 0
    TOTAL = 0

    blink_timestamps = []  # 用于记录眨眼时间戳
    last_photo_time = None
    PHOTO_COOLDOWN = 10  # 拍照冷却时间（秒）

    if not os.path.exists("captured_images"):
        os.makedirs("captured_images")

    print("[INFO] loading facial landmark predictor...")
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(args["shape_predictor"])
    (lStart, lEnd) = FACIAL_LANDMARKS_68_IDXS["left_eye"]
    (rStart, rEnd) = FACIAL_LANDMARKS_68_IDXS["right_eye"]

    print("[INFO] starting video stream...")
    vs = cv2.VideoCapture('/dev/video11' if args["video"] == "" else args["video"])
    time.sleep(1.0)
    vs.set(cv2.CAP_PROP_FRAME_WIDTH, 1056)
    vs.set(cv2.CAP_PROP_FRAME_HEIGHT, 784)

    tracker = dlib.correlation_tracker()
    tracking_face = False
    frame_count = 0
    TRACK_EVERY_N_FRAMES = 20
    rect = None

    while True:
        if stop_event and stop_event.is_set():
            break

        ret, frame = vs.read()
        if not ret:
            break

        start_time = time.time()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_count += 1

        if not tracking_face or frame_count % TRACK_EVERY_N_FRAMES == 0:
            rects = detector(gray, 0)
            if len(rects) > 0:
                rect = rects[0]
                tracker.start_track(frame, rect)
                tracking_face = True
            else:
                tracking_face = False
                rect = None
        elif tracking_face:
            tracker.update(frame)
            pos = tracker.get_position()
            rect = dlib.rectangle(int(pos.left()), int(pos.top()), int(pos.right()), int(pos.bottom()))

        if rect is not None:
            shape = predictor(gray, rect)
            shape = shape_to_np(shape)

            leftEye = shape[lStart:lEnd]
            rightEye = shape[rStart:rEnd]
            leftEAR = eye_aspect_ratio(leftEye)
            rightEAR = eye_aspect_ratio(rightEye)
            ear = (leftEAR + rightEAR) / 2.0

            if ear < EYE_AR_THRESH:
                COUNTER += 1
            else:
                if COUNTER >= EYE_AR_CONSEC_FRAMES:
                    TOTAL += 1
                    blink_timestamps.append(datetime.now())  # 添加当前眨眼时间
                COUNTER = 0

            # 保留最近60秒内的眨眼记录
            now = datetime.now()
            blink_timestamps = [t for t in blink_timestamps if now - t < timedelta(seconds=60)]

            # 检测是否需要拍照
            if len(blink_timestamps) > 8:
                if last_photo_time is None or (now - last_photo_time).total_seconds() > PHOTO_COOLDOWN:
                    filename = now.strftime("%Y-%m-%d_%H-%M-%S") + ".jpg"
                    cv2.imwrite(os.path.join("captured_images", filename), frame)
                    print(f"[INFO] Fatigue detected, photo saved as {filename}")
                    last_photo_time = now

            leftEyeHull = cv2.convexHull(leftEye)
            rightEyeHull = cv2.convexHull(rightEye)
            cv2.drawContours(frame, [leftEyeHull], -1, (0, 255, 0), 1)
            cv2.drawContours(frame, [rightEyeHull], -1, (0, 255, 0), 1)

            cv2.putText(frame, f"Blinks: {TOTAL}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.putText(frame, f"EAR: {ear:.2f}", (300, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        end_time = time.time()
        fps = 1.0 / (end_time - start_time)
        cv2.putText(frame, f"FPS: {fps:.2f}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

        cv2.imshow("Frame", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            break

    vs.release()
    cv2.destroyAllWindows()
