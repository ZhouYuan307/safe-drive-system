import time
import threading
from smbus2 import SMBus
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque
import numpy as np
from scipy.signal import butter, filtfilt

latest_bpm = {'value': 0}
latest_spo2 = {'value': 0}
flag = {'value': 0} #用于判断驾驶员的手是否在传感器上，以免误报
#I2C设置
I2C_BUS_NUM = 7
I2C_ADDR = 0x57

REG_INTR_STATUS_1 = 0x00
REG_INTR_STATUS_2 = 0x01
REG_INTR_ENABLE_1 = 0x02
REG_INTR_ENABLE_2 = 0x03
REG_FIFO_WR_PTR = 0x04
REG_OVF_COUNTER = 0x05
REG_FIFO_RD_PTR = 0x06
REG_FIFO_DATA = 0x07
REG_FIFO_CONFIG = 0x08
REG_MODE_CONFIG = 0x09
REG_SPO2_CONFIG = 0x0A
REG_LED1_PA = 0x0C
REG_LED2_PA = 0x0D

#滤波器
def lowpass_filter(data, cutoff=8, fs=100, order=1):
    b, a = butter(order, cutoff / (0.5 * fs), btype='low')
    return filtfilt(b, a, data)

def setup_sensor(bus):
    bus.write_byte_data(I2C_ADDR, REG_MODE_CONFIG, 0x40)
    time.sleep(0.1)
    bus.write_byte_data(I2C_ADDR, REG_FIFO_WR_PTR, 0x00)
    bus.write_byte_data(I2C_ADDR, REG_OVF_COUNTER, 0x00)
    bus.write_byte_data(I2C_ADDR, REG_FIFO_RD_PTR, 0x00)
    bus.write_byte_data(I2C_ADDR, REG_FIFO_CONFIG, 0x4F)
    bus.write_byte_data(I2C_ADDR, REG_MODE_CONFIG, 0x03)
    bus.write_byte_data(I2C_ADDR, REG_SPO2_CONFIG, 0x27)
    bus.write_byte_data(I2C_ADDR, REG_LED1_PA, 0x24)
    bus.write_byte_data(I2C_ADDR, REG_LED2_PA, 0x24)

def read_fifo(bus):
    try:
        data = bus.read_i2c_block_data(I2C_ADDR, REG_FIFO_DATA, 6)
        red = (data[0] << 16) | (data[1] << 8) | data[2]
        ir = (data[3] << 16) | (data[4] << 8) | data[5]
        return ir & 0x3FFFF, red & 0x3FFFF
    except Exception as e:
        print(f"读取错误: {e}")
        return 0, 0

def calculate_ylim(data, margin=0.1):
    valid_data = [x for x in data if x > 1000]
    if not valid_data:
        return 0, 100000
    min_val = min(valid_data)
    max_val = max(valid_data)
    range_val = max(1, max_val - min_val)
    return (min_val - margin * range_val, max_val + margin * range_val)

