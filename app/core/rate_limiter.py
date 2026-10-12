import time
from collections import deque
from threading import Lock
class NoReadySlot(RuntimeError): pass
class Limiter:
 def __init__(self,n,rpm,window=65,cooldown=65): self.s=[{"calls":deque(),"until":0.,"reason":""} for _ in range(n)];self.rpm=rpm;self.window=window;self.cooldown=cooldown;self.cursor=0;self.lock=Lock()
 def _ready(self,i,now):
  x=self.s[i]
  while x["calls"] and x["calls"][0]<=now-self.window:x["calls"].popleft()
  if now>=x["until"]:x["reason"]=""
  return now>=x["until"] and len(x["calls"])<self.rpm
 def has_ready(self):
  with self.lock:return any(self._ready(i,time.monotonic()) for i in range(len(self.s)))
 def acquire(self,excluded=None):
  excluded=excluded or set()
  with self.lock:
   now=time.monotonic()
   for o in range(len(self.s)):
    i=(self.cursor+o)%len(self.s)
    if i not in excluded and self._ready(i,now):self.s[i]["calls"].append(now);self.cursor=(i+1)%len(self.s);return i
  raise NoReadySlot("Không có key sẵn sàng; hãy chờ RPM/cooldown.")
 def suspend(self,i,reason):
  with self.lock:self.s[i]["until"]=max(self.s[i]["until"],time.monotonic()+self.cooldown);self.s[i]["reason"]=reason
 def status(self):
  with self.lock:
   now=time.monotonic();out=[]
   for i,x in enumerate(self.s):
    ready=self._ready(i,now);times=([x["until"]] if x["until"]>now else [])+([x["calls"][0]+self.window] if len(x["calls"])>=self.rpm else [])
    out.append({"slot":i,"ready":ready,"calls_in_window":len(x["calls"]),"rpm":self.rpm,"ready_in_seconds":round(max(0,min(times)-now),1) if times else 0,"reason":x["reason"]})
   return out
