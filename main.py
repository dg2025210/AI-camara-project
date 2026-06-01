import time
from machine import I2C, Pin
import neopixel
import math

# ==========================================
# 0. 개발용 테스트 설정 (중요!)
# ==========================================
# True로 설정하면 허스키렌즈에 물체를 "학습(Learn)"시키지 않아도,
# 화면에 아무 네모 상자(ID 0 포함)나 보이면 즉시 LED가 작동하여 테스트하기 편합니다.
TEST_MODE_ANY_OBJECT = True 
PERSON_ID = 1  # 테스트 모드가 False일 때만 감지할 목표 ID (학습된 대상)

# ==========================================
# 1. 하드웨어 및 네오픽셀 설정 (GP16 사용)
# ==========================================
NUM_LEDS = 8
NEO_PIN = 16  # 네오픽셀 데이터 선을 GP16에 연결
np = neopixel.NeoPixel(Pin(NEO_PIN), NUM_LEDS)

# I2C1 설정 (SDA=GP6, SCL=GP7 채널 활성화)
i2c_bus = I2C(1, sda=Pin(6), scl=Pin(7), freq=100000)

# ==========================================
# 2. 허스키렌즈 I2C 통신 클래스 (패킷 길이 수정 완료)
# ==========================================
class HuskyLensI2C:
    def __init__(self, i2c_bus, address=0x32):
        self.i2c = i2c_bus
        self.address = address
        
    def get_blocks(self):
        """허스키렌즈로부터 화면상에 감지된 객체 정보를 가져옵니다."""
        # 1. 데이터 요청 명령 전송
        cmd = bytearray([0x55, 0xAA, 0x11, 0x00, 0x20, 0x30])
        try:
            self.i2c.writeto(self.address, cmd)
            time.sleep_ms(20) # 허스키렌즈 처리 대기
            
            # 2. 응답 헤더 및 정보 패킷 읽기 (기존 10바이트 -> 16바이트로 수정!)
            info = self.i2c.readfrom(self.address, 16)
            if len(info) < 16 or info[0] != 0x55 or info[1] != 0xAA:
                return []
            
            # 감지된 블록 수 계산 (5, 6번째 바이트 사용)
            num_blocks = info[5] + (info[6] << 8)
            blocks = []
            
            # 3. 각 블록 데이터 읽기 (블록당 16바이트)
            for _ in range(num_blocks):
                block_data = self.i2c.readfrom(self.address, 16)
                if len(block_data) == 16 and block_data[4] == 0x2A: # 0x2A: COMMAND_RETURN_BLOCK
                    x = block_data[5] + (block_data[6] << 8)
                    y = block_data[7] + (block_data[8] << 8)
                    w = block_data[9] + (block_data[10] << 8)
                    h = block_data[11] + (block_data[12] << 8)
                    id_val = block_data[13] + (block_data[14] << 8)
                    
                    blocks.append({
                        'x': x, 'y': y, 'width': w, 'height': h, 'id': id_val
                    })
            return blocks
        except Exception as e:
            # 통신 중 오류가 났을 때 어떤 오류인지 Thonny 셸에 출력
            # print("I2C 에러:", e) 
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
    b = 0
    
    # 0, 1, 2번은 주황색 펄스
    for i in range(3):
        np[i] = (r, g, b)
    # 나머지는 연한 초록색 상태 표시
    for i in range(3, NUM_LEDS):
        np[i] = (0, 10, 0)
    np.write()

def show_strobe_red():
    """[3단계] 긴급 비상용 빨간색 초고속 깜빡이 연출 (전체 LED 사용)"""
    if (time.ticks_ms() // 100) % 2 == 0:
        set_all_color(255, 0, 0) # 전체 밝은 빨간색
    else:
        set_all_color(0, 0, 0)   # 일시 소등

# ==========================================
# 4. 실시간 상태 감지 및 메인 루프
# ==========================================
waiting_start_time = None

print("수정된 안전 시스템 작동 시작...")
set_all_color(0, 50, 100) # 대기 상태 (하늘색)로 시작

while True:
    blocks = lens.get_blocks()
    
    danger_detected = False
    follow_detected = False
    
    for obj in blocks:
        # TEST_MODE_ANY_OBJECT가 True이면 모든 물체(ID >= 0)를 대상으로 감지하고,
        # False이면 오직 등록된 특정 ID만 추적합니다.
        if TEST_MODE_ANY_OBJECT or (obj['id'] == PERSON_ID):
            width = obj['width']
            # print(f"감지된 물체 크기(width): {width}") # 모니터링용 출력
            
            # [조건 1] 충돌 위험: 너무 가깝거나 빠른 접근
            if width > 120:
                danger_detected = True
                break
                
            # [조건 2] 양보 권고 대상: 좁은 길 정체 유발 거리
            elif 70 <= width <= 120:
                follow_detected = True

    # 4초 누적 대기 상태 판정 (비차단형 타이머)
    is_waiting = False
    if follow_detected and not danger_detected:
        if waiting_start_time is None:
            waiting_start_time = time.ticks_ms()
        else:
            elapsed = time.ticks_diff(time.ticks_ms(), waiting_start_time)
            if elapsed >= 4000: # 4초 유지
                is_waiting = True
    else:
        waiting_start_time = None

    # ==========================================
    # 5. 우선순위에 따른 네오픽셀 패턴 출력
    # ==========================================
    if danger_detected:
        show_strobe_red()
    elif is_waiting:
        show_breathing_orange()
    else:
        set_all_color(0, 50, 100) # 평상시 (하늘색)
        
    time.sleep_ms(20) # 애니메이션 자연스럽게 구동
