import shutil,uuid
from pathlib import Path
from fastapi import FastAPI,UploadFile,File,HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import load_settings
from app.core.pools import ApiPool,CliPool
from app.services.stt import STT
from app.services.translate import Translator
from app.services.tts import TTS
from app.services.media import render
import traceback
S=load_settings();media=ApiPool(S.media_keys,S.api_rpm,S.window,S.cooldown);trans=CliPool(S.translate_keys,S.cli_rpm,S.window,S.cooldown);stt=STT(media,S.stt_model);tr=Translator(trans,S.translate_model,S.cli_command);tts=TTS(media,S.tts_model,S.tts_voice)
app=FastAPI()
@app.get('/api/health')
def health():
 can=media.ready(S.stt_model) and media.ready(S.tts_model) and trans.ready(S.translate_model)
 return {"ok":True,"can_process":can,"api_keys":media.status(),"translate_keys":trans.status(),"required_models":{"stt":S.stt_model,"tts":S.tts_model,"translate":S.translate_model}}
@app.post('/api/process')
async def process(video:UploadFile=File(...)):
 if not media.ready(S.stt_model) or not media.ready(S.tts_model) or not trans.ready(S.translate_model):raise HTTPException(429,"Không có key sẵn sàng cho đủ ba model STT, TTS và translate.")
 jid=uuid.uuid4().hex[:12];work=Path('outputs')/jid;work.mkdir(parents=True);src=Path('uploads')/f'{jid}.mp4';src.parent.mkdir(exist_ok=True)
 with src.open('wb') as f:shutil.copyfileobj(video.file,f)
 try:
  segs=tr.run(stt.run(src));items=[]
  for s in segs:
   if s.vi:a=work/f'{s.id}.wav';tts.run(s.vi,a);items.append((s,a))
  out=work/'output.mp4';render(src,items,out);return {"job_id":jid,"video_url":f'/api/jobs/{jid}/video',"segments":[s.dict() for s in segs]}
 except Exception as e:
    traceback.print_exc()
    raise HTTPException(
        500,
        f"{type(e).__name__}: {e}"
    )
@app.get('/api/jobs/{jid}/video')
def video(jid:str):return FileResponse(Path('outputs')/jid/'output.mp4',media_type='video/mp4')
if Path('frontend/dist').exists():app.mount('/',StaticFiles(directory='frontend/dist',html=True),name='ui')