def run_hrspo2(stop_event=None):
    # 初始化状态标志
    animation_running = True
    resources_initialized = False
    
    try:
        window_size = 200
        ir_buffer = deque([0]*window_size, maxlen=window_size)
        red_buffer = deque([0]*window_size, maxlen=window_size)
        ir_filtered = deque([0]*window_size, maxlen=window_size)
        sample_index = 0
        peak_x, peak_y = deque([], maxlen=20), deque([], maxlen=20)
        last_peak_time = [None]

        # 初始化图形界面
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
        x_vals = list(range(window_size))

        line_ir, = ax1.plot(x_vals, ir_buffer, label='IR Raw', color='red')
        line_ir_filt, = ax1.plot(x_vals, ir_filtered, label='IR Filtered', color='darkred')
        scatter_peak = ax1.scatter([], [], color='green', s=40, label='Peaks')
        text_info = ax1.text(0.02, 0.95, '', transform=ax1.transAxes, fontsize=10, verticalalignment='top')
        line_red, = ax2.plot(x_vals, red_buffer, label='RED', color='blue')

        ax1.set_title("MAX30102 Heart Rate & SpO₂ Monitor")
        ax1.set_ylabel("IR Value")
        ax1.legend(loc="upper right")
        ax2.set_ylabel("RED Value")
        ax2.set_xlabel("Sample Index")
        ax2.legend(loc="upper right")
        plt.tight_layout()

        # 初始化硬件
        bus = SMBus(I2C_BUS_NUM)
        setup_sensor(bus)
        resources_initialized = True

        def update(frame):
            nonlocal sample_index, animation_running

            # 检查停止信号
            if stop_event and stop_event.is_set():
                if animation_running:
                    animation_running = False
                    plt.close(fig)
                return []

            try:
                ir, red = read_fifo(bus)
                sample_index += 1
                ir_buffer.append(ir)
                red_buffer.append(red)

                if len(ir_buffer) == window_size:
                    ir_filtered_np = lowpass_filter(list(ir_buffer))
                    ir_filtered.clear()
                    ir_filtered.extend(ir_filtered_np)

                    #标记变量以检测驾驶员的手是否在方向盘上
                    flag['value'] = list(ir_filtered)[-1]

                    raw = list(ir_buffer)
                    if sample_index >= 5:
                        mid = raw[-3]
                        prev1 = raw[-4]
                        next1 = raw[-2]

                        mean_val = np.mean(raw[-30:])
                        std_val = np.std(raw[-30:])
                        threshold = mean_val + 0.4 * std_val

                        if prev1 < mid > next1 and mid > threshold:
                            now = time.time()
                            if last_peak_time[0]:
                                interval = now - last_peak_time[0]
                                if 0.3 < interval < 2.0:
                                    bpm = int(60 / interval)
                                    latest_bpm['value'] = bpm
                            last_peak_time[0] = now
                            peak_x.append(sample_index - 3)
                            peak_y.append(mid)

                    # 计算血氧
                    red_np = np.array(red_buffer)
                    ir_np = np.array(ir_buffer)
                    red_ac = np.std(red_np)
                    ir_ac = np.std(ir_np)
                    red_dc = np.mean(red_np)
                    ir_dc = np.mean(ir_np)
                    r = (red_ac / red_dc) / (ir_ac / ir_dc) if ir_ac > 0 and red_ac > 0 else 0
                    spo2 = max(0, min(100, 110 - 25 * r)) if r > 0 else 0
                    latest_spo2['value'] = spo2

                # 更新图形
                line_ir.set_ydata(list(ir_buffer))
                line_ir_filt.set_ydata(list(ir_filtered))
                scatter_peak.set_offsets(np.c_[(peak_x, peak_y)])
                line_red.set_ydata(list(red_buffer))
                text_info.set_text(f"Heart Rate: {latest_bpm['value']} BPM\nSpO₂: {latest_spo2['value']:.1f}%")

                ax1.set_ylim(calculate_ylim(ir_buffer))
                ax2.set_ylim(calculate_ylim(red_buffer))
                
                return [line_ir, line_ir_filt, scatter_peak, line_red, text_info]
                
            except Exception as e:
                print(f"[hrspo2] 数据采集错误: {e}")
                return []

        # 创建动画
        ani = animation.FuncAnimation(
            fig, 
            update, 
            interval=50,
            blit=False,
            cache_frame_data=False
        )
        
        plt.show()
        
    except Exception as e:
        print(f"[hrspo2] 初始化错误: {e}")
    finally:
        # 资源清理
        try:
            if 'ani' in locals() and ani is not None:
                ani.event_source.stop()
        except:
            pass
            
        try:
            if 'fig' in locals() and fig is not None:
                plt.close(fig)
        except:
            pass
            
        try:
            if resources_initialized and 'bus' in locals():
                bus.close()
        except:
            pass