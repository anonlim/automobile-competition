#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

#=============================================
# 함께 사용되는 각종 파이썬 패키지들의 import 선언부
#=============================================
import rospy, math
import cv2, time, rospy
import numpy as np
from ar_track_alvar_msgs.msg import AlvarMarkers
from tf.transformations import euler_from_quaternion
from std_msgs.msg import Int32MultiArray
from xycar_msgs.msg import xycar_motor

#=============================================
# 터미널에서 Ctrl-C 키입력으로 프로그램 실행을 끝낼 때
# 그 처리시간을 줄이기 위한 함수
#=============================================
def signal_handler(sig, frame):
    import time
    time.sleep(3)
    os.system('killall -9 python rosout')
    sys.exit(0)

#=============================================
# 프로그램에서 사용할 변수, 저장공간 선언부
#=============================================
arData = {"DX":0.0, "DY":0.0, "DZ":0.0, 
          "AX":0.0, "AY":0.0, "AZ":0.0, "AW":0.0}
roll, pitch, yaw = 0, 0, 0
motor_msg = xycar_motor()
back_drive = False
start_t, end_t = 0, 0

#=============================================
# 콜백함수 - ar_pose_marker 토픽을 처리하는 콜백함수
# ar_pose_marker 토픽이 도착하면 자동으로 호출되는 함수
# 토픽에서 AR 정보를 꺼내 arData 변수에 옮겨 담음.
#=============================================
def callback(msg):
    global arData, start_t

    for i in msg.markers:
        start_t = i.header.stamp.secs
        arData["DX"] = i.pose.pose.position.x
        arData["DY"] = i.pose.pose.position.y
        arData["DZ"] = i.pose.pose.position.z

        arData["AX"] = i.pose.pose.orientation.x
        arData["AY"] = i.pose.pose.orientation.y
        arData["AZ"] = i.pose.pose.orientation.z
        arData["AW"] = i.pose.pose.orientation.w
    

#=========================================
# ROS 노드를 생성하고 초기화 함.
# AR Tag 토픽을 구독하고 모터 토픽을 발행할 것임을 선언
#=========================================
rospy.init_node('ar_drive') # 노드 선언
rospy.Subscriber('ar_pose_marker', AlvarMarkers, callback) # 위치 정보(x,y 좌표값)와 각도 정보(yaw 좌우회전 값)가 포함되어 있는 
# 'ar_pose_marker' 데이터를 받으면(AlvarMarkers라는 class) callback 함수 실행
motor_pub = rospy.Publisher('xycar_motor', xycar_motor, queue_size =1 ) # 'xycar_motor'라는 xycar_motor class의 데이터를 publish하는 변수 선언 
motor_msg = xycar_motor()

#=========================================
# 메인 루프 
# 끊임없이 루프를 돌면서 
# "AR정보 변환처리 +차선위치찾기 +조향각결정 +모터토픽발행" 
# 작업을 반복적으로 수행함.
#=========================================
while not rospy.is_shutdown():

    x = arData["DX"]
    y = arData["DY"]
    # 쿼터니언 형식의 데이터를 오일러 형식의 데이터로 변환
    (roll,pitch,yaw)=euler_from_quaternion((arData["AX"],arData["AY"],arData["AZ"], arData["AW"]))
	
    # 라디안 형식의 데이터를 호도법(각) 형식의 데이터로 변환
    roll = math.degrees(roll)
    pitch = math.degrees(pitch)
    yaw = math.degrees(yaw)
    
    # Row 100, Column 500 크기의 배열(이미지) 준비
    img = np.zeros((100, 500, 3))

    # 4개의 직선 그리기
    img = cv2.line(img,(25,65),(475,65),(0,0,255),2)
    img = cv2.line(img,(25,40),(25,90),(0,0,255),3)
    img = cv2.line(img,(250,40),(250,90),(0,0,255),3)
    img = cv2.line(img,(475,40),(475,90),(0,0,255),3)

    # DX 값을 그림에 표시하기 위한 좌표값 계산
    point = int(arData["DX"]) + 250

    if point > 475:
        point = 475

    elif point < 25 : 
        point = 25	

    # DX값에 해당하는 위치에 동그라미 그리기 
    img = cv2.circle(img,(point,65),15,(0,255,0),-1)  
  
    # DX값과 DY값을 이용해서 거리값 distance 구하기
    distance = math.sqrt(pow(arData["DX"],2) + pow(arData["DY"],2))
    
    # 그림 위에 distance 관련된 정보를 그려넣기
    cv2.putText(img, str(int(distance))+" pixel", (350,25), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255))

    # DX값 DY값 Yaw값 구하기
    dx_dy_yaw = "DX:"+str(int(arData["DX"]))+" DY:"+str(int(arData["DY"])) \
                +" Yaw:"+ str(round(yaw,1)) 

    # 그림 위에 DX값 DY값 Yaw값 관련된 정보를 그려넣기
    cv2.putText(img, dx_dy_yaw, (20,25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255))

    # 만들어진 그림(이미지)을 모니터에 디스플레이 하기
    cv2.imshow('AR Tag Position', img)
    cv2.waitKey(1)	

    # dx, dy, yaw 값을 이용하여 angle 업데이트
    angle = math.atan2(x, y)
    yaw = math.radians(yaw) 
    angle = math.degrees(angle - yaw) * 2
    speed = 40

    # back_drive==True인 경우 뒤로 주행
    if back_drive:
        while True:
            x = arData["DX"]
            y = arData["DY"]

            # dx와 dy를 이용하여 ar태그까지의 거리값 distance 계산
            distance = math.sqrt(pow(arData["DX"],2) + pow(arData["DY"],2))

            # 앞으로 주행했을때와 반대의 각도로 뒤로 200만큼 주행
            speed = -40
            angle = -angle
            if distance > 200:
                break

            # 조향각값과 속도값을 넣어 모터 토픽을 발행하기
            motor_msg.speed = speed
            motor_msg.angle = angle
            motor_pub.publish(motor_msg)
        
        back_drive = False
        
    else: 
        # ar태그까지의 거리값(distance)이 70 이하일 경우.
        if distance < 70:
            # dx가 3 이하이며, yaw가 3 이하일 경우, 목표지점까지 주행 완료.
            if abs(x) < 3 and abs(yaw) < 3:
                angle = 0
                speed = 0
            # ar태그까지의 거리값(distance)이 70 이하이지만 목표지점까지 주행하지 못한 경우, 뒤로 후진 후 재주행.
            else:
                back_drive = True

        
    # 조향각값과 속도값을 넣어 모터 토픽을 발행하기
    motor_msg.angle = angle
    motor_msg.speed = speed
    motor_pub.publish(motor_msg)

        
# while 루프가 끝나면 열린 윈도우 모두 닫고 깔끔하게 종료하기
cv2.destroyAllWindows()