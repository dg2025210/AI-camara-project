import time
from machine import I2C, Pin
import neopixel
import math

# ==========================================
# 0. 개발용 테스트 설정 (손 감지 테스트 가능)
# ==========================================
# True로 설정하면 학습 안 된 물체(ID 0)도 무조건 인식하여 테스트가 쉬워집니다.
# 단, 1번 설명처럼 허스키렌즈 화면에 '네모 박스'가 반드시 뜨고 있어야 작동합니다!
TEST_MODE_ANY_OBJECT = True 
PERSON_ID = 1  # 테스트 모드가 False일 때만 인식할 ID (기본 사람 ID는 1)

# ==========================================
# 1. 하드웨어 및 네오픽셀 설정 (GP16 사용)
# ==========================================
NUM_LEDS = 8
NEO_PIN = 16  # 네오픽셀 데이터 선을 GP16에 연결
np = neopixel.NeoPixel(Pin(NEO_PIN), NUM_LEDS)

# I2C1 설정 (SDA=GP6, SCL=GP7 채널 활성화)
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
        # 데이터 요청 명령어 (COMMAND_REQUEST = 0x20)
        cmd = bytearray([0x55, 0xAA, 0x11, 0x00, 0x20, 0x30])
        try:
            self.i2c.writeto(self.address, cmd)
            time.sleep_ms(30)  # 허스키렌즈가 응답을 계산할 시간을 충분히 줍니다.
            
            # [단계 1] 최초 5바이트(헤더 3바이트 + 데이터 길이 1바이트 + 명령어 1바이트) 읽기
            info_header = self.i2c.readfrom(self.address, 5)
            if len(info_header) < 5 or info_header[0] != 0x55 or info_header[1] != 0xAA:
                return []
                
            # [단계 2] 수신한 정보 창에 적힌 데이터 길이만큼 정확히 추가 수신 (길이 + 체크섬 1바이트)
            info_payload_len = info_header[3]
            info_payload = self.i2c.readfrom(self.address, info_payload_len + 1)
            
            # [단계 3] 감지된 물체의 총 개수 계산 (INFO 패킷 파싱)
            num_objects = info_payload[0] + (info_payload[1] << 8)
            blocks = []
            
            # [단계 4] 물체 개수만큼 반복하여 각각의 블록 데이터 읽기
            for _ in range(num_objects):
                # 블록 헤더 5바이트 수신
                blk_header = self.i2c.readfrom(self.address, 5)
                if len(blk_header) < 5:
                    continue
                # 블록의 실제 데이터 수신 (길이 + 체크섬 1바이트)
                blk_payload_len = blk_header[3]
                blk_payload = self.i2c.readfrom(self.address, blk_payload_len + 1)
                
                # COMMAND_RETURN_BLOCK (0x2A) 데이터 분석
                if blk_header[4] == 0x2A:
                    x = blk_payload[0] + (blk_payload[1] << 8)
                    y = blk_payload[2] + (blk_payload[3] << 8)
                    w = blk_payload[4] + (blk_payload[5] << 8)
                    h = blk_payload[6] + (blk_payload[7] << 8)
                    id_val = blk_payload[8] + (blk_payload[9] << 8)
                    
                    blocks.append({
                        'x': x, 'y': y, 'width': w, 'height': h, 'id': id_val
                    })
            return blocks
        except Exception as e:
            # 에러 발생 시 Thonny 셸에 에러 표시 (연결선 단선 확인용)
            # print("I2C 통신 오류:", e)
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
    """[2단계] 양보 권고: 주황색 숨쉬기 (LED 0, 1, 2)"""
    pulse = (math.sin(time.ticks_ms() / 400) + 1) / 2
    r = int(255 * pulse)
    g = int(90 * pulse)
    b = 0
    
    for i in range(3):
        np[i] = (r, g, b)
    for i in range(3, NUM_LEDS):
        np[i] = (0, 10, 0) # 평상시 상태 표시등
    np.write()

def show_strobe_red():
    """[3단계] 긴급 비상: 빨간색 초고속 깜빡이"""
    if (time.ticks_ms() // 100) % 2 == 0:
        set_all_color(255, 0, 0)
    else:
        set_all_color(0, 0, 0)

# ==========================================
# 4. 실시간 상태 감지 및 메인 루프
# ==========================================
waiting_start_time = None
print("초정밀 3단계 감지 시스템 가동 완료 (SDA=GP6, SCL=GP7)...")
set_all_color(0, 50, 100) # 대기 상태 (하늘색)

while True:
    blocks = lens.get_blocks()
    
    danger_detected = False
    follow_detected = False
    
    for obj in blocks:
        if TEST_MODE_ANY_OBJECT or (obj['id'] == PERSON_ID):
            width = obj['width']
            # 디버깅용 로그: Thonny 화면 하단에 인식된 물체의 폭 출력
            print(f"물체 감지됨! 너비(width): {width} 픽셀")
            
            if width > 120:
                danger_detected = True
                break
            elif 70 <= width <= 120:
                follow_detected = True

    # 4초 누적 대기 알고리즘
    is_waiting = False
    if follow_detected and not danger_detected:
        if waiting_start_time is None:
            waiting_start_time = time.ticks_ms()
        else:
            elapsed = time.ticks_diff(time.ticks_ms(), waiting_start_time)
            if elapsed >= 4000:
                is_waiting = True
    else:
        waiting_start_time = None

    # LED 출력 상태 업데이트
    if danger_detected:
        show_strobe_red()
    elif is_waiting:
        show_breathing_orange()
    else:
        set_all_color(0, 50, 100) # 대기 중 (하늘색)
        
    time.sleep_ms(20)
