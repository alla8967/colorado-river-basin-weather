"""Download DEM tiles listed in a manifest for terrain-feature generation.

This is only needed when rebuilding local terrain rasters rather than using processed terrain artifacts."""

from pathlib import Path
import argparse
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = PROJECT_DIR / "Raw_DEM" / "data.csv"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "Raw_DEM"
TIF_URL_PATTERN = re.compile(r"https?://[^,\s]+?\.tif(?:f)?", re.IGNORECASE)
DEFAULT_CHUNK_SIZE = 1024 * 1024


def extract_tif_urls(manifest_file):
    text = manifest_file.read_text(errors="replace")
    urls = TIF_URL_PATTERN.findall(text)
    unique_urls = []
    seen_urls = set()

    for url in urls:
        clean_url = url.strip()

        if clean_url in seen_urls:
            continue

        unique_urls.append(clean_url)
        seen_urls.add(clean_url)

    return unique_urls


def filename_from_url(url):
    parsed_url = urllib.parse.urlparse(url)
    filename = Path(parsed_url.path).name

    if not filename:
        raise ValueError(f"Could not determine a filename from URL: {url}")

    return filename


def format_bytes(byte_count):
    if byte_count is None:
        return "unknown size"

    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(byte_count)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"

        value /= 1024

    return f"{value:.1f} TB"


def get_expected_size(url, timeout):
    request = urllib.request.Request(url, method="HEAD")

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_length = response.headers.get("Content-Length")

            if content_length is None:
                return None

            return int(content_length)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def should_skip_existing(output_file, expected_size, overwrite):
    if overwrite or not output_file.exists():
        return False

    if expected_size is None:
        return output_file.stat().st_size > 0

    return output_file.stat().st_size == expected_size


def open_download_response(url, partial_file, timeout):
    headers = {}
    resume_from = 0

    if partial_file.exists():
        resume_from = partial_file.stat().st_size

    if resume_from > 0:
        headers["Range"] = f"bytes={resume_from}-"

    request = urllib.request.Request(url, headers=headers)
    response = urllib.request.urlopen(request, timeout=timeout)

    if resume_from > 0 and response.status != 206:
        response.close()
        partial_file.unlink()
        request = urllib.request.Request(url)
        response = urllib.request.urlopen(request, timeout=timeout)
        resume_from = 0

    return response, resume_from


def download_file(url, output_file, timeout, chunk_size, overwrite):
    partial_file = output_file.with_suffix(output_file.suffix + ".part")
    expected_size = get_expected_size(url, timeout)

    if should_skip_existing(output_file, expected_size, overwrite):
        print(f"SKIP existing: {output_file.name} ({format_bytes(output_file.stat().st_size)})")
        return "skipped"

    print(f"Downloading: {output_file.name} ({format_bytes(expected_size)})")
    start_time = time.time()

    response, resume_from = open_download_response(url, partial_file, timeout)
    mode = "ab" if resume_from > 0 else "wb"
    downloaded = resume_from
    last_report_time = start_time

    with response, partial_file.open(mode) as file:
        while True:
            chunk = response.read(chunk_size)

            if not chunk:
                break

            file.write(chunk)
            downloaded += len(chunk)
            now = time.time()

            if now - last_report_time >= 5:
                print(f"  {output_file.name}: {format_bytes(downloaded)} downloaded")
                last_report_time = now

    partial_file.rename(output_file)
    elapsed_seconds = max(time.time() - start_time, 0.001)
    speed = output_file.stat().st_size / elapsed_seconds
    print(f"  Done: {output_file.name} at {format_bytes(speed)}/s")
    return "downloaded"


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Download USGS DEM GeoTIFF tiles from a TNM cart CSV/TXT manifest."
    )
    parser.add_argument(
        "manifest",
        nargs="?",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to the TNM cart CSV/TXT manifest.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Folder where DEM .tif files should be saved.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only download the first N tiles. Useful for testing.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be downloaded without downloading files.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Redownload files even if they already exist.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Network timeout in seconds.",
    )
    return parser.parse_args()


def main():
    arguments = parse_arguments()

    if not arguments.manifest.exists():
        raise FileNotFoundError(f"Manifest file was not found: {arguments.manifest}")

    urls = extract_tif_urls(arguments.manifest)

    if arguments.limit is not None:
        urls = urls[:arguments.limit]

    if not urls:
        raise ValueError(f"No GeoTIFF URLs were found in: {arguments.manifest}")

    arguments.output_dir.mkdir(parents=True, exist_ok=True)

    print("DEM tile downloader")
    print("===================")
    print(f"Manifest: {arguments.manifest}")
    print(f"Output folder: {arguments.output_dir}")
    print(f"Tiles found: {len(urls)}")

    if arguments.dry_run:
        print()
        print("Dry run only. No files will be downloaded.")

        for url in urls[:10]:
            print(f"- {filename_from_url(url)}")

        if len(urls) > 10:
            print(f"...and {len(urls) - 10} more")

        return

    downloaded_count = 0
    skipped_count = 0
    failed_count = 0

    for index, url in enumerate(urls, start=1):
        output_file = arguments.output_dir / filename_from_url(url)

        print()
        print(f"[{index}/{len(urls)}]")

        if arguments.overwrite and output_file.exists():
            output_file.unlink()

        try:
            result = download_file(
                url,
                output_file,
                arguments.timeout,
                DEFAULT_CHUNK_SIZE,
                arguments.overwrite,
            )

            if result == "skipped":
                skipped_count += 1
            else:
                downloaded_count += 1
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            failed_count += 1
            print(f"FAILED: {output_file.name}")
            print(f"Reason: {error}", file=sys.stderr)

    print()
    print("Download summary")
    print("----------------")
    print(f"Downloaded: {downloaded_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Failed: {failed_count}")


if __name__ == "__main__":
    main()
