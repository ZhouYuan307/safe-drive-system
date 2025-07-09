import time
import threading
import signal
from script import motor, hrspo2, detect_blinks, alcohol, messedge_tts
from datetime import datetime, timedelta
import asyncio

HOLD_FLAG = 1000

stop_event = threading.Event()


def log_abnormal(info):
    with open("abnormal_log.txt", "a") as f:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"{now} | {info}\n")

#eg:log_abnormal("血氧过低")

def signal_handler(sig, frame):
    print("\n[系统] 准备退出...")
    stop_event.set()

def monitor_heart_rate():
    warning_text = "检测到您已连续驾驶较长时间，疲劳会降低反应速度哦～建议在安全区域休息20分钟再出发吧！"
    stable_threshold = 2
    stable_duration = 10
    prev_bpm = 0
    stable_time = 0

    while not stop_event.is_set():
        time.sleep(5)
        current_bpm = hrspo2.latest_bpm['value']
        current_spo2 = hrspo2.latest_spo2['value']
        print(f"[监控] 当前心率: {current_bpm} BPM, 血氧: {current_spo2:.1f}%")

        if current_bpm == 0:
            continue

        if (current_spo2 < 90) and (hrspo2.flag['value'] > HOLD_FLAG):
            print("[警告] SpO₂ 低于 90%")
            log_abnormal("血氧过低")
            motor.run_motor(60)

        if abs(current_bpm - prev_bpm) <= stable_threshold:
            stable_time += 1
            #print(f"[监控] 心率稳定时间: {stable_time * 5}s")
            if (stable_time >= stable_duration) and (hrspo2.flag['value'] > HOLD_FLAG):
                try:
                    print("[警告] 心率稳定时间过长，疑似疲劳")
                    log_abnormal("心率稳定时间过长，疑似疲劳")
                    asyncio.run(messedge_tts.text_to_speech_play(warning_text, rate="+0%"))
                    motor.run_motor(60)
                except Exception as e:
                    print(f"[错误] 触发马达失败: {e}")
                stable_time = 0
        else:
            stable_time = 0

        prev_bpm = current_bpm



def read_alcohol():
    sensor = alcohol.AlcoholSensor()
    warning_text = "系统检测到您可能饮酒，方向盘和酒精的‘组合技’风险超高！建议您改日再开车~"
    while not stop_event.is_set():
        time.sleep(3)
        value = sensor.read_raw_value()
        voltage = sensor.read_voltage()
        if value is not None:
            print(f"酒精传感器原始值: {value}")
        if voltage is not None:
            print(f"酒精传感器电压值: {voltage:.2f}V")
        if value < 2000:
            asyncio.run(messedge_tts.text_to_speech_play(warning_text, rate="+0%"))



if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    monitor_thread = threading.Thread(
        target=monitor_heart_rate,
        daemon=True
    )
    monitor_thread.start()

    alcohol_thread = threading.Thread(
        target=read_alcohol,
        daemon=True
    )
    alcohol_thread.start()

    blink_thread = threading.Thread(
        target=detect_blinks.run_blink_detection,
        kwargs={"stop_event": stop_event},
        daemon=True
    )
    blink_thread.start()

    try:
        hrspo2.run_hrspo2(stop_event=stop_event)
    except Exception as e:
        print(f"[系统] 运行失败: {e}")
    finally:
        stop_event.set()
        monitor_thread.join(timeout=2)
        alcohol_thread.join(timeout=2)
        blink_thread.join(timeout=2)
