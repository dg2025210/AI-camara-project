from machine import I2C, Pin, PWM
import time

# 당곡고 AI 도우미: 허스키 렌즈 I2C 통신 클래스
class HuskyLens:
    def __init__(self, i2c_bus, address=0x32):
        self.i2c = i2c_bus
        self.address = address

    def get_blocks(self):
        # 데이터 요청 명령어 전송
        command = bytearray([0x55, 0xAA, 0x11, 0x00, 0x20, 0x31])
        try:
            self.i2c.writeto(self.address, command)
            time.sleep(0.05) # 데이터 준비 대기
            response = self.i2c.readfrom(self.address, 16)
            
            # 패킷 헤더(0x55, 0xAA)와 데이터 종류(0x0A: 블록) 확인
            if response[0] == 0x55 and response[1] == 0xAA:
                if response[3] == 0x0A: 
                    # 10바이트 데이터에서 위치(x,y), 크기(width, height), 사물 ID 추출
                    x = response[5] + (response[6] << 8)
                    y = response[7] + (response[8] << 8)
                    width = response[9] + (response[10] << 8)
                    height = response[11] + (response[12] << 8)
                    obj_id = response[13] + (response[14] << 8)
                    
                    return {"x": x, "y": y, "width": width, "height": height, "id": obj_id}
        except OSError:
            print("통신 오류: 선 연결을 확인하세요.")
            return None
        return None

# 1. 허스키 렌즈 I2C 통신 설정
i2c_bus = I2C(0, scl=Pin(5), sda=Pin(4), freq=100000)
huskylens = HuskyLens(i2c_bus)

# 2. RGB LED 핀 및 PWM 설정
led_r = PWM(Pin(13))
led_g = PWM(Pin(14))
led_b = PWM(Pin(15))

led_r.freq(1000)
led_g.freq(1000)
led_b.freq(1000)

def set_led_color(r, g, b):
    # 0~255 값을 피코의 16비트 해상도(0~65535)로 변환
    led_r.duty_u16(int((r / 255) * 65535))
    led_g.duty_u16(int((g / 255) * 65535))
    led_b.duty_u16(int((b / 255) * 65535))

print("💡 당곡고 AI 도우미: 사물 인식 및 거리 측정 프로젝트 시작!")
set_led_color(0, 0, 0) # 초기 상태: LED 끄기

while True:
    block = huskylens.get_blocks()
    
    if block:
        obj_id = block["id"]
        box_width = block["width"]
        
        print(f"📦 사물 ID: {obj_id} 발견! / 현재 너비: {box_width}")
        
        # [핵심 로직] 사물의 너비(크기)를 기준으로 거리를 판단합니다.
        # 앞서 논의한 기준값(80, 160)을 적용했습니다. 실험을 통해 수정해 보세요!
        if box_width < 80:
            print("🟢 사물이 멀리 있습니다.")
            set_led_color(0, 255, 0) # 초록색
            
        elif 80 <= box_width < 160:
            print("🟡 사물이 중간 거리에 있습니다.")
            set_led_color(255, 255, 0) # 노란색
            
        elif box_width >= 160:
            print("🔴 사물이 아주 가깝습니다!")
            set_led_color(255, 0, 0) # 빨간색
            
    else:
        # 화면에 아무 사물도 인식되지 않을 때
        set_led_color(0, 0, 0) # LED 끄기 (또는 0, 0, 255 로 파란색 대기 상태 가능)
        
    time.sleep(0.1) # 반응 속도를 조금 더 빠르게 조정 (0.1초)
