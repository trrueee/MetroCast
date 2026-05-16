import os
import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer
from dotenv import load_dotenv

load_dotenv()

class CosyVoiceTTS:
    def __init__(self, voice: str = "longxiaochun"):
        """
        CosyVoice TTS 适配器
        常用音色: longxiaochun (活泼女声), longmiao (温柔女声), longst (稳重男声)
        """
        self.api_key = os.getenv("AI_API_KEY") 
        self.model = "cosyvoice-v1"
        self.voice = voice

    def generate_audio(self, text: str, output_dir: str) -> list:
        """
        使用 CosyVoice 为每段文字生成独立音频文件。
        每段单独保存为一个 MP3，返回 segment 元数据列表。
        不再直接二进制拼接 MP3。
        """
        import time as time_mod
        import dashscope
        dashscope.api_key = self.api_key
        os.makedirs(output_dir, exist_ok=True)

        # 将长文本按换行符拆分，每段不超过 500 字
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]

        # 预设多音色库
        VOICE_MAP = {
            "婉儿": "longyewan",  # 知性女声
            "老铁": "longlaotie", # 幽默东北男声（带劲！）
            "default": self.voice
        }

        segments = []

        for i, p in enumerate(paragraphs):
            # 动态识别音色标签
            current_voice = VOICE_MAP["default"]
            if p.startswith("[婉儿]"):
                current_voice = VOICE_MAP["婉儿"]
                p = p.replace("[婉儿]", "").replace("：", "").strip()
            elif p.startswith("[老铁]"):
                current_voice = VOICE_MAP["老铁"]
                p = p.replace("[老铁]", "").replace("：", "").strip()

            # 通用逻辑：在中英文、中数字交界处自动补空格
            refined_p = ""
            for idx in range(len(p)):
                char = p[idx]
                refined_p += char
                if idx + 1 < len(p):
                    next_char = p[idx+1]
                    is_current_eng = ord(char) < 128 and char.isalnum()
                    is_next_eng = ord(next_char) < 128 and next_char.isalnum()
                    if is_current_eng != is_next_eng:
                        refined_p += " "
            p = refined_p

            # 停顿优化
            p = p.replace("。", "。，").replace("！", "！，").replace("？", "？，")
            if not p.endswith((".", "。", "！", "？")):
                p += "。"
            p += " ... "

            print(f"正在合成第 {i+1}/{len(paragraphs)} 段 (音色: {current_voice})...")

            success = False
            audio_chunk = None
            for attempt in range(3):
                try:
                    # 每一段都创建一个新的 synthesizer 对象
                    synthesizer = SpeechSynthesizer(model=self.model, voice=current_voice)
                    audio_chunk = synthesizer.call(refined_p)
                    if audio_chunk:
                        success = True
                        break
                    else:
                        print(f"警告：第 {i+1} 段第 {attempt+1} 次合成未返回数据，2秒后重试...")
                except Exception as e:
                    print(f"警告：第 {i+1} 段第 {attempt+1} 次合成失败: {e}，2秒后重试...")

                time_mod.sleep(2)  # 强制等待，避免高频请求被封禁

            if not success:
                print(f"错误：第 {i+1} 段合成在重试 3 次后依然失败，跳过该段。")
                continue

            # 每段单独保存为独立文件
            seg_filename = f"segment_{i:03d}.mp3"
            seg_path = os.path.join(output_dir, seg_filename)
            with open(seg_path, 'wb') as f:
                f.write(audio_chunk)

            segments.append({
                "index": i,
                "text": p,
                "voice": current_voice,
                "audio_path": seg_path,
                "filename": seg_filename,
            })

        if segments:
            return segments
        else:
            raise Exception("CosyVoice TTS 呼叫失败，未返回任何音频数据")

if __name__ == "__main__":
    pass
    # Test
    # tts = CosyVoiceTTS()
    # tts.generate_audio("欢迎使用通义万物 CosyVoice 合成播客内容。", "cosy_test.mp3")
