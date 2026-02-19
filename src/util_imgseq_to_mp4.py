#!/usr/bin/env python3
"""
Convert an image sequence (`img_%04d.png`) to MP4 with a title slate.
"""

import argparse
import os
import re
import shutil
import subprocess
import tempfile
from datetime import date, datetime


DEFAULT_FPS = 24
DEFAULT_TITLE_SECONDS = 5
FRAME_PATTERN = re.compile(r"^(?P<base>.+)\.(?P<frame>\d{4,5})\.png$")
SLATE_OUTPUT = True
LOGO_SCALE = 0.25


def fail(message: str, exit_code: int = 1) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(exit_code)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert img_%04d.png sequence to MP4 with title slate"
    )
    parser.add_argument(
        "--path-src",
        default=os.getcwd(),
        help="Source directory containing img_%04d.png (default: current working directory)",
    )
    parser.add_argument(
        "--movie-title",
        default="scene description",
        help="Movie title metadata and slate title (default: scene description)",
    )
    parser.add_argument(
        "--font-file",
        default=None,
        help="Optional path to a .ttf/.otf font file for slate text",
    )
    return parser.parse_args()


def validate_source(path_src: str, wf_img_dir: str) -> str:
    path_src_abs = os.path.abspath(path_src)
    if not os.path.isdir(path_src_abs):
        fail(f"path_src directory does not exist: {path_src_abs}")

    wf_real = os.path.realpath(wf_img_dir)
    src_real = os.path.realpath(path_src_abs)
    if src_real != wf_real and not src_real.startswith(wf_real + os.sep):
        fail(f"path_src must be a subdirectory of WF_IMG_DIR\n  WF_IMG_DIR={wf_real}\n  path_src={src_real}")

    return path_src_abs


def find_sequence_frames(path_src: str) -> tuple[str, int, list[int]]:
    frame_numbers: list[int] = []
    base_name: str | None = None
    frame_width: int | None = None
    for file_name in os.listdir(path_src):
        match = FRAME_PATTERN.match(file_name)
        if match:
            base = match.group("base")
            frame_text = match.group("frame")
            if base_name is None:
                base_name = base
                frame_width = len(frame_text)
            elif base != base_name:
                fail(
                    "Multiple base names detected in sequence directory\n"
                    f"  base A: {base_name}\n"
                    f"  base B: {base}\n"
                    f"  source: {path_src}"
                )
            elif frame_width != len(frame_text):
                fail(
                    "Mixed frame padding widths detected in sequence directory\n"
                    f"  base: {base_name}\n"
                    f"  widths: {frame_width} and {len(frame_text)}\n"
                    f"  source: {path_src}"
                )
            frame_numbers.append(int(frame_text))

    if not frame_numbers or base_name is None or frame_width is None:
        fail(f"No frames matching [anytext].####.png found in: {path_src}")

    frame_numbers.sort()
    return base_name, frame_width, frame_numbers


def summarize_missing(values: list[int]) -> str:
    ranges: list[str] = []
    start = values[0]
    end = values[0]
    for value in values[1:]:
        if value == end + 1:
            end = value
            continue
        ranges.append(f"{start:04d}" if start == end else f"{start:04d}-{end:04d}")
        start = value
        end = value
    ranges.append(f"{start:04d}" if start == end else f"{start:04d}-{end:04d}")
    return ", ".join(ranges)


def validate_contiguous_frames(frame_numbers: list[int], path_src: str, base_name: str, frame_width: int) -> tuple[int, int]:
    start = frame_numbers[0]
    end = frame_numbers[-1]
    frame_set = set(frame_numbers)
    missing = [number for number in range(start, end + 1) if number not in frame_set]
    if missing:
        sample = ", ".join(f"{base_name}.{number:0{frame_width}d}.png" for number in missing[:20])
        missing_ranges = summarize_missing(missing)
        fail(
            "Missing frames detected in sequence:\n"
            f"  source: {path_src}\n"
            f"  expected frame range: {start:04d}-{end:04d}\n"
            f"  missing frame ranges: {missing_ranges}\n"
            f"  sample missing files: {sample}"
        )

    return start, end


