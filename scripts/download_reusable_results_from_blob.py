import argparse
import csv
import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AZCOPY = Path(os.environ.get("AZCOPY_EXE", r"E:\桌面\AAAI\azcopy\azcopy.exe"))
DEFAULT_ACCOUNT_URL = "https://vigstandard.blob.core.windows.net/data"
STORAGE_PREFIX = "/storage/"


SETTING_TARGETS = {
    "text_only": ("reusable_text_only_manifest.csv", "text_only"),
    "optional_with_generated_image": (
        "reusable_optional_with_generated_image_manifest.csv",
        "optional_with_generated_image",
    ),
    "valid_wrong_render_step1": (
        "reusable_valid_wrong_render_step1_manifest.csv",
        "valid_wrong_render_step1",
    ),
}


def shell_quote_for_log(value: str) -> str:
    if "sig=" in value:
        return value.split("sig=", 1)[0] + "sig=<hidden>"
    return value


def blob_url_from_storage_path(sample_dir: str, sas: str, account_url: str) -> str:
    normalized = sample_dir.replace("\\", "/")
    if not normalized.startswith(STORAGE_PREFIX):
        raise ValueError(f"sample_dir is not a /storage path: {sample_dir}")
    blob_path = normalized[len(STORAGE_PREFIX) :].lstrip("/")
    sas = sas.lstrip("?")
    return f"{account_url.rstrip('/')}/{blob_path}?{sas}"


def local_target_dir(row: dict, output_root: Path, setting_name: str) -> Path:
    model = row["model"].replace(":", "-")
    rel = Path(*row["relative_source_dir"].replace("\\", "/").split("/"))
    sample_id = str(row["sample_id"])
    old_dir_name = Path(row["sample_dir"].replace("\\", "/")).name
    # Use manifest fields for stable lookup, but keep the original sample folder name.
    return output_root / model / setting_name / rel / old_dir_name if old_dir_name != sample_id else output_root / model / setting_name / rel / sample_id


def valid_local_dir(path: Path, require_render: bool) -> bool:
    steps = path / "steps.md"
    if not (steps.exists() and steps.stat().st_size > 0):
        return False
    if not require_render:
        return True
    for item in path.glob("p*"):
        if item.name == "p0.png":
            continue
        if item.suffix.lower() in {".png", ".jpg", ".jpeg"} and item.stat().st_size > 0:
            return True
    return False


def read_rows(manifest: Path, models: set[str] | None, limit: int | None) -> list[dict]:
    rows = []
    with manifest.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if models and row.get("model") not in models:
                continue
            rows.append(row)
            if limit is not None and len(rows) >= limit:
                break
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--settings",
        nargs="+",
        default=list(SETTING_TARGETS),
        choices=list(SETTING_TARGETS),
    )
    parser.add_argument("--models", nargs="*", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output-root", default="newtasks_reused")
    parser.add_argument("--manifest-root", default="outputs/final_tracking")
    parser.add_argument("--account-url", default=DEFAULT_ACCOUNT_URL)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    sas = os.environ.get("AZURE_STORAGE_SAS") or os.environ.get("VIGSTANDARD_DATA_SAS")
    if not sas and not args.dry_run:
        raise SystemExit(
            "Missing SAS. Set AZURE_STORAGE_SAS to the blob SAS token first."
        )
    if not AZCOPY.exists() and not args.dry_run:
        raise SystemExit(f"azcopy not found: {AZCOPY}")

    manifest_root = ROOT / args.manifest_root
    output_root = ROOT / args.output_root
    output_root.mkdir(parents=True, exist_ok=True)
    models = set(args.models) if args.models else None

    summary = []
    for setting in args.settings:
        manifest_name, target_setting = SETTING_TARGETS[setting]
        manifest = manifest_root / manifest_name
        rows = read_rows(manifest, models, args.limit)
        require_render = setting != "text_only"

        downloaded = 0
        skipped = 0
        failed = []
        for i, row in enumerate(rows, 1):
            dst = local_target_dir(row, output_root, target_setting)
            if dst.exists() and not args.overwrite and valid_local_dir(dst, require_render):
                skipped += 1
                continue
            if dst.exists() and args.overwrite:
                shutil.rmtree(dst)
            dst.parent.mkdir(parents=True, exist_ok=True)

            src = blob_url_from_storage_path(row["sample_dir"], sas or "", args.account_url)
            cmd = [
                str(AZCOPY),
                "copy",
                src,
                str(dst),
                "--recursive=true",
                "--overwrite=ifSourceNewer",
            ]
            if args.dry_run:
                print(f"[DRY] {shell_quote_for_log(src)} -> {dst}")
                continue

            print(f"[{setting}] {i}/{len(rows)} {row['model']} {row['relative_source_dir']}:{row['sample_id']}")
            proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if proc.returncode == 0 and valid_local_dir(dst, require_render):
                downloaded += 1
            else:
                failed.append(
                    {
                        "model": row.get("model"),
                        "setting": setting,
                        "relative_source_dir": row.get("relative_source_dir"),
                        "sample_id": row.get("sample_id"),
                        "dst": str(dst),
                        "returncode": proc.returncode,
                        "output_tail": proc.stdout[-1200:],
                    }
                )

        summary.append(
            {
                "setting": setting,
                "rows": len(rows),
                "downloaded": downloaded,
                "skipped_existing": skipped,
                "failed": len(failed),
            }
        )
        fail_path = output_root / f"download_failed_{setting}.json"
        fail_path.write_text(json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_path = output_root / "download_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(summary_path)


if __name__ == "__main__":
    main()
