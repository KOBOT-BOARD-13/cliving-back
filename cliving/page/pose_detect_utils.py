import cv2
import mediapipe as mp
from django.http import JsonResponse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from datetime import datetime
from .models import Checkpoint, Video, FirstImage, Hold


def detect_pose(video):
    mp_drawing = mp.solutions.drawing_utils
    mp_pose = mp.solutions.pose

    start_checkpoints = []
    success_checkpoints = []
    failure_checkpoints = []

    is_started = False

    try:
        latest_first_image = FirstImage.objects.latest('created_at')
    except FirstImage.DoesNotExist:
        return {'error': 'No FirstImage found'}

    top_hold = Hold.objects.filter(first_image=latest_first_image, is_top=True).first()
    bottom_hold = Hold.objects.filter(first_image=latest_first_image, is_bottom=True).first()

    if not top_hold:
        x1, x2, y1, y2 = 0.4, 0.6, 0.2, 0.4
        print("'custom_error': No top hold found for the latest first image. However, we will proceed with the default values x1, x2, y1, y2 = 0.4, 0.6, 0.2, 0.4.")
    else:
        x1, x2, y1, y2 = top_hold.x1, top_hold.x2, top_hold.y1, top_hold.y2
        print("Top Hold : ", x1,y1,x2,y2)

    if not bottom_hold:
        x3, x4, y3, y4 = 0.1, 0.2, 0.1, 0.2
        print("'custom_error': No bottom hold found for the latest first image. However, we will proceed with the default values x3, x4, y3, y4 = 0.1, 0.2, 0.1, 0.2.")
    else:
        x3, x4, y3, y4 = bottom_hold.x1, bottom_hold.x2, bottom_hold.y1, bottom_hold.y2
        print("Bottom Hold : ", x3,y4,x3,y4)

    cap = cv2.VideoCapture(video.videofile.path)
    with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
        while cap.isOpened():
            success, image = cap.read()
            if not success:
                break

            # MediaPipe 포즈 탐지 수행
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = pose.process(image)

            # 두 개의 Y축 선 그리기
            # height, width, _ = image.shape
            # cv2.line(image, (0, int(height * 0.3)), (width, int(height * 0.3)), (0, 255, 0), 2)
            # cv2.line(image, (0, int(height * 0.7)), (width, int(height * 0.7)), (0, 0, 255), 2)

            # 특정 조건 확인
            if results.pose_landmarks:
                nose_y = results.pose_landmarks.landmark[mp_pose.PoseLandmark.NOSE].y

                # 스타팅 포인트 넘으면 is_started를 True로 변경
                if not is_started and nose_y < 0.3:
                    is_started = True
                    start_checkpoint = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                    start_checkpoints.append(start_checkpoint)

                # is_started가 True일 때만 실패/성공 체크
                if is_started:
                    # 특정 y축 밑으로 떨어지면 실패
                    if nose_y > 0.7:
                        failure_checkpoint = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                        failure_checkpoints.append(failure_checkpoint)
                        is_started = False  # 다음 게임을 위해 대기 상태로 전환

                    # 왼손 또는 오른손이 특정 좌표 범위에 닿으면 성공
                    left_wrist = results.pose_landmarks.landmark[mp_pose.PoseLandmark.LEFT_WRIST]
                    right_wrist = results.pose_landmarks.landmark[mp_pose.PoseLandmark.RIGHT_WRIST]

                    if (x1 < left_wrist.x < x2 and y1 < left_wrist.y < y2) or \
                            (x1 < right_wrist.x < x2 and y1 < right_wrist.y < y2):
                        success_checkpoint = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                        success_checkpoints.append(success_checkpoint)
                        is_started = False  # 다음 게임을 위해 대기 상태로 전환

    cap.release()
    #test
    # 시작점 체크포인트 저장
    for timestamp in start_checkpoints:
        Checkpoint.objects.create(
            video=video,
            time=datetime.utcfromtimestamp(timestamp).time(),
            type=0  # 시작점 체크포인트
        )

    for timestamp in success_checkpoints:
        Checkpoint.objects.create(
            video=video,
            time=datetime.utcfromtimestamp(timestamp).time(),
            type=1  # 성공 체크포인트
        )

    for timestamp in failure_checkpoints:
        Checkpoint.objects.create(
            video=video,
            time=datetime.utcfromtimestamp(timestamp).time(),
            type=2  # 실패 체크포인트
        )

    return {
        'start_checkpoints' : start_checkpoints,
        'success_checkpoints': success_checkpoints,
        'failure_checkpoints': failure_checkpoints
    }

"""
# 데이터베이스에서 좌표값 가져오기
Hold = Hold.objects.first()
if Hold:
    x1, x2 = Hold.x1, Hold.x2
    y1, y2 = Hold.y1, Hold.y2
else:
    # 좌표값이 없는 경우 기본값 설정
    x1, x2 = 0.4, 0.6
    y1, y2 = 0.2, 0.4 
"""