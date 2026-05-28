import time
from machine import I2C, Pin
import neopixel
import math

# ==========================================
# 1. 하드웨어 및 네오픽셀 설정 (GP16 사용)
# ==========================================
NUM_LEDS = 8
NEO_PIN = 16  # 네오픽셀 데이터 선을 GP16 (D16)에 연결
np = neopixel.NeoPixel(Pin(NEO_PIN), NUM_LEDS)

# I2C1 설정 (SDA=GP6, SCL=GP7 채널 활성화)
# 만약 GP2, GP3에 꼽았다면 sda=Pin(2), scl=Pin(3)으로 수정하세요.
i2c_bus = I2C(1, sda=Pin(6), scl=Pin(7), freq=100000)

# ==========================================
# 2. 허스키렌즈 I2C 통신 클래스
# ==========================================
class HuskyLensI2C:
    def __init__(self, i2c_bus, address=0x32):
        self.i2c = i2c_bus
        self.address = address
        
    def get_blocks(self):
        """허스키렌즈로부터 화면상에 감지된 객체 정보를 가져옵니다."""
        cmd = bytearray([0x55, 0xAA, 0x11, 0x00, 0x20, 0x30])
        try:
            self.i2c.writeto(self.address, cmd)
            time.sleep_ms(20) # 허스키렌즈 처리 대기
            
            info = self.i2c.readfrom(self.address, 10)
            if len(info) < 10 or info[0] != 0x55 or info[1] != 0xAA:
                return []
            
            num_blocks = info[5] + (info[6] << 8)
            blocks = []
            
            for _ in range(num_blocks):
                block_data = self.i2c.readfrom(self.address, 16)
                if len(block_data) == 16 and block_data[4] == 0x2A: # COMMAND_RETURN_BLOCK
                    x = block_data[5] + (block_data[6] << 8)
                    y = block_data[7] + (block_data[8] << 8)
                    w = block_data[9] + (block_data[10] << 8)
                    h = block_data[11] + (block_data[12] << 8)
                    id_val = block_data[13] + (block_data[14] << 8)
                    
                    blocks.append({
                        'x': x, 'y': y, 'width': w, 'height': h, 'id': id_val
                    })
            return blocks
        except Exception:
            return []

lens = HuskyLensI2C(i2c_bus)

# ==========================================
# 3. 비차단형(Non-blocking) 네오픽셀 연출 함수들
# ==========================================
def set_all_color(r, g, b):
    """모든 LED를 지정한 색상으로 설정"""
    for i in range(NUM_LEDS):
        np[i] = (r, g, b)
    np.write()

def show_breathing_orange():
    """[2단계] 사용자 알림용 주황색 숨쉬기 연출 (LED 0, 1, 2번 사용)"""
    pulse = (math.sin(time.ticks_ms() / 400) + 1) / 2  # 0.0 ~ 1.0 사이 값 생성
    r = int(255 * pulse)
    g = int(90 * pulse)
    b = 0  # 파란색 채널 값 고정
    
    # 0, 1, 2번은 주황색 펄스
    for i in range(3):
        np[i] = (r, g, b)
    # 나머지는 연한 초록색 상태 표시
    for i in range(3, NUM_LEDS):
        np[i] = (0, 10, 0)
    np.write()

def show_strobe_red():
    """[3단계] 긴급 비상용 빨간색 초고속 깜빡이 연출 (전체 LED 사용)"""
    # 0.1초마다 켜고 끄기 위해 시간(ms)에 따라 조건 판정
    if (time.ticks_ms() // 100) % 2 == 0:
        set_all_color(255, 0, 0) # 전체 밝은 빨간색
    else:
        set_all_color(0, 0, 0)   # 일시 소등

# ==========================================
# 4. 실시간 상태 감지 및 메인 루프
# ==========================================
waiting_start_time = None
PERSON_ID = 1 # 허스키렌즈 일반 사물 인식 모드의 '사람' ID

print("통합 후방 위험 및 양보 감지 스탠드 작동 시작 (I2C1 & GP16)...")

while True:
    blocks = lens.get_blocks()
    
    # 실시간 상태 판정 변수
    danger_detected = False
    follow_detected = False
    
    for obj in blocks:
        if obj['id'] == PERSON_ID:
            width = obj['width']
            
            # [조건 1] 충돌 위험: 객체 너비가 120 이상인 경우 (너무 가깝거나 빠른 접근)
            if width > 120:
                danger_detected = True
                break # 위험 상황은 발견 즉시 판정하므로 탐색 중단
                
            # [조건 2] 양보 권고 대상: 객체 너비가 70 ~ 120 사이일 때
            elif 70 <= width <= 120:
                follow_detected = True

    # 4초 누적 대기 상태 판정 (비차단형 타이머 방식)
    is_waiting = False
    if follow_detected and not danger_detected:
        if waiting_start_time is None:
            waiting_start_time = time.ticks_ms()
        else:
            elapsed = time.ticks_diff(time.ticks_ms(), waiting_start_time)
            if elapsed >= 4000: # 4초 이상 뒤를 졸졸 따라오는 중
                is_waiting = True
    else:
        # 안전구역을 벗어났거나, 충돌 직전이거나, 사람이 사라지면 타이머 리셋
        waiting_start_time = None

    # ==========================================
    # 5. 우선순위에 따른 네오픽셀 패턴 출력
    # ==========================================
    if danger_detected:
        # 최우선순위: 긴급 충돌 경고! (빨간색 사이렌 효과)
        show_strobe_red()
    elif is_waiting:
        # 두번째순위: 양보 필요 상태 (은은한 주황색 숨쉬기 효과)
        show_breathing_orange()
    else:
        # 평상시 상태: 평화로움 (맑은 하늘색 유지)
        set_all_color(0, 50, 100)
        
    time.sleep_ms(20) # 원활한 애니메이션 구동을 위한 딜레이
