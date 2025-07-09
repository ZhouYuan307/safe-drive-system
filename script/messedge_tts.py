import edge_tts
import asyncio
import pygame
import io

# 异步函数：将文本转为语音并播放


async def text_to_speech_play(text, voice="zh-CN-XiaoxiaoNeural", rate="+0%"):
    """
    使用 edge-tts 将文本合成为语音，并用 pygame 播放，无需生成临时文件。
    :param text: 要合成的文本内容
    :param voice: 语音名称（微软Edge TTS支持的voice）
    :param rate: 语速（如"0%"为正常，"+20%"更快，"-20%"更慢）
    """
    # 创建 edge-tts 通信对象
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
    audio_bytes = b""  # 用于存储音频数据
    # 异步获取音频流数据
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_bytes += chunk["data"]

    # 初始化 pygame 音频模块
    pygame.mixer.init()
    # 将音频字节流包装为文件对象
    audio_file = io.BytesIO(audio_bytes)
    # 加载音频到pygame播放器
    pygame.mixer.music.load(audio_file)
    # 播放音频
    pygame.mixer.music.play()
    # 等待音频播放结束
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)


#测试用
'''
if __name__ == "__main__":
    # 要合成的文本内容
    text = "你好，这是微软Edge TTS的语音合成演示。"
    # 调用异步语音合成与播放函数，rate参数需为+0%、+20%等格式
    asyncio.run(text_to_speech_play(text, rate="+0%"))
'''
