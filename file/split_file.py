#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按指定大小拆分文本文件，保证不截断行。

支持格式：txt / json / markdown / jsonl 等文本文件。
支持按字节大小拆分（如 10MB、1.5GB、100KB、1024）。

用法示例：
    python split_file.py input.txt 10MB -o ./output
    python split_file.py data.jsonl 500MB -o ./chunks --index-width 4
"""

import argparse
import re
import sys
from pathlib import Path

try:
    import chardet
except ImportError:  # pragma: no cover
    chardet = None


# 常见二进制文件扩展名，用于风险提示（本脚本仍按文本处理，但会提示）
BINARY_SUFFIXES = {".bin", ".exe", ".zip", ".gz", ".tar", ".rar", ".7z", ".pdf", ".docx"}


def parse_size(size_str: str) -> int:
    """
    解析大小字符串，如 10MB、1.5GB、100KB、1024，返回字节数。
    支持 KB/MB/GB/TB（十进制）和 KiB/MiB/GiB/TiB（二进制）。
    """
    size_str = size_str.strip().upper().replace(" ", "")
    if not size_str:
        raise ValueError("Size cannot be empty")

    if size_str.isdigit():
        return int(size_str)

    match = re.match(r"^(\d+(?:\.\d+)?)\s*(B|KB|MB|GB|TB|KIB|MIB|GIB|TIB)$", size_str)
    if not match:
        raise ValueError(
            f"Invalid size format: '{size_str}'. Expected like 10MB, 1.5GB, 100KB, 1024"
        )

    value = float(match.group(1))
    unit = match.group(2)

    units = {
        "B": 1,
        "KB": 1000,
        "MB": 1000 ** 2,
        "GB": 1000 ** 3,
        "TB": 1000 ** 4,
        "KIB": 1024,
        "MIB": 1024 ** 2,
        "GIB": 1024 ** 3,
        "TIB": 1024 ** 4,
    }
    return int(value * units[unit])


def detect_file_info(file_path: Path, sample_size: int = 1024 * 1024) -> dict:
    """
    检测文件编码及 BOM 信息。

    返回：
        {
            "encoding": str,      # 检测到的编码，如 'utf-8'
            "confidence": float,  # 置信度 0~1
            "bom": bool,          # 是否包含 BOM
            "bom_bytes": bytes    # BOM 字节
        }
    """
    with open(file_path, "rb") as f:
        first_bytes = f.read(sample_size)

    if chardet is not None:
        result = chardet.detect(first_bytes) or {}
        encoding = result.get("encoding") or "utf-8"
        confidence = result.get("confidence") or 0.0
    else:
        encoding = "utf-8"
        confidence = 0.0

    # 检测 BOM
    bom_bytes = b""
    with open(file_path, "rb") as f:
        head = f.read(4)
    if head.startswith(b"\xef\xbb\xbf"):
        bom_bytes = b"\xef\xbb\xbf"
    elif head.startswith(b"\xff\xfe"):
        bom_bytes = b"\xff\xfe"
    elif head.startswith(b"\xfe\xff"):
        bom_bytes = b"\xfe\xff"
    elif head.startswith(b"\x00\x00\xfe\xff"):
        bom_bytes = b"\x00\x00\xfe\xff"

    return {
        "encoding": encoding,
        "confidence": confidence,
        "bom": bool(bom_bytes),
        "bom_bytes": bom_bytes,
    }


def split_file(
    input_path: Path,
    target_size: int,
    output_dir: Path,
    *,
    index_width: int = 3,
    verbose: bool = True,
    encoding_override: str = None,
) -> int:
    """
    拆分文件。

    参数：
        input_path:   输入文件路径
        target_size:  目标大小（字节）
        output_dir:   输出目录
        index_width:  序号位数（默认 3，如 001）
        verbose:      是否打印进度

    返回：
        生成的文件数量
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if not input_path.is_file():
        raise ValueError(f"Input path is not a file: {input_path}")
    if target_size <= 0:
        raise ValueError(f"Target size must be positive, got {target_size}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # 编码检测
    info = detect_file_info(input_path)
    if encoding_override:
        info["encoding"] = encoding_override
    encoding = info["encoding"]
    # 检测 BOM 仅用于日志报告；二进制按行切分已自然保留 BOM，无需额外写入。
    bom_bytes = info["bom_bytes"]

    if input_path.suffix.lower() in BINARY_SUFFIXES:
        print(
            f"WARNING: Input file '{input_path.suffix}' looks like a binary format. "
            "This script is designed for text files.",
            file=sys.stderr,
        )

    if verbose:
        print(f"Input file:  {input_path}")
        print(f"Output dir:  {output_dir}")
        print(f"Encoding:    {encoding} (confidence: {info['confidence']:.2f})")
        print(f"Target size: {target_size} bytes")
        print(f"BOM:         {'yes' if info['bom'] else 'no'}")
        print("-" * 40)

    stem = input_path.stem
    suffix = input_path.suffix

    current_chunk = bytearray()
    file_index = 0
    total_lines = 0
    chunk_lines = 0
    total_written = 0

    def write_chunk():
        nonlocal file_index, current_chunk, chunk_lines, total_written
        if not current_chunk:
            return
        file_index += 1
        out_name = f"{stem}_{file_index:0{index_width}d}{suffix}"
        out_path = output_dir / out_name
        with open(out_path, "wb") as f:
            f.write(current_chunk)
        written = len(current_chunk)
        total_written += written
        if verbose:
            print(
                f"  {out_name}: {written:>10} bytes, {chunk_lines:>6} lines"
            )
        current_chunk = bytearray()
        chunk_lines = 0

    with open(input_path, "rb") as f:
        for line in f:
            line_len = len(line)
            total_lines += 1

            # 检查单行是否超过目标大小
            if line_len > target_size:
                preview = line[:120].decode(encoding, errors="replace")
                raise ValueError(
                    f"Single line ({line_len} bytes) exceeds target size "
                    f"({target_size} bytes). Cannot split without breaking a line.\n"
                    f"Line preview: {preview!r}"
                )

            # 如果当前 chunk 非空，且加入本行会超过目标大小，则先写出
            if current_chunk and len(current_chunk) + line_len > target_size:
                write_chunk()

            current_chunk += line
            chunk_lines += 1

    # 写出最后一段
    write_chunk()

    if verbose:
        print("-" * 40)
        print(
            f"Done. Total files: {file_index}, total lines: {total_lines}, "
            f"total written: {total_written} bytes."
        )

    return file_index


def main():
    parser = argparse.ArgumentParser(
        description="Split a text file into smaller files by size without breaking lines.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python split_file.py input.txt 10MB
  python split_file.py data.jsonl 500MB -o ./chunks
  python split_file.py article.md 1MB -o ./parts --index-width 4
        """,
    )
    parser.add_argument("input", help="Path to the input text file")
    parser.add_argument(
        "size",
        help="Max size per output file, e.g. 10MB, 1.5GB, 100KB, 1024 (bytes)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output directory (default: ./split_output next to input file)",
    )
    parser.add_argument(
        "--index-width",
        type=int,
        default=3,
        help="Width of the file index (default: 3, e.g. 001, 002)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    parser.add_argument(
        "--encoding",
        default=None,
        help="Override detected encoding (e.g. utf-8, gbk). Auto-detect if omitted.",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output) if args.output else input_path.parent / "split_output"

    try:
        target_size = parse_size(args.size)
        split_file(
            input_path,
            target_size,
            output_dir,
            index_width=args.index_width,
            verbose=not args.quiet,
            encoding_override=args.encoding,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
