import hashlib
from pathlib import Path


FILES = [
    Path("yijing-page/index.html"),
    Path("index.html"),
    Path("cloudflare-upload/index.html"),
]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    hashes = {path.as_posix(): sha256(path) for path in FILES}
    first = next(iter(hashes.values()))
    for path, digest in hashes.items():
        print(f"{digest}  {path}")
    if any(digest != first for digest in hashes.values()):
        raise SystemExit("Frontend entry files are out of sync.")
    print("Frontend entry files are in sync.")


if __name__ == "__main__":
    main()
