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
NEO_PIN = 16  # 네오픽셀 데이터 선 GP16
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
        """허스키렌즈로부터 dynamic packet-length 방식으로 정교하게 데이터를 수집합니다."""
        cmd = bytearray([0x55, 0xAA, 0x11, 0x00, 0x20, 0x30])
        try:
            self.i2c.writeto(self.address, cmd)
            time.sleep_ms(20) # 허스키렌즈 처리 대기
            
            # [1단계] 헤더 5바이트 수신
            info_header = self.i2c.readfrom(self.address, 5)
            if len(info_header) < 5 or info_header[0] != 0x55 or info_header[1] != 0xAA:
                return []
                
            # [2단계] 페이로드 수신 (길이 + 체크섬 1바이트)
            info_payload_len = info_header[3]
            info_payload = self.i2c.readfrom(self.address, info_payload_len + 1)
            
            # [3단계] 감지된 물체의 총 개수 계산
            num_objects = info_payload[0] + (info_payload[1] << 8)
            blocks = []
            
            # [4단계] 개별 블록 데이터 파싱
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
    pulse = (math.sin(time.ticks_ms() / 400) + 1) / 2
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
# 4. 상태 관리 변수 (유예 시간 논리 포함)
# ==========================================
waiting_start_time = None  # 정체 상태가 시작된 시각
last_seen_time = None      # 마지막으로 화면에서 타겟을 감지한 시각

print("개선된 실시간 3단계 감지 시스템 가동...")
set_all_color(0, 50, 100)  # 기본 대기 상태 (하늘색)

while True:
    blocks = lens.get_blocks()
    
    danger_detected = False
    follow_detected = False
    
    for obj in blocks:
        if TEST_MODE_ANY_OBJECT or (obj['id'] == PERSON_ID):
            width = obj['width']
            # 실시간으로 감지되는 물체의 가로 픽셀 크기를 콘솔에 출력 (디버깅 편의성 업그레이드!)
            print(f"감지 중.. 픽셀 크기(width): {width}") 
            
            # [수정된 기준] 충돌 위험: 너비가 80픽셀을 초과할 때 (상대적으로 가까움)
            if width > 80:
                danger_detected = True
                break
                
            # [수정된 기준] 정체 발생 범위: 너비가 30 ~ 80픽셀 사이일 때 (적당히 떨어진 거리)
            elif 30 <= width <= 80:
                follow_detected = True

    # ==========================================
    # ★ 개선된 핵심 알고리즘: 프레임 유예 시간 적용
    # ==========================================
    is_waiting = False
    
    if follow_detected and not danger_detected:
        last_seen_time = time.ticks_ms() # '방금 전 물체를 보았다'고 시각 기록
        
        if waiting_start_time is None:
            waiting_start_time = time.ticks_ms() # 정체 타이머 시작
        
        # 2초(2000ms) 이상 안정적으로 머물렀는지 판정
        elapsed = time.ticks_diff(time.ticks_ms(), waiting_start_time)
        if elapsed >= 2000:
            is_waiting = True
            
    else:
        # 화면에서 순간적으로 물체를 놓쳤다면 (follow_detected == False)
        if last_seen_time is not None:
            # 마지막으로 보았던 때로부터 '유예 시간(1초)'이 지났는지 확인합니다.
            time_since_last_seen = time.ticks_diff(time.ticks_ms(), last_seen_time)
            
            # 놓친 지 1초(1000ms)가 지났거나, 아예 빨간불(충돌 위험) 상황이 되었다면 비로소 누적 타이머를 0으로 리셋합니다.
            if time_since_last_seen > 1000 or danger_detected:
                waiting_start_time = None
                last_seen_time = None
        else:
            # 아예 처음부터 감지되지 않은 상태라면 리셋
            waiting_start_time = None

    # ==========================================
    # 5. 우선순위 출력 제어
    # ==========================================
    if danger_detected:
        show_strobe_red()
    elif is_waiting:
        show_breathing_orange()
    else:
        set_all_color(0, 50, 100) # 평상시 (하늘색)
        
    time.sleep_ms(20)
