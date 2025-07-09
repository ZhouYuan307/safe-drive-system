import os

class AlcoholSensor:
    def __init__(self, device_path='/sys/bus/iio/devices/iio:device0/in_voltage4_raw'):
        self.device_path = device_path
        
    def read_raw_value(self):
        try:
            with open(self.device_path, 'r') as f:
                raw_value = int(f.read().strip())
            return raw_value
        except (IOError, ValueError) as e:
            print(f"Error reading sensor value: {e}")
            return None
    
    def read_voltage(self, vref=3.3, max_raw=4095):
        raw_value = self.read_raw_value()
        if raw_value is not None:
            return (raw_value / max_raw) * vref
        return None


#测试用
'''
if __name__ == '__main__':
    sensor = AlcoholSensor()

    raw_value = sensor.read_raw_value()
    if raw_value is not None:
        print(f"Raw sensor value: {raw_value}")

    voltage = sensor.read_voltage()
    if voltage is not None:
        print(f"Sensor voltage: {voltage:.2f}V")
'''