def derive_names(path_src: str, wf_img_dir: str, job_dir: str) -> tuple[str, str, str]:
    path_src_parts = path_src.split('/')
    wf_parts = wf_img_dir.split('/')

    project_name = os.path.basename(os.path.normpath(job_dir))

    idx_scene = len(wf_parts) + 2
    if idx_scene >= len(path_src_parts):
        fail(
            "Unable to derive scene_name from path_src using WF_IMG_DIR offset\n"
            f"  WF_IMG_DIR={wf_img_dir}\n"
            f"  path_src={path_src}"
        )
    scene_name = path_src_parts[idx_scene]

    path_src_norm_parts = os.path.normpath(path_src).split(os.sep)
    if len(path_src_norm_parts) < 2:
        fail(f"Unable to derive movie name from path_src: {path_src}")
    cam_name = path_src_norm_parts[-2]
    comp_name = path_src_norm_parts[-1]

    movie_stem = f"{scene_name}_{cam_name}_{comp_name}"
    return project_name, scene_name, movie_stem


def ffmpeg_escape(value: str) -> str:
    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace(":", "\\:")
    escaped = escaped.replace("'", "\\'")
    escaped = escaped.replace(",", "\\,")
    return escaped


def build_slate_filter(
    movie_title: str,
    project_name: str,
    scene_name: str,
    movie_date: str,
    copyright_text: str,
    font_file: str | None,
    logo_scale: float,
) -> str:
    title_esc = ffmpeg_escape(movie_title)
    proj_esc = ffmpeg_escape(f"PROJECT: {project_name}")
    scene_esc = ffmpeg_escape(f"SCENE: {scene_name}")
    date_esc = ffmpeg_escape(f"DATE: {movie_date}")
    copy_esc = ffmpeg_escape(copyright_text)
    font_opt = f"fontfile='{ffmpeg_escape(font_file)}':" if font_file else ""

    return (
        "[0:v]"
        "drawtext=" + font_opt + "fontcolor=white:fontsize=62:text='" + title_esc + "':x=(w-text_w)/2:y=h*0.26,"
        "drawtext=" + font_opt + "fontcolor=white:fontsize=34:text='" + proj_esc + "':x=(w-text_w)/2:y=h*0.49,"
        "drawtext=" + font_opt + "fontcolor=white:fontsize=34:text='" + scene_esc + "':x=(w-text_w)/2:y=h*0.56,"
        "drawtext=" + font_opt + "fontcolor=white:fontsize=34:text='" + date_esc + "':x=(w-text_w)/2:y=h*0.63,"
        "drawtext=" + font_opt + "fontcolor=white:fontsize=28:text='" + copy_esc + "':x=(w-text_w)/2:y=h*0.83[sbase];"
        "[1:v]scale=iw*" + str(logo_scale) + ":ih*" + str(logo_scale) + "[logo];"
        "[sbase][logo]overlay=x=W-w-80:y=70"
    )


def run_cmd(cmd: list[str], step_name: str) -> None:
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        fail(
            f"ffmpeg failed during {step_name}\n"
            f"  command: {' '.join(cmd)}\n"
            f"  stderr:\n{exc.stderr}"
        )


def make_sequence_video(
    path_src: str,
    fps: int,
    frame_start: int,
    base_name: str,
    frame_width: int,
    path_out: str,
) -> None:
    input_pattern = os.path.join(path_src, f"{base_name}.%0{frame_width}d.png")
    cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(fps),
        "-start_number",
        str(frame_start),
        "-i",
        input_pattern,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        path_out,
    ]
    run_cmd(cmd, "sequence encoding")


def make_slate_video(
    path_logo: str,
    movie_title: str,
    project_name: str,
    scene_name: str,
    movie_date: str,
    font_file: str | None,
    path_out: str,
) -> None:
    copyright_text = f"copyright [dummy] {datetime.now().year}"
    filter_complex = build_slate_filter(
        movie_title=movie_title,
        project_name=project_name,
        scene_name=scene_name,
        movie_date=movie_date,
        copyright_text=copyright_text,
        font_file=font_file,
        logo_scale=LOGO_SCALE,
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=#111111:s=1920x1080:r={DEFAULT_FPS}:d={DEFAULT_TITLE_SECONDS}",
        "-loop",
        "1",
        "-i",
        path_logo,
        "-filter_complex",
        filter_complex,
        "-t",
        str(DEFAULT_TITLE_SECONDS),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        path_out,
    ]
    run_cmd(cmd, "slate creation")


