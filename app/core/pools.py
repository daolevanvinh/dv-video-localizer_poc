import os
from google import genai
from app.core.rate_limiter import Limiter, NoReadySlot

RATE = ("429", "resource_exhausted", "quota", "rate limit", "too many requests")
def is_rate(error): return any(x in str(error).lower() for x in RATE)

class ModelPoolBase:
 def __init__(self, keys, rpm, window, cooldown):
  self.keys=keys; self.rpm=rpm; self.window=window; self.cooldown=cooldown; self.limiters={}
 def limiter(self, model):
  if model not in self.limiters:self.limiters[model]=Limiter(len(self.keys),self.rpm,self.window,self.cooldown)
  return self.limiters[model]
 def ready(self, model): return self.limiter(model).has_ready()
 def status(self):
  rows=[]
  for model,limiter in self.limiters.items():
   for row in limiter.status():rows.append({**row,"model":model})
  return rows

class ApiPool(ModelPoolBase):
 def call(self, model, fn):
  limiter=self.limiter(model); tried=set(); last=None
  while len(tried)<len(self.keys):
   i=limiter.acquire(tried); tried.add(i)
   try:return fn(genai.Client(api_key=self.keys[i]))
   except Exception as error:
    last=error; limiter.suspend(i,"429/quota" if is_rate(error) else type(error).__name__)
  raise NoReadySlot(f"Không còn media key dùng được cho model {model}: {last}")

class CliPool(ModelPoolBase):
 def take(self, model, tried):
  i=self.limiter(model).acquire(tried); return i,self.keys[i]
 def env(self,key):
  env=os.environ.copy(); env["GEMINI_API_KEY"]=key; env["NO_COLOR"]="1"; return env
 def suspend(self,model,index,reason):self.limiter(model).suspend(index,reason)
