"""Flask의 /static URL을 유지하면서 Vercel CDN에 정적 파일을 배치한다."""
from pathlib import Path
import shutil


def main():
    base = Path(__file__).resolve().parent.parent
    shutil.copytree(base / "gadong" / "static", base / "public" / "static", dirs_exist_ok=True)


if __name__ == "__main__":
    main()
