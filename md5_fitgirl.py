import hashlib
import os
import psutil
from tqdm import tqdm
from pathlib import Path
import colorama
import argparse
import sys

def get_max_chunk_size():
    """Get an optimal chunk size based on available system memory."""
    available_memory = psutil.virtual_memory().available
    return min(available_memory // 2, 6 * 1024**3)

def md5_hash_file(path, chunk_size=None):
    """Generate MD5 hash for a file with progressive updates."""
    md5 = hashlib.md5()
    total_size = os.path.getsize(path)
    if chunk_size is None:
        chunk_size = get_max_chunk_size()
    read_size = min(chunk_size, 8 * 1024**2)

    with open(path, 'rb') as f, tqdm(total=total_size, unit='B', unit_scale=True,
                                     desc=os.path.basename(path), colour='green') as pbar:
        bytes_read = 0
        while bytes_read < total_size:
            chunk = f.read(read_size)
            if not chunk:
                break
            md5.update(chunk)
            bytes_read += len(chunk)
            pbar.update(len(chunk))
    return md5.hexdigest()

def parse_md5_file(md5_file_path):
    """Parse an MD5 file and return the list of checksums and file paths."""
    entries = []
    with open(md5_file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(';'):
                continue
            try:
                checksum, relative_path = line.split(' *')
                # Normalize path to use Unix-style separators
                relative_path = relative_path.replace('\\', '/')
                entries.append((checksum.lower(), os.path.normpath(relative_path)))
            except ValueError:
                print(f"Skipping invalid line: {line}")
    return entries

def find_md5_file(target: Path) -> Path | None:
    """Find a .md5 file in the given path or its md5/ subfolder."""
    if target.is_file() and target.suffix == ".md5":
        return target

    if target.is_dir():
        # Check directly inside the folder
        md5_files = list(target.glob("*.md5"))
        if md5_files:
            return md5_files[0]

        # Check md5/ subfolder
        md5_subfolder = target / "md5"
        if md5_subfolder.exists() and md5_subfolder.is_dir():
            md5_files = list(md5_subfolder.glob("*.md5"))
            if md5_files:
                return md5_files[0]
    return None

def main():
    """Main function to process the command-line arguments and verify MD5 hashes."""
    parser = argparse.ArgumentParser(description="Verify files against an .md5 checksum list.")
    parser.add_argument("path", type=Path, help="Path to .md5 file or folder containing one.")
    args = parser.parse_args()

    colorama.init()
    fore = colorama.Fore

    # Resolve the target path and ensure it's cross-platform safe
    target_path = args.path.resolve()

    # Find the .md5 file
    md5_file = find_md5_file(target_path)
    if not md5_file or not md5_file.exists():
        print(f"{fore.RED}Error: No .md5 file found at '{target_path}'{fore.RESET}")
        sys.exit(1)

    print(f"{fore.YELLOW}Using MD5 file: {md5_file.relative_to(Path.cwd())}{fore.RESET}")
    entries = parse_md5_file(md5_file)

    Missing_files = 0
    ok_files = 0
    failed_files = 0

    # Process each file and verify against its expected checksum
    for expected_hash, rel_path in entries:
        # Adjust relative path to work with WSL
        abs_path = (md5_file.parent / rel_path).resolve()
        if not abs_path.exists():
            print(f"{fore.CYAN}[MISSING] {rel_path}{fore.RESET}")
            Missing_files += 1
            continue

        actual_hash = md5_hash_file(abs_path)
        if actual_hash == expected_hash:
            print(f"{fore.GREEN}[ OK ] {rel_path}{fore.RESET}")
            ok_files += 1
        else:
            print(f"{fore.RED}[FAIL] {rel_path}{fore.RESET}")
            print(f"{fore.RED}  Expected: {expected_hash}{fore.RESET}")
            print(f"{fore.RED}  Found:    {actual_hash}{fore.RESET}")
            failed_files += 1

    total_files_checked = ok_files + failed_files

    print(
        f"{fore.YELLOW}Total Checked: {fore.GREEN}{total_files_checked} "
        f"{fore.RESET}/{fore.CYAN}{len(entries)}{fore.RESET}\n"
        f"    {fore.GREEN}OK: {ok_files}{fore.RESET}\n"
        f"    {fore.RED}FAILED: {failed_files}{fore.RESET}\n"
        f"    {fore.CYAN}MISSING: {Missing_files}{fore.RESET}\n"
    )

if __name__ == "__main__":
    main()
