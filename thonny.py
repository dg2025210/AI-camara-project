from machine import I2C, Pin, PWM
import time

class HuskyLens:
    def __init__(self, i2c_bus, address=0x32):
        self.i2c = i2c_bus
        self.address = address

    def get_blocks(self):
        command = bytearray([0x55, 0xAA, 0x11, 0x00, 0x20, 0x31])
        try:
            self.i2c.writeto(self.address, command)
            time.sleep(0.05) 
            response = self.i2c.readfrom(self.address, 16)
            
            if response[0] == 0x55 and response[1] == 0xAA:
                if response[3] == 0x0A: 
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
    led_r.duty_u16(int((r / 255) * 65535))
    led_g.duty_u16(int((g / 255) * 65535))
    led_b.duty_u16(int((b / 255) * 65535))

print("💡 당곡고 AI 도우미: '넓이(Area)'를 이용한 거리 측정 시작!")
set_led_color(0, 0, 0) 

while True:
    block = huskylens.get_blocks()
    
    if block:
        obj_id = block["id"]
        box_width = block["width"]
        box_height = block["height"]
        
        # [핵심 로직 변경] 가로와 세로를 곱하여 '넓이(Area)'를 구합니다!
        box_area = box_width * box_height 
        
        print(f"📦 ID: {obj_id} / 가로: {box_width}, 세로: {box_height} / 📏 넓이: {box_area}")
        
        # 넓이(Area)를 기준으로 거리를 판단합니다.
        # 전체 화면 넓이가 76800 이므로, 이 기준값(10000, 30000)은 거리에 맞게 조절해 보세요!
        if box_area < 10000:
            print("🟢 멀리 있습니다. (화면 비중이 작음)")
            set_led_color(0, 255, 0)
            
        elif 10000 <= box_area < 30000:
            print("🟡 중간 거리에 있습니다.")
            set_led_color(255, 255, 0)
            
        elif box_area >= 30000:
            print("🔴 아주 가깝습니다! (화면에 크게 꽉 참)")
            set_led_color(255, 0, 0)
            
    else:
        set_led_color(0, 0, 0) # 화면에 아무것도 없을 때 끄기
        
    time.sleep(0.1)
