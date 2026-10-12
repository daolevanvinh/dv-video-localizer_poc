import subprocess
def run(c):
 p=subprocess.run(c,capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr[-4000:])
def duration(p):
 q=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(p)],capture_output=True,text=True);return float(q.stdout)
def render(video,items,out):
 total=duration(video);n=out.with_suffix(".wav");cmd=["ffmpeg","-y","-f","lavfi","-i",f"anullsrc=r=24000:cl=mono:d={total}"]
 for _,a in items:cmd += ["-i",str(a)]
 fs=[];labs=[]
 for j,(s,_) in enumerate(items,1):lab=f"d{j}";fs.append(f"[{j}:a]adelay={int(s.start*1000)}|{int(s.start*1000)}[{lab}]");labs.append(f"[{lab}]")
 fs.append(f"[0:a]{''.join(labs)}amix=inputs={len(labs)+1}:duration=first:normalize=0[o]");run(cmd+["-filter_complex",";".join(fs),"-map","[o]",str(n)]);run(["ffmpeg","-y","-i",str(video),"-i",str(n),"-map","0:v:0","-map","1:a:0","-c:v","copy","-c:a","aac","-shortest",str(out)])
