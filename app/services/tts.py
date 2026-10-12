import wave
from google.genai import types
class TTS:
 def __init__(self,pool,model,voice):self.pool=pool;self.model=model;self.voice=voice
 def run(self,text,out):
  cfg=types.GenerateContentConfig(response_modalities=["AUDIO"],speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.voice))))
  data=self.pool.call(self.model,lambda c:c.models.generate_content(model=self.model,contents=text,config=cfg).candidates[0].content.parts[0].inline_data.data)
  with wave.open(str(out),"wb") as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000);f.writeframes(data)
