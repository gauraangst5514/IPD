"""Run in a network-enabled Terminal. Each acquisition reports its actual outcome."""
import argparse, json, pathlib, subprocess, sys, shutil, importlib.util
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(); p.add_argument('--generali',action='store_true'); p.add_argument('--lightglue',action='store_true'); args=p.parse_args()
    results={}
    def run(name,command):
        process=subprocess.run(command,cwd=ROOT)
        results[name]={'success':process.returncode==0,'returncode':process.returncode}
        return process.returncode == 0
    run('tqvcd',[sys.executable,'research/scripts/acquire_tqvcd.py'])
    run('resnet18',[sys.executable,'-c','from torchvision.models import resnet18,ResNet18_Weights; resnet18(weights=ResNet18_Weights.DEFAULT)'])
    def install(name, package):
        uv=shutil.which('uv')
        if uv:
            command=[uv,'pip','install','--python',sys.executable,package]
        elif importlib.util.find_spec('pip'):
            command=[sys.executable,'-m','pip','install',package]
        else:
            if not run('bootstrap_pip',[sys.executable,'-m','ensurepip']):
                results[name]={'success':False,'status':'package_manager_missing'}
                return False
            command=[sys.executable,'-m','pip','install',package]
        return run(name,command)
    if args.lightglue:
        if install('lightglue_install','git+https://github.com/cvg/LightGlue.git'):
            run('lightglue_weights',[sys.executable,'-c',"from lightglue import SuperPoint,LightGlue; SuperPoint(); LightGlue(features='superpoint')"])

    if args.generali:
        target=ROOT/'data/raw/generali'; target.mkdir(parents=True,exist_ok=True)
        if install('gdown_install','gdown>=5.2,<6'):
            run('generali_released_folder',[sys.executable,'-m','gdown','--folder','https://drive.google.com/drive/folders/1VKMuGIejowfg7xylZsPKJ9VGdaxNWTYv','-O',str(target)])
    results['cddm']={'success':False,'status':'author_license_form_required','source':'https://github.com/SCUT-CCNL/CDDM'}
    results['cardd']={'success':False,'status':'author_license_form_required','source':'https://cardd-ustc.github.io/'}
    results['generali_note']='Download is not evaluation: inspect archive labels, real/synthetic subsets, license and OSNet architecture before loading checkpoints.'
    out=ROOT/'research/results';out.mkdir(exist_ok=True)
    (out/'acquisition_status.json').write_text(json.dumps(results,indent=2)); print(json.dumps(results,indent=2))
if __name__=='__main__':main()
