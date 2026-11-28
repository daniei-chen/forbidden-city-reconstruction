"""Encode and validate the actual 960-frame v5 render, preserving its ledger.

Run with ordinary Python and ffmpeg/ffprobe on PATH. A complete file hash
ledger, source-model identity and full decoder pass are required before the
pending MP4 is renamed to the requested delivery filename.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def run(command):
    result=subprocess.run([str(x) for x in command],capture_output=True,text=True,encoding='utf8',errors='replace')
    if result.returncode:
        raise RuntimeError('Media command failed: '+result.stderr[-5000:])
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('frames',type=Path)
    parser.add_argument('project',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    frames,project,output=args.frames.resolve(),args.project.resolve(),args.output.resolve()
    pending=output.with_name(output.stem+'.pending.mp4')
    validation=output.with_suffix('.validation.json')
    contact=output.with_name(output.stem+'_contact.png')
    if any(p.exists() for p in (output,pending,validation,contact)):
        parser.error('Preserve existing media and inspection evidence; use a new filename.')
    ffmpeg,ffprobe=shutil.which('ffmpeg'),shutil.which('ffprobe')
    if not ffmpeg or not ffprobe:
        parser.error('Both ffmpeg and ffprobe must be available on PATH.')
    ledger_path=frames/'frame_ledger.json'
    ledger=json.loads(ledger_path.read_text(encoding='utf8'))
    profile=ledger['profile']
    audit=json.loads((frames/'render_input_route_audit.json').read_text(encoding='utf8'))
    expected=list(range(1,961))
    records=sorted(ledger['frames'],key=lambda r:r['frame'])
    if not ledger['complete'] or [r['frame'] for r in records]!=expected:
        raise RuntimeError('The native frame sequence is incomplete or contains duplicate receipts.')
    if profile['fps']!=24 or profile['frame_start']!=1 or profile['frame_end']!=960:
        raise RuntimeError('The sequence profile is not the expected 40-second, 24fps route.')
    if digest(project)!=profile['project_sha256'] or not audit['passed'] or audit['frames']!=960:
        raise RuntimeError('Source-model identity or actual-input navigation audit failed.')
    for record in records:
        image=frames/f"{record['frame']:04d}.png"
        if record['file']!=image.name or digest(image)!=record['sha256']:
            raise RuntimeError('The actual frame does not match its render receipt: '+image.name)
    print('FABRIC_VIDEO_INPUT_VERIFIED',len(records),flush=True)
    output.parent.mkdir(parents=True,exist_ok=True)
    run([ffmpeg,'-hide_banner','-loglevel','error','-n','-framerate','24','-start_number','1',
         '-i',frames/'%04d.png','-frames:v','960','-c:v','libx264','-preset','slow','-crf','18',
         '-pix_fmt','yuv420p','-movflags','+faststart','-an',pending])
    probe=json.loads(run([ffprobe,'-v','error','-select_streams','v:0','-count_frames',
          '-show_entries','stream=codec_name,width,height,avg_frame_rate,nb_read_frames,duration:format=duration',
          '-of','json',pending]).stdout)
    stream=probe['streams'][0]
    checks={'all_960_render_frame_hashes_match':True,'source_model_hash_matches':True,
            'actual_render_input_route_passed':True,
            'encoded_frames_960':int(stream.get('nb_read_frames','0'))==960,
            'encoded_rate_24fps':stream['avg_frame_rate']=='24/1',
            'encoded_resolution_matches':[stream['width'],stream['height']]==[profile['width'],profile['height']],
            'encoded_duration_40_seconds':abs(float(probe['format']['duration'])-40.)<.002}
    decoded=run([ffmpeg,'-hide_banner','-v','error','-i',pending,'-f','null','-'])
    checks['complete_file_decodes_without_reported_errors']=not decoded.stderr.strip()
    if not all(checks.values()):
        raise RuntimeError('Encoded media verification failed: '+str(checks))
    run([ffmpeg,'-hide_banner','-loglevel','error','-n','-i',pending,
         '-vf',r'select=not(mod(n\,60)),scale=480:270,tile=4x4',
         '-frames:v','1',contact])
    pending.replace(output)
    report={'passed':True,'verified_at':datetime.now().astimezone().isoformat(),
            'video':output.name,'video_sha256':digest(output),'video_bytes':output.stat().st_size,
            'project':project.name,'project_sha256':profile['project_sha256'],
            'frame_ledger_sha256':digest(ledger_path),'render_profile':profile,'checks':checks,'probe':probe,
            'contact_sheet':contact.name,'contact_sheet_sha256':digest(contact),
            'contact_sheet_encoded_frame_indices_zero_based':list(range(0,960,60)),
            'continuous_human_playback_review_complete':False,
            'whole_city_pixel_perfect_reconstruction_proven':False,
            'scope':'Complete-frame identity, encoded duration/resolution/rate and full decode; visual temporal review is recorded separately.'}
    validation.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('FABRIC_VIDEO_ENCODED_VERIFIED',str(output),flush=True)


if __name__=='__main__':
    main()
