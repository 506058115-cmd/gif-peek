#!/usr/bin/env python3
"""Summarize GIF container blocks without decoding image data."""

import argparse
from pathlib import Path
import stat
import sys


MAX_BYTES = 512 * 1024 * 1024
MAX_BLOCKS = 1_000_000


class GifError(ValueError):
    pass


def read_exact(stream, size, label):
    data = stream.read(size)
    if len(data) != size:
        raise GifError(f"truncated {label}")
    return data


def skip_bytes(stream, size, file_size, label):
    if size > file_size - stream.tell():
        raise GifError(f"truncated {label}")
    stream.seek(size, 1)


def skip_subblocks(stream, file_size, budget):
    while True:
        budget -= 1
        if budget < 0:
            raise GifError("block limit exceeded")
        size = read_exact(stream, 1, "data sub-block size")[0]
        if size == 0:
            return budget
        skip_bytes(stream, size, file_size, "data sub-block")


def inspect(path):
    source = Path(path)
    file_stat = source.stat()
    if not stat.S_ISREG(file_stat.st_mode):
        raise GifError("input must be a regular file")
    if file_stat.st_size > MAX_BYTES:
        raise GifError("input exceeds the 512 MiB limit")

    extensions = {"graphic control": 0, "comment": 0, "plain text": 0, "application": 0, "other": 0}
    frames = local_tables = 0
    with source.open("rb") as stream:
        header = read_exact(stream, 6, "header")
        if header[:3] != b"GIF" or header[3:] not in (b"87a", b"89a"):
            raise GifError("invalid GIF87a/GIF89a header")
        screen = read_exact(stream, 7, "logical screen descriptor")
        width = int.from_bytes(screen[0:2], "little")
        height = int.from_bytes(screen[2:4], "little")
        packed = screen[4]
        if not width or not height:
            raise GifError("logical screen dimensions must be nonzero")
        global_entries = 2 << (packed & 0x07) if packed & 0x80 else 0
        if global_entries:
            skip_bytes(stream, global_entries * 3, file_stat.st_size, "global color table")

        budget = MAX_BLOCKS
        while True:
            budget -= 1
            if budget < 0:
                raise GifError("block limit exceeded")
            marker = read_exact(stream, 1, "data block marker")[0]
            if marker == 0x3B:
                break
            if marker == 0x21:
                label = read_exact(stream, 1, "extension label")[0]
                category = {
                    0xF9: "graphic control",
                    0xFE: "comment",
                    0x01: "plain text",
                    0xFF: "application",
                }.get(label, "other")
                extensions[category] += 1
                budget = skip_subblocks(stream, file_stat.st_size, budget)
                continue
            if marker != 0x2C:
                raise GifError("unexpected data block marker")

            descriptor = read_exact(stream, 9, "image descriptor")
            left = int.from_bytes(descriptor[0:2], "little")
            top = int.from_bytes(descriptor[2:4], "little")
            image_width = int.from_bytes(descriptor[4:6], "little")
            image_height = int.from_bytes(descriptor[6:8], "little")
            image_flags = descriptor[8]
            if not image_width or not image_height or left + image_width > width or top + image_height > height:
                raise GifError("image descriptor falls outside the logical screen")
            if image_flags & 0x80:
                entries = 2 << (image_flags & 0x07)
                skip_bytes(stream, entries * 3, file_stat.st_size, "local color table")
                local_tables += 1
            code_size = read_exact(stream, 1, "LZW minimum code size")[0]
            if not 2 <= code_size <= 8:
                raise GifError("LZW minimum code size must be 2–8")
            budget = skip_subblocks(stream, file_stat.st_size, budget)
            frames += 1

        trailing_bytes = file_stat.st_size - stream.tell()

    return header[3:].decode("ascii"), width, height, global_entries, frames, local_tables, extensions, trailing_bytes


def main():
    parser = argparse.ArgumentParser(
        description="Inspect GIF dimensions and block counts without decoding image data."
    )
    parser.add_argument("input", help="GIF87a or GIF89a file")
    args = parser.parse_args()
    try:
        version, width, height, global_entries, frames, local_tables, extensions, trailing = inspect(args.input)
    except GifError as error:
        print(f"gif-peek: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"gif-peek: {error.strerror or 'unable to read input'}", file=sys.stderr)
        return 2

    print(f"GIF version: {version}")
    print(f"Logical screen: {width} × {height}")
    print(f"Global color table: {global_entries} entries" if global_entries else "Global color table: absent")
    print(f"Image descriptors: {frames}")
    print(f"Local color tables: {local_tables}")
    print("Extensions: " + ", ".join(f"{name} {count}" for name, count in extensions.items()))
    print(f"Bytes after trailer: {trailing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