def concat_videos(path_a: str, path_b: str, path_dst: str, movie_title: str, movie_date: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        list_file = fh.name
        fh.write(f"file '{path_a}'\n")
        fh.write(f"file '{path_b}'\n")

    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_file,
            "-c",
            "copy",
            "-metadata",
            f"title={movie_title}",
            "-metadata",
            f"date={movie_date}",
            path_dst,
        ]
        run_cmd(cmd, "final concat")
    finally:
        if os.path.exists(list_file):
            os.unlink(list_file)


def main() -> None:
    args = parse_args()

    job_dir = os.getenv("JOB_DIR")
    wf_img_dir = os.getenv("WF_IMG_DIR")
    if not job_dir or not wf_img_dir:
        fail("WF_IMG_DIR and JOB_DIR must be set")
    if shutil.which("ffmpeg") is None:
        fail("ffmpeg executable was not found in PATH (install with: brew install ffmpeg)")

    job_dir = os.path.abspath(job_dir)
    wf_img_dir = os.path.abspath(wf_img_dir)
    path_src = validate_source(path_src=args.path_src, wf_img_dir=wf_img_dir)
    movie_title = args.movie_title
    movie_date = date.today().isoformat()
    font_file = os.path.abspath(args.font_file) if args.font_file else None
    if font_file and not os.path.isfile(font_file):
        fail(f"Font file not found: {font_file}")
    if font_file is None:
        default_fonts = [
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Helvetica.ttf",
        ]
        font_file = next((path for path in default_fonts if os.path.isfile(path)), None)
        if font_file is None:
            fail("No font filename provided and no default font file found. Use --font-file.")

    base_name, frame_width, frame_numbers = find_sequence_frames(path_src)
    frame_start, frame_end = validate_contiguous_frames(
        frame_numbers,
        path_src,
        base_name=base_name,
        frame_width=frame_width,
    )
    print(f"Found sequence: {len(frame_numbers)} frames ({frame_start:04d}-{frame_end:04d})")

    project_name, scene_name, movie_stem = derive_names(
        path_src=path_src,
        wf_img_dir=wf_img_dir,
        job_dir=job_dir,
    )

    path_dst = os.path.join(job_dir, "movies", "source", f"{movie_stem}.mp4")
    dst_parent = os.path.dirname(path_dst)
    if not os.path.isdir(dst_parent):
        fail(f"Destination directory does not exist: {dst_parent}")
    if not os.access(dst_parent, os.W_OK):
        fail(f"Destination directory is not writable: {dst_parent}")

    if not SLATE_OUTPUT:
        print("Encoding image sequence...")
        make_sequence_video(
            path_src=path_src,
            fps=DEFAULT_FPS,
            frame_start=frame_start,
            base_name=base_name,
            frame_width=frame_width,
            path_out=path_dst,
        )
        print("\nDone")
        print(f"  Source : {path_src}")
        print(f"  Output : {path_dst}")
        print(f"  Title  : {movie_title}")
        return

    logo_path = os.path.join(job_dir, "logo", "logo9.png")
    if not os.path.isfile(logo_path):
        fail(f"Logo not found: {logo_path}")

    with tempfile.TemporaryDirectory(prefix="imgseq2mp4_") as tmp_dir:
        path_slate = os.path.join(tmp_dir, "slate.mp4")
        path_seq = os.path.join(tmp_dir, "sequence.mp4")

        print(f"Creating slate ({DEFAULT_TITLE_SECONDS}s)...")
        make_slate_video(
            path_logo=logo_path,
            movie_title=movie_title,
            project_name=project_name,
            scene_name=scene_name,
            movie_date=movie_date,
            font_file=font_file,
            path_out=path_slate,
        )

        print("Encoding image sequence...")
        make_sequence_video(
            path_src=path_src,
            fps=DEFAULT_FPS,
            frame_start=frame_start,
            base_name=base_name,
            frame_width=frame_width,
            path_out=path_seq,
        )

        print("Concatenating slate + sequence...")
        concat_videos(
            path_a=path_slate,
            path_b=path_seq,
            path_dst=path_dst,
            movie_title=movie_title,
            movie_date=movie_date,
        )

    print("\nDone")
    print(f"  Source : {path_src}")
    print(f"  Output : {path_dst}")
    print(f"  Title  : {movie_title}")
    print(f"  Project: {project_name}")
    print(f"  Scene  : {scene_name}")
    print(f"  Date   : {movie_date}")


if __name__ == "__main__":
    main()