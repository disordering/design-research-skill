"""按 11 月 2 日两份案例交付的原始清单还原文件，并生成可复核归档。"""

import argparse
import hashlib
import itertools
import json
import re
import struct
import tempfile
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = {"护法": "2026-11-02-hufa-review", "吴山石": "2026-11-02-wushanshi-review"}
SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHUNKS = {b"IHDR", b"pHYs", b"IDAT", b"tEXt", b"IEND"}


def sha256(content):
    return hashlib.sha256(content).hexdigest()


def valid_chunk(body):
    return len(body) >= 8 and zlib.crc32(body[:-4]) == int.from_bytes(body[-4:], "big")


def recover_chunk(raw, lost_bytes):
    positions = (m.start() for m in re.finditer(b"\n", raw))
    for sites in itertools.combinations(positions, lost_bytes):
        pieces = []
        start = 0
        for index in sites:
            pieces.extend([raw[start:index], b"\r"])
            start = index
        restored = b"".join([*pieces, raw[start:]])
        if valid_chunk(restored):
            return restored
    raise ValueError("找不到与原始 CRC 相符的 PNG 数据块")


def recover_png(content):
    damaged_signature = SIGNATURE.replace(b"\r\n", b"\n")
    if content.startswith(SIGNATURE):
        pos = len(SIGNATURE)
    elif content.startswith(damaged_signature):
        pos = len(damaged_signature)
    else:
        raise ValueError("无法识别 PNG 签名")
    result = bytearray(SIGNATURE)
    kinds = []
    while pos < len(content):
        size = struct.unpack_from(">I", content, pos)[0]
        kind = content[pos + 4:pos + 8]
        if kind not in CHUNKS:
            raise ValueError(f"未知 PNG 数据块 {kind!r}")
        # 这四幅图的完整分块最多缺少两个 CR，实际边界需和下一数据块头吻合。
        end = pos + size + 12
        for lost in range(3):
            boundary = end - lost
            if boundary != len(content) and content[boundary + 4:boundary + 8] not in CHUNKS:
                continue
            restored_body = recover_chunk(content[pos + 4:boundary], lost)
            result.extend(content[pos:pos + 4] + restored_body)
            kinds.append(kind)
            pos = boundary
            break
        else:
            raise ValueError(f"无法确定 {kind!r} 分块边界")
    if kinds[0] != b"IHDR" or kinds[-1] != b"IEND":
        raise ValueError("PNG 首尾数据块不完整")
    return bytes(result), len(kinds)


def recover_case(label, folder, destination):
    manifest_bytes = (folder / "SHA256SUMS.txt").read_bytes()
    parts = [row.split(maxsplit=1) for row in manifest_bytes.decode().splitlines() if row]
    assert len(parts) == len({name for _, name in parts}) == 13
    files = {}
    rows = []
    for expected, name in parts:
        original = (folder / name).read_bytes()
        raw = original
        blocks = None
        if name.endswith(".png"):
            raw, blocks = recover_png(original)
            method = "按原始 PNG 分块 CRC 校验" if raw == original else "按原始 PNG 分块 CRC 补回 CR"
        elif sha256(original) == expected:
            method = "原样"
        else:
            raw = original.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            method = "还原 CRLF"
        if sha256(raw) != expected:
            raise ValueError(f"{label}/{name} 与交付清单不符")
        rows.append({"文件": name, "处理": method, "补回字节数": len(raw) - len(original),
                     "数据块数": blocks, "原交付SHA256": expected})
        files[name] = raw
    files["SHA256SUMS.txt"] = manifest_bytes
    final = destination / f"{label}-2026-11-02-原交付.zip"
    with tempfile.TemporaryDirectory(dir=destination) as temp:
        archive = Path(temp) / "case.zip"
        with zipfile.ZipFile(archive, "w") as z:
            for name, data in files.items():
                member = zipfile.ZipInfo(name, date_time=(2026, 11, 2, 0, 0, 0))
                member.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(member, data)
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None and len(z.namelist()) == 14
            for expected, name in parts:
                assert sha256(z.read(name)) == expected
        archive.replace(final)
    return {"案例": label, "压缩包": final.name, "压缩包SHA256": sha256(final.read_bytes()),
            "匹配": len(parts), "清单文件数": len(parts), "文件校验": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="存放两份已校验 ZIP 与校验结果的目录")
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=True)
    index = [recover_case(label, ROOT / "deliverables" / folder, out) for label, folder in CASES.items()]
    (out / "校验结果.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for row in index:
        print(row["案例"], f"{row['匹配']}/{row['清单文件数']}", row["压缩包SHA256"])
