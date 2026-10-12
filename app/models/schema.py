from dataclasses import dataclass,asdict
@dataclass
class Segment:
 id:int;start:float;end:float;source:str;vi:str=""
 def dict(self):return asdict(self)
