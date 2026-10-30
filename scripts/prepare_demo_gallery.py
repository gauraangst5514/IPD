"""Keep mutable demo ingestion separate from downloaded evaluation images."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]
def prepare():
    source=ROOT/'data/raw/generali/extracted/paper/test_papers_2.1.0_for_repo'
    if not source.exists():source=ROOT/'data/raw/tqvcd'
    target=ROOT/'var/retrieval-gallery';target.mkdir(parents=True,exist_ok=True)
    for path in source.rglob('*'):
        if path.suffix.lower() not in {'.jpg','.jpeg','.png','.webp'}:continue
        dest=target/path.relative_to(source);dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():shutil.copy2(path,dest)
    return target
if __name__=='__main__':print(prepare())
