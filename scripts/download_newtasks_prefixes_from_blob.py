import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AZCOPY = Path(os.environ.get("AZCOPY_EXE", r"E:\桌面\AAAI\azcopy\azcopy.exe"))
ACCOUNT_URL = "https://vigstandard.blob.core.windows.net/data"
REMOTE_ROOT = "v-jinpewang/yansiyu_workspace/See2Think"


PRESETS = {
    "no_render": [
        "newtasks/final600_gpt-5.5_vaot_no_render",
        "newtasks/final600_o3_vaot_no_render",
        "newtasks/final600_gemini-3.5-flash_vaot_no_render",
    ],
    "text_cot": [
        "newtasks/final600_gpt-5.5_text_cot",
        "newtasks/final600_o3_text_cot",
        "newtasks/final600_gemini-3.5-flash_text_cot",
    ],
    "wrong_render": [
        "newtasks/final600_gpt-5.5_vaot_wrong_render_floor",
        "newtasks/final600_o3_vaot_wrong_render_floor",
        "newtasks/final600_gemini-3.5-flash_vaot_wrong_render_floor",
        "newtasks/final600_gpt-5.5_vaot_wrong_render",
        "newtasks/final600_o3_vaot_wrong_render",
        "newtasks/final600_gemini-3.5-flash_vaot_wrong_render",
    ],
    "full": [
        "newtasks/final1154_gpt-5.5_vaot_full_floor",
        "newtasks/final1154_o3_vaot_full_floor",
        "newtasks/final1154_gemini-3.5-flash_vaot_full_floor",
    ],
}


def blob_url(prefix: str, sas: str) -> str:
    return f"{ACCOUNT_URL}/{REMOTE_ROOT}/{prefix.strip('/')}?{sas.lstrip('?')}"


def count_steps(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.rglob("steps.md"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", choices=sorted(PRESETS), required=True)
    parser.add_argument("--prefix", action="append", default=[])
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sas = os.environ.get("AZURE_STORAGE_SAS") or os.environ.get("VIGSTANDARD_DATA_SAS")
    if not sas and not args.dry_run:
        raise SystemExit("Missing SAS. Set AZURE_STORAGE_SAS first.")
    if not AZCOPY.exists() and not args.dry_run:
        raise SystemExit(f"azcopy not found: {AZCOPY}")

    prefixes = PRESETS[args.preset] + args.prefix
    summary = []
    for prefix in prefixes:
        dst = ROOT / prefix
        if args.overwrite and dst.exists():
            shutil.rmtree(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        url = blob_url(prefix, sas or "")
        print(f"DOWNLOAD {prefix}")
        print(f"  -> {dst}")
        if args.dry_run:
            summary.append({"prefix": prefix, "dst": str(dst), "steps": count_steps(dst), "dry_run": True})
            continue
        cmd = [
            str(AZCOPY),
            "copy",
            url,
            str(dst),
            "--recursive=true",
            "--overwrite=ifSourceNewer",
        ]
        proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        steps = count_steps(dst)
        summary.append(
            {
                "prefix": prefix,
                "dst": str(dst),
                "returncode": proc.returncode,
                "steps": steps,
                "output_tail": proc.stdout[-1200:],
            }
        )
        print(f"  returncode={proc.returncode} steps={steps}")

    out = ROOT / "outputs" / "final_tracking" / f"download_{args.preset}_prefixes_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
