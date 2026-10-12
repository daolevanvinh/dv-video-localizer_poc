import json,time
from app.models.schema import Segment
class STT:
 def __init__(self,pool,model):self.pool=pool;self.model=model
 def run(self,path):
  def op(c):
   f=c.files.upload(file=str(path))
   while getattr(c.files.get(name=f.name).state,"name","") not in {"ACTIVE","FAILED"}:time.sleep(2)
   try:return c.models.generate_content(model=self.model,contents=[f,"Trả JSON duy nhất: {\"segments\":[{\"id\":0,\"start\":0.0,\"end\":2.0,\"source\":\"nguyên văn\"}]}. Chép chính xác lời nói/lời hát, giữ ngôn ngữ gốc, bỏ âm thanh vô nghĩa."]).text
   finally:c.files.delete(name=f.name)
  d=json.loads(self.pool.call(self.model,op));return [Segment(int(x.get("id",i)),float(x["start"]),float(x["end"]),x["source"]) for i,x in enumerate(d["segments"])]
