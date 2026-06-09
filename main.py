import time
from machine import I2C, Pin
from neopixel import NeoPixel

# ==========================================
# 0. 개발용 테스트 설정
# ==========================================
TEST_MODE_ANY_OBJECT = False   # 실전 모드 (학습된 대상만 인식)
TARGET_IDS = [1, 2, 3]         # ★ 인식할 대상들의 ID 목록 (사람, 자전거, 킥보드 등)

# ==========================================
# 1. WS2813 Mini 네오픽셀 설정
# ==========================================
NUM_LEDS = 10
NEO_PIN = 16
TIMING = (280, 515, 515, 745)  # WS2813 Mini 전용 타이밍
np = NeoPixel(Pin(NEO_PIN), NUM_LEDS, timing=TIMING)

# I2C1 설정 (SDA=GP6, SCL=GP7)
i2c_bus = I2C(1, sda=Pin(6), scl=Pin(7), freq=100000)

# ==========================================
# 2. 허스키렌즈 I2C 통신 클래스
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
                
                if blk_header[4] == 0x2A:
                    x = blk_payload[0] + (blk_payload[1] << 8)
                    y = blk_payload[2] + (blk_payload[3] << 8)
                    w = blk_payload[4] + (blk_payload[5] << 8)
                    h = blk_payload[6] + (blk_payload[7] << 8)
                    id_val = blk_payload[8] + (blk_payload[9] << 8)
                    blocks.append({'x': x, 'y': y, 'width': w, 'height': h, 'id': id_val})
            return blocks
        except Exception:
            return []

lens = HuskyLensI2C(i2c_bus)

def set_color(r, g, b):
    for i in range(NUM_LEDS):
        np[i] = (r, g, b)
    np.write()

# 부팅 신호
set_color(0, 100, 0)
time.sleep(0.5)
set_color(0, 0, 0)
time.sleep(0.5)

print("다중 객체 인식 모드 시작...")

while True:
    blocks = lens.get_blocks()
    
    # 기본 색상: 하늘색 (대기)
    r, g, b = 0, 50, 100 
    
    for obj in blocks:
        # ★ obj의 ID가 우리가 정한 TARGET_IDS 목록 안에 있는지 확인!
        if TEST_MODE_ANY_OBJECT or (obj['id'] in TARGET_IDS):
            width = obj['width']
            # 어떤 종류(ID)가 감지되었는지 함께 출력
            print(f"감지! 종류 ID: {obj['id']}, 크기(width): {width}")
            
            if width > 80:
                r, g, b = 255, 0, 0   # 위험: 빨간색
                break  # 위험이 감지되면 즉시 중단
            elif 30 <= width <= 80:
                r, g, b = 255, 80, 0  # 정체: 주황색
                
    set_color(r, g, b)
    time.sleep_ms(50)
