import time
import os
PWM_BASE = '/sys/class/pwm/pwmchip0'

class PWMMotor:
    def __init__(self, channel):
        self.channel = channel
        self.path = f"{PWM_BASE}/pwm{channel}"
        self.exported = False
        
        try:
            # 检查是否已导出
            if not os.path.exists(self.path):
                with open(f"{PWM_BASE}/export", 'w') as f:
                    f.write(str(channel))
                time.sleep(0.2)  # 等待系统创建文件
                
            if os.path.exists(self.path):
                self.exported = True
            else:
                raise RuntimeError(f"无法导出PWM通道 {channel}")
                
        except PermissionError:
            print("错误：需要root权限运行此脚本")
            print("请尝试: sudo python3 motor.py")
            raise
        except Exception as e:
            print(f"初始化PWM{channel}失败: {str(e)}")
            raise
        
    def setup(self, freq_hz=50):
        if not self.exported:
            return
            
        period_ns = int(1e9 / freq_hz)
        self.set_period(period_ns)
        self.set_duty_cycle(0)
        try:
            self.set_polarity("normal")
        except:
            print("ERROR")
        
    def set_period(self, period_ns):
        if not self.exported:
            return
            
        try:
            with open(f"{self.path}/period", 'w') as f:
                f.write(str(period_ns))
        except:
            print(f"设置PWM{self.channel}周期失败")
    
    def set_duty_cycle(self, duty_cycle_ns):
        with open(f"{self.path}/duty_cycle", 'w') as f:
            f.write(str(duty_cycle_ns))
    
    def set_polarity(self, polarity):
        with open(f"{self.path}/polarity", 'w') as f:
            f.write(polarity)
    
    def enable(self):
        with open(f"{self.path}/enable", 'w') as f:
            f.write("1")
    
    def disable(self):
        with open(f"{self.path}/enable", 'w') as f:
            f.write("0")
    
    def set_speed_percent(self, percent):
        with open(f"{self.path}/period", 'r') as f:
            period = int(f.read())
        duty = int(period * percent / 100)
        self.set_duty_cycle(duty)
    
    def __del__(self):
        self.disable()
        with open(f"{PWM_BASE}/unexport", 'w') as f:
            f.write(str(self.channel))

def test_single_motor():
    motor = PWMMotor(0)
    motor.setup(freq_hz=50)
    
    try:
        motor.enable()
        for speed in range(0, 101, 10):
            print(f"设置速度: {speed}%")
            motor.set_speed_percent(speed)
            time.sleep(1)
    finally:
        motor.disable()

def run_motor(speed):
    motor = PWMMotor(0)
    motor.setup(freq_hz=50)

    
    try:
        motor.enable()
        motor.set_speed_percent(speed)
        time.sleep(1)
    finally:
        motor.disable()


#测试用
'''
if __name__ == "__main__":
    try:
        test_single_motor()
        time.sleep(1)
    except KeyboardInterrupt:
        print("中断")
    except Exception as e:
        print(f"测试出错: {str(e)}")
'''

