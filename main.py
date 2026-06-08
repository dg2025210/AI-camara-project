import time
from machine import I2C, Pin
import neopixel
import math

# ==========================================
# 0. 개발용 테스트 설정
# ==========================================
TEST_MODE_ANY_OBJECT = True 
PERSON_ID = 1

# ==========================================
# 1. 하드웨어 및 네오픽셀 설정 (GP16, I2C1 사용)
# ==========================================
NUM_LEDS = 8
NEO_PIN = 16  
np = neopixel.NeoPixel(Pin(NEO_PIN), NUM_LEDS)

# I2C1 설정 (SDA=GP6, SCL=GP7)
i2c_bus = I2C(1, sda=Pin(6), scl=Pin(7), freq=100000)

# ==========================================
# 2. 허스키렌즈 초정밀 동적 I2C 통신 클래스
# ==========================================
class HuskyLensI2C:
    def __init__(self, i2c_bus, address=0x32):
        self.i2c = i2c_bus
        self.address = address
        
    def get_blocks(self):
        cmd = bytearray([0x55, 0xAA, 0x11, 0x00, 0x20, 0x30])
        try:
            self.i2c.writeto(self.address, cmd)
            time.sleep_ms(20)
            
            info_header = self.i2c.readfrom(self.address, 5)
            if len(info_header) < 5 or info_header[0] != 0x55 or info_header[1] != 0xAA:
                return []
                
            info_payload_len = info_header[3]
            info_payload = self.i2c.readfrom(self.address, info_payload_len + 1)
            
            num_objects = info_payload[0] + (info_payload[1] << 8)
            blocks = []
            
            for _ in range(num_objects):
                blk_header = self.i2c.readfrom(self.address, 5)
                if len(blk_header) < 5:
                    continue
                blk_payload_len = blk_header[3]
                blk_payload = self.i2c.readfrom(self.address, blk_payload_len + 1)
                
                if blk_header[4] == 0x2A: # COMMAND_RETURN_BLOCK
                    x = blk_payload[0] + (blk_payload[1] << 8)
                    y = blk_payload[2] + (blk_payload[3] << 8)
                    w = blk_payload[4] + (blk_payload[5] << 8)
                    h = blk_payload[6] + (blk_payload[7] << 8)
                    id_val = blk_payload[8] + (blk_payload[9] << 8)
                    
                    blocks.append({
                        'x': x, 'y': y, 'width': w, 'height': h, 'id': id_val
                    })
            return blocks
        except Exception:
            return []

lens = HuskyLensI2C(i2c_bus)

# ==========================================
# 3. 비차단형 네오픽셀 연출 함수들
# ==========================================
def set_all_color(r, g, b):
    for i in range(NUM_LEDS):
        np[i] = (r, g, b)
    np.write()

def show_breathing_orange():
    """[2단계] 정체 발생 알림: 은은한 주황색 펄스 (LED 0, 1, 2)"""
    pulse = (math.sin(time.ticks_ms() / 300) + 1) / 2 # 조금 더 빠르게 숨쉬게 변경
    r = int(255 * pulse)
    g = int(90 * pulse)
    b = 0
    
    for i in range(3):
        np[i] = (r, g, b)
    for i in range(3, NUM_LEDS):
        np[i] = (0, 10, 0) # 상태등
    np.write()

def show_strobe_red():
    """[3단계] 긴급 충돌 경고: 빨간색 초고속 사이렌"""
    if (time.ticks_ms() // 100) % 2 == 0:
        set_all_color(255, 0, 0)
    else:
        set_all_color(0, 0, 0)

# ==========================================
# 4. 상태 정의 및 타이머 변수 (핵심 수정 부분)
# ==========================================
STATE_NORMAL = 0
STATE_WAITING = 1
STATE_DANGER = 2

current_state = STATE_NORMAL

# 시간 기록용 변수들 (초기화)
waiting_start_time = None  # 정체가 유지된 시작 시각
last_danger_time = 0       # 마지막으로 '위험(width > 80)'을 목격한 시각
last_follow_time = 0       # 마지막으로 '정체(30~80)'를 목격한 시각

# 상태를 유지해 주는 최소 시간 (1.5초)
STATE_HOLD_TIME = 1500  

print("상태 홀드 알고리즘 적용 완료! 시스템 테스트를 시작합니다.")
set_all_color(0, 50, 100)  # 기본 상태 (하늘색)

while True:
    blocks = lens.get_blocks()
    
    danger_detected = False
    follow_detected = False
    
    # 1. 센서 값 읽기
    for obj in blocks:
        if TEST_MODE_ANY_OBJECT or (obj['id'] == PERSON_ID):
            width = obj['width']
            print(f"감지 중.. 픽셀 크기(width): {width}") 
            
            if width > 80:
                danger_detected = True
            elif 30 <= width <= 80:
                follow_detected = True

    now = time.ticks_ms()

    # 2. 마지막 감지 시각 기록 업데이트
    if danger_detected:
        last_danger_time = now
    if follow_detected:
        last_follow_time = now

    # ==========================================
    # 3. ★ 핵심 상태 결정 머신 (Hysteresis & Hold)
    # ==========================================
    
    # [우선순위 1] 지금 위험하거나, 위험이 사라진 지 1.5초가 안 지났다면 무조건 "위험(빨간불)"
    if danger_detected or (time.ticks_diff(now, last_danger_time) < STATE_HOLD_TIME):
        current_state = STATE_DANGER
        waiting_start_time = None  # 정체용 타이머는 리셋
        
    # [우선순위 2] 위험하지 않고, 정체 대상이 감지 중이거나 놓친 지 1.5초가 안 지났을 때
    elif follow_detected or (time.ticks_diff(now, last_follow_time) < STATE_HOLD_TIME):
        # 정체 상태 진입 조건 계산 (최소 2초간 뒤따라와야 정체로 인정)
        if waiting_start_time is None:
            waiting_start_time = now  # 최초 정체 타이머 구동
            
        elapsed = time.ticks_diff(now, waiting_start_time)
        if elapsed >= 2000:  # 2초 유지 시
            current_state = STATE_WAITING
        else:
            current_state = STATE_NORMAL  # 2초 안 되었을 때는 아직 평상시 유지
            
    # [우선순위 3] 아무것도 감지되지 않고 1.5초 유예 시간도 모두 끝났을 때 -> "평상시(하늘색)"
    else:
        current_state = STATE_NORMAL
        waiting_start_time = None

    # ==========================================
    # 4. 결정된 상태에 따른 LED 최종 출력
    # ==========================================
    if current_state == STATE_DANGER:
        show_strobe_red()
    elif current_state == STATE_WAITING:
        show_breathing_orange()
    else:
        set_all_color(0, 50, 100) # 평상시 (하늘색)
        
    time.sleep_ms(20)
