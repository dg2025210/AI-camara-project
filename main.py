import time
from machine import I2C, Pin
import neopixel

# ==========================================
# 1. 하드웨어 및 네오픽셀 설정 (GP16, I2C1 사용)
# ==========================================
NUM_LEDS = 8
NEO_PIN = 16  # 네오픽셀 GP16 연결
np = neopixel.NeoPixel(Pin(NEO_PIN), NUM_LEDS)

# I2C1 설정 (SDA=GP6, SCL=GP7)
i2c_bus = I2C(1, sda=Pin(6), scl=Pin(7), freq=100000)

# ==========================================
# 2. 허스키렌즈 기본 통신 클래스
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
                
                if blk_header[4] == 0x2A: # Block 감지
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
    """네오픽셀 전체 색상을 즉시 변경하는 함수"""
    for i in range(NUM_LEDS):
        np[i] = (r, g, b)
    np.write()

# 시작할 때 꺼짐 상태로 세팅
set_color(0, 0, 0)
time.sleep(0.5)

print("초간단 실시간 수치 매핑 시작...")

while True:
    blocks = lens.get_blocks()
    
    # 기본 색상: 화면에 아무것도 잡히지 않을 때는 하늘색(Cyan)
    r, g, b = 0, 50, 100 
    
    if len(blocks) > 0:
        # 화면에 잡힌 첫 번째 물체의 가로 크기(width) 가져오기
        width = blocks[0]['width']
        print(f"실시간 수치 감지 중 -> 크기: {width}")
        
        if width > 80:
            # 80보다 크면 무조건 빨간색 (Red)
            r, g, b = 255, 0, 0
        elif 30 <= width <= 80:
            # 30 ~ 80 사이면 무조건 주황색 (Orange)
            r, g, b = 255, 80, 0
    else:
        print("화면에 아무것도 없음")
        
    # 결정된 색상을 네오픽셀에 즉시 적용
    set_color(r, g, b)
    
    time.sleep_ms(50)  # 0.05초마다 초고속으로 업데이트
