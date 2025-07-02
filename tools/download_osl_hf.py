import os
import json
import argparse
from urllib.parse import urlparse
from huggingface_hub import hf_hub_download, snapshot_download, HfApi

def human_size(num):
    """Convert a file size in bytes to a human-readable string (B, KB, MB, GB, TB)."""
    for unit in ['B','KB','MB','GB','TB']:
        if num < 1024.0:
            return f"{num:3.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} PB"

def fix_hf_url(hf_url):
    """Convert a HuggingFace 'blob' URL to a 'resolve' URL for direct download."""
    return hf_url.replace("/blob/", "/resolve/")

def parse_hf_url(hf_url):
    """
    Parse a Hugging Face dataset file URL (supports 'blob' or 'resolve' forms).
    Returns (repo_id, revision, path_in_repo).
    """
    url = fix_hf_url(hf_url)
    parsed = urlparse(url)
    parts = parsed.path.strip("/").split("/")
    if "datasets" in parts:
        datasets_idx = parts.index("datasets")
        parts = parts[datasets_idx + 1:]
    if len(parts) < 4 or parts[2] != "resolve":
        raise ValueError(f"URL does not look like a valid HuggingFace dataset file URL: {url}")
    repo_id = f"{parts[0]}/{parts[1]}"
    revision = parts[3]
    path_in_repo = "/".join(parts[4:])
    return repo_id, revision, path_in_repo

def get_json_repo_folder(path_in_repo):
    """
    Return the folder containing the JSON inside the repo, or '' if at root.
    (Used to determine video relative paths inside the repo.)
    """
    folder = os.path.dirname(path_in_repo)
    return folder if folder and folder != '.' else ''

def main(osl_json_url, output_dir="downloaded_data", dry_run=False):
    api = HfApi()
    # Parse the HuggingFace dataset URL to extract repo and file info
    repo_id, revision, path_in_repo = parse_hf_url(osl_json_url)
    repo_json_folder = get_json_repo_folder(path_in_repo)

    print(f"⬇️  Downloading OSL JSON from {repo_id}@{revision}: {path_in_repo}")
    os.makedirs(output_dir, exist_ok=True)
    hf_json_path = hf_hub_download(
        repo_id=repo_id,
        repo_type="dataset",
        filename=path_in_repo,
        revision=revision,
        local_dir=output_dir,
        local_dir_use_symlinks=False,
    )
    print(f"  → Saved as {hf_json_path}")

    # Load the OSL JSON to extract video file paths
    with open(hf_json_path, "r") as f:
        osl = json.load(f)

    videos = osl.get("videos", [])
    print(f"Found {len(videos)} video files to download.")

    # Get list of repo-relative video paths
    repo_paths = [video["path"].lstrip("/") for video in videos]

    def repo_full_path(rel_path):
        """
        Ensure each video path is properly prefixed with the repo folder,
        so it's a valid repo-relative path for download.
        """
        if repo_json_folder and not rel_path.startswith(repo_json_folder + "/"):
            return os.path.join(repo_json_folder, rel_path)
        return rel_path

    # All unique, full repo-relative paths of videos to download
    allow_patterns = sorted(set([repo_full_path(rel_path) for rel_path in repo_paths]))

    if dry_run:
        # DRY RUN: Print the download and storage info without downloading
        try:
            info_obj = api.repo_info(repo_id=repo_id, revision=revision, repo_type="dataset", files_metadata=True)
            size_lookup = {f.rfilename: f.size for f in info_obj.siblings}
        except Exception as e:
            print(f"[ERROR] Could not fetch repo files info: {e}")
            size_lookup = {}

        total_size = 0
        missing_files = []
        for full_repo_path in allow_patterns:
            local_path = os.path.join(output_dir, full_repo_path)
            size = size_lookup.get(full_repo_path)
            if size is not None:
                size_str = human_size(size)
                total_size += size
            else:
                size_str = "Not found"
                missing_files.append(full_repo_path)
            print(f"[DRY RUN] Would download from repo: '{full_repo_path}' ({size_str})")
            print(f"[DRY RUN] Would save to local: '{local_path}'")

        print("-" * 48)
        print(f"Total estimated storage needed: {human_size(total_size)}")
        if missing_files:
            print(f"WARNING: {len(missing_files)} files not found in repo!")
            for f in missing_files:
                print(f"  - {f}")

    else:
        # ACTUAL DOWNLOAD: Download only the files listed in allow_patterns
        print(f"Downloading {len(allow_patterns)} files using snapshot_download...")
        snapshot_download(
            repo_id=repo_id,
            repo_type="dataset",
            revision=revision,
            local_dir=output_dir,
            allow_patterns=allow_patterns,
            max_workers=8,  # Parallel downloads (tune as needed)
        )
        print(f"  → All requested files downloaded to: {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True, help='URL of the OSL JSON file on HuggingFace')
    parser.add_argument('--output-dir', default="downloaded_data", help='Directory to store downloaded files')
    parser.add_argument('--dry-run', action='store_true', help='List files to download without downloading them, and show total storage needed')
    args = parser.parse_args()
    main(args.url, args.output_dir, dry_run=args.dry_run)
