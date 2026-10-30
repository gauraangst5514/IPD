"""Render a narrated walkthrough from actual captured browser states.

This is an edited walkthrough of screenshots, not a continuous screen recording.
Speech uses the installed macOS Aman voice. No user voice is cloned or recorded.
"""
from pathlib import Path
import wave
import json
import subprocess
import textwrap
from PIL import Image,ImageDraw,ImageFont
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1]
SCENES=[
('01_dashboard.png','Available investigator checks','The dashboard reports the checks that are actually installed. Vehicle make verification, plate OCR, TruFor forensic diagnostics, and historical photograph retrieval are now available. These are research aids for an investigator, and do not establish fraudulent intent.'),
('02_retrieval.png','Historical photograph retrieval','Photo retrieval is restricted to assessors and administrators. The gallery shown here is a local research demonstration gallery. It is separate from the claim database and from the frozen offline evaluation corpus.'),
('03_query.png','Select an original photograph','Select a photograph and choose three, five, or ten candidates. The application sends the bytes through the authenticated backend to the pretrained OSNet embedding model. The query preview helps the assessor confirm the selected evidence.'),
('04_candidates.png','Review ranked evidence','The model ranks historical photographs by cosine similarity. Similarity is not a probability. The cards include local feature counts and damage-region diagnostics. An unavailable detector result remains explicit instead of being replaced with an invented score.'),
('05_correspondence.png','Inspect matching local features','Expand correspondence inspection to see keypoints and connecting lines between the query and a candidate. Coordinates are scaled to the rendered photographs. Matches may come from background or undamaged bodywork, so they do not prove the same physical damage.'),
('06_lines_hidden.png','Compare without overlays','The line toggle hides the overlay so the photographs can be inspected directly. Damage masking measures sensitivity to an artificial perturbation. It does not establish a causal explanation, image authenticity, or an automatic insurance decision.'),
('07_ingestion.png','Index history and retain limitations','Assessors can add photographs to the historical gallery. Exact duplicates are detected, and images survive a restart. The completed LightGlue experiment showed no improvement. Abstention and external sample tests are documented with uncertainty, and the final decision stays with the human investigator.')]

def main():
    target=ROOT/'submission';frames=target/'demo_frames';work=target/'demo_render';work.mkdir(exist_ok=True)
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',27)
    heading=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf',35)
    small=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',19)
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe();clips=[];transcript=[];elapsed=0
    def timestamp(seconds):
        ms=round(seconds*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
    subtitles=[]
    for i,(filename,title,speech) in enumerate(SCENES,1):
        image=Image.open(frames/filename).convert('RGB');image.thumbnail((600,650))
        canvas=Image.new('RGB',(1280,800),'#0b1220');draw=ImageDraw.Draw(canvas)
        draw.text((32,20),'INTELLICLAIM · RESEARCH PROTOTYPE',font=small,fill='#94a3b8')
        canvas.paste(image,(25+(600-image.width)//2,85))
        y=105
        for line in textwrap.wrap(title,25):draw.text((670,y),line,font=heading,fill='white');y+=46
        y+=25
        for line in textwrap.wrap(speech,38):draw.text((670,y),line,font=font,fill='#cbd5e1');y+=37
        draw.text((32,760),f'{i} / {len(SCENES)} · Captured app screens · Synthesized narration · Investigator review required',font=small,fill='#94a3b8')
        png=work/f'{i:02}.png';canvas.save(png)
        text=work/f'{i:02}.txt';text.write_text(speech)
        audio=work/f'{i:02}.aiff'
        subprocess.run(['say','-v','Aman','-r','155','-f',str(text),'-o',str(audio)],check=True)
        wav=work/f'{i:02}.wav'
        subprocess.run([ffmpeg,'-y','-i',str(audio),'-ac','1','-ar','22050',str(wav)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        audio=wav
        with wave.open(str(audio),'rb') as recording:duration=recording.getnframes()/recording.getframerate()+.6
        clip=work/f'{i:02}.mp4'
        subprocess.run([ffmpeg,'-y','-loop','1','-i',str(png),'-i',str(audio),'-t',str(duration),'-vf','fps=24,format=yuv420p','-c:v','libx264','-preset','fast','-threads','2','-crf','23','-c:a','aac','-b:a','128k','-af','apad','-movflags','+faststart',str(clip)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        clips.append(clip);transcript.append(f'{i}. {title}\n\n{speech}')
        subtitles.append(f'{i}\n{timestamp(elapsed)} --> {timestamp(elapsed+duration)}\n{speech}\n');elapsed+=duration
    concat=work/'concat.txt';concat.write_text('\n'.join("file '"+str(p)+"'" for p in clips))
    output=target/'IntelliClaim_Narrated_Walkthrough.mp4'
    subprocess.run([ffmpeg,'-y','-f','concat','-safe','0','-i',str(concat),'-c','copy','-movflags','+faststart',str(output)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    (target/'IntelliClaim_Narration_Transcript.md').write_text('# Narrated walkthrough\n\nEdited from actual browser screen captures, with synthesized Aman narration. This is not a continuous screen recording.\n\n'+'\n\n'.join(transcript))
    (target/'IntelliClaim_Narrated_Walkthrough.srt').write_text('\n'.join(subtitles))
    (target/'narrated_demo_manifest.json').write_text(json.dumps({'file':str(output.relative_to(ROOT)),'seconds':elapsed,'scenes':len(SCENES),'method':'Actual browser screenshots with synthesized macOS Aman narration; edited still-screen walkthrough','continuous_screen_recording':False,'voice_cloning':False},indent=2))
    print(output,round(elapsed,1),'seconds')

if __name__=='__main__':main()
