import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)

def csv(name): return [x.strip() for x in os.getenv(name,"").split(",") if x.strip()]
@dataclass(frozen=True)
class Settings:
 media_keys:list[str]; translate_keys:list[str]; stt_model:str; tts_model:str; tts_voice:str; translate_model:str; cli_command:str; api_rpm:int; cli_rpm:int; window:float; cooldown:float; demucs:bool; demucs_model:str; demucs_device:str
def load_settings():
 media=csv("GEMINI_API_KEYS") or csv("GEMINI_API_KEY")
 trans=csv("GEMINI_TRANSLATE_KEYS")
 if not media: raise RuntimeError("Set GEMINI_API_KEYS")
 if not trans: raise RuntimeError("Set GEMINI_TRANSLATE_KEYS")
 return Settings(media,trans,os.getenv("GEMINI_STT_MODEL","gemini-3.8-flash"),os.getenv("GEMINI_TTS_MODEL","gemini-2.5-flash-preview-tts"),os.getenv("GEMINI_TTS_VOICE","Kore"),os.getenv("GEMMA_TRANSLATE_MODEL","gemma-4-31b-it"),os.getenv("GEMINI_CLI_COMMAND","gemini"),int(os.getenv("GEMINI_API_RPM","2")),int(os.getenv("GEMINI_CLI_RPM","2")),float(os.getenv("RATE_WINDOW_SECONDS","65")),float(os.getenv("RATE_COOLDOWN_SECONDS","65")),os.getenv("DEMUCS_ENABLED","1").lower() not in {"0","false"},os.getenv("DEMUCS_MODEL","htdemucs"),os.getenv("DEMUCS_DEVICE","cpu"))
