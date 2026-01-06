#!/usr/bin/env python3
"""

- Écoute UDP (défaut 12351)
- Parse 2 types de paquets :
  - skdf : définition du squelette (bones + parents + pose de référence)
  - fram : frames (fnum/time + transforms par bone)
- Affiche quelques os (root/head/l_hand/r_hand) ou bien tout en JSON.
"""

from __future__ import annotations

import argparse
import json
import socket
import struct
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Tuple

BONE_NAMES: List[str] = [
    "root", "torso_1", "torso_2", "torso_3", "torso_4", "torso_5", "torso_6", "torso_7",
    "neck_1", "neck_2", "head",
    "l_shoulder", "l_up_arm", "l_low_arm", "l_hand",
    "r_shoulder", "r_up_arm", "r_low_arm", "r_hand",
    "l_up_leg", "l_low_leg", "l_foot", "l_toes",
    "r_up_leg", "r_low_leg", "r_foot", "r_toes",
]


@dataclass(frozen=True)
class Transform:
    rot_xyzw: Tuple[float, float, float, float]  # quaternion (x,y,z,w)
    pos_xyz: Tuple[float, float, float]          # position (x,y,z)


@dataclass(frozen=True)
class SkeletonBone:
    bone_id: int
    parent_id: int
    rest: Optional[Transform]


@dataclass(frozen=True)
class FrameBone:
    bone_id: int
    trans: Transform


@dataclass(frozen=True)
class Frame:
    fnum: int
    time: int
    bones: List[FrameBone]


def bone_name(bone_id: int) -> str:
    return BONE_NAMES[bone_id] if 0 <= bone_id < len(BONE_NAMES) else f"bone_{bone_id}"


def read_box(buf: bytes, offset: int) -> Tuple[str, bytes, int]:
    """
    Box = [u32 little-endian length][4 bytes ASCII tag][payload(length bytes)]
    Retour: (tag, payload, new_offset)
    """
    if offset + 8 > len(buf):
        raise ValueError("Truncated box header")

    length = struct.unpack_from("<I", buf, offset)[0]
    tag_bytes = buf[offset + 4: offset + 8]
    try:
        tag = tag_bytes.decode("ascii")
    except UnicodeDecodeError:
        tag = tag_bytes.hex()

    start = offset + 8
    end = start + length
    if end > len(buf):
        raise ValueError(f"Truncated payload for tag={tag}: need {length} bytes, have {len(buf) - start}")

    return tag, buf[start:end], end


def iter_boxes(payload: bytes) -> Iterator[Tuple[str, bytes]]:
    off = 0
    while off < len(payload):
        tag, data, off = read_box(payload, off)
        yield tag, data


def parse_tran_payload(payload: bytes) -> Transform:
    # attendu: 7 floats little-endian = 28 bytes (quat 4 + pos 3)
    if len(payload) < 28:
        raise ValueError(f"tran payload too short: {len(payload)} bytes")
    x, y, z, w, px, py, pz = struct.unpack_from("<7f", payload, 0)
    return Transform(rot_xyzw=(x, y, z, w), pos_xyz=(px, py, pz))


def parse_head(payload: bytes) -> Dict[str, object]:
    out: Dict[str, object] = {}
    for tag, data in iter_boxes(payload):
        if tag == "ftyp":
            out["ftyp"] = data.decode("utf-8", errors="replace")
        elif tag == "vrsn":
            out["vrsn"] = data[0] if data else None
        else:
            out[tag] = data
    return out


def parse_info(payload: bytes) -> Dict[str, object]:
    out: Dict[str, object] = {}
    for tag, data in iter_boxes(payload):
        if tag == "ipad" and len(data) >= 8:
            out["ipad_raw_u64"] = struct.unpack_from("<Q", data, 0)[0]
        elif tag == "rcvp" and len(data) >= 2:
            out["rcvp"] = struct.unpack_from("<H", data, 0)[0]
        else:
            out[tag] = data
    return out


def parse_bndt(payload: bytes) -> SkeletonBone:
    bone_id: Optional[int] = None
    parent_id: Optional[int] = None
    rest: Optional[Transform] = None

    for tag, data in iter_boxes(payload):
        if tag == "bnid" and len(data) >= 2:
            bone_id = struct.unpack_from("<H", data, 0)[0]
        elif tag == "pbid" and len(data) >= 2:
            parent_id = struct.unpack_from("<H", data, 0)[0]
        elif tag == "tran":
            rest = parse_tran_payload(data)

    if bone_id is None or parent_id is None:
        raise ValueError("bndt missing bnid/pbid")
    return SkeletonBone(bone_id=bone_id, parent_id=parent_id, rest=rest)


def parse_skdf(payload: bytes) -> List[SkeletonBone]:
    bones: List[SkeletonBone] = []
    for tag, data in iter_boxes(payload):
        if tag == "bons":
            for t2, d2 in iter_boxes(data):
                if t2 == "bndt":
                    bones.append(parse_bndt(d2))
    return bones


def parse_btdt(payload: bytes) -> FrameBone:
    bone_id: Optional[int] = None
    trans: Optional[Transform] = None

    for tag, data in iter_boxes(payload):
        if tag == "bnid" and len(data) >= 2:
            bone_id = struct.unpack_from("<H", data, 0)[0]
        elif tag == "tran":
            trans = parse_tran_payload(data)

    if bone_id is None or trans is None:
        raise ValueError("btdt missing bnid/tran")
    return FrameBone(bone_id=bone_id, trans=trans)


def parse_fram(payload: bytes) -> Frame:
    fnum: Optional[int] = None
    time: Optional[int] = None
    bones: List[FrameBone] = []

    for tag, data in iter_boxes(payload):
        if tag == "fnum" and len(data) >= 4:
            fnum = struct.unpack_from("<I", data, 0)[0]
        elif tag == "time" and len(data) >= 4:
            time = struct.unpack_from("<I", data, 0)[0]
        elif tag == "btrs":
            for t2, d2 in iter_boxes(data):
                if t2 == "btdt":
                    bones.append(parse_btdt(d2))

    if fnum is None or time is None:
        raise ValueError("fram missing fnum/time")
    return Frame(fnum=fnum, time=time, bones=bones)


def parse_packet(datagram: bytes) -> Dict[str, object]:
    """
    Top-level (souvent): head -> info -> (skdf|fram)
    """
    off = 0
    tag1, head_payload, off = read_box(datagram, off)
    tag2, info_payload, off = read_box(datagram, off)
    tag3, third_payload, off = read_box(datagram, off)

    head = parse_head(head_payload)
    info = parse_info(info_payload)

    if tag3 == "skdf":
        return {"type": "skeleton", "head_tag": tag1, "info_tag": tag2, "head": head, "info": info,
                "bones": parse_skdf(third_payload)}
    if tag3 == "fram":
        return {"type": "frame", "head_tag": tag1, "info_tag": tag2, "head": head, "info": info,
                "frame": parse_fram(third_payload)}

    return {"type": "unknown", "tag": tag3, "head": head, "info": info, "payload_len": len(third_payload)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0", help="Interface d'écoute (défaut: 0.0.0.0)")
    ap.add_argument("--port", type=int, default=12351, help="Port UDP (défaut: 12351)")
    ap.add_argument("--json", action="store_true", help="Sortie JSON (1 ligne par frame, tous les os)")
    ap.add_argument("--bones", default="root,head,l_hand,r_hand",
                    help="Os à afficher (noms séparés par des virgules), ignoré si --json")
    args = ap.parse_args()

    wanted_names = [x.strip() for x in args.bones.split(",") if x.strip()]
    wanted_ids = {i for i, n in enumerate(BONE_NAMES) if n in wanted_names}

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, args.port))
    print(f"Listening UDP on {args.host}:{args.port} ...")

    skeleton_cache: Dict[int, SkeletonBone] = {}

    while True:
        data, addr = sock.recvfrom(65535)
        try:
            pkt = parse_packet(data)
        except Exception as e:
            print(f"[WARN] parse error from {addr}: {e} (len={len(data)})")
            continue

        if pkt["type"] == "skeleton":
            bones: List[SkeletonBone] = pkt["bones"]  # type: ignore[assignment]
            for b in bones:
                skeleton_cache[b.bone_id] = b
            print(f"[SKDF] skeleton reçu: {len(bones)} bones")
            continue

        if pkt["type"] == "frame":
            frame: Frame = pkt["frame"]  # type: ignore[assignment]

            if args.json:
                out = {
                    "fnum": frame.fnum,
                    "time": frame.time,
                    "bones": {
                        bone_name(b.bone_id): {
                            "rot_xyzw": b.trans.rot_xyzw,
                            "pos_xyz": b.trans.pos_xyz,
                        }
                        for b in frame.bones
                    },
                }
                print(json.dumps(out, separators=(",", ":")))
            else:
                print(f"[FRAM] fnum={frame.fnum} time={frame.time} bones={len(frame.bones)}")
                for b in frame.bones:
                    if wanted_ids and b.bone_id not in wanted_ids:
                        continue
                    r = tuple(round(x, 4) for x in b.trans.rot_xyzw)
                    p = tuple(round(x, 4) for x in b.trans.pos_xyz)
                    print(f"  - {bone_name(b.bone_id):>10s} id={b.bone_id:02d} rot={r} pos={p}")
            continue

        print(f"[UNK] tag={pkt.get('tag')} from {addr}")


if __name__ == "__main__":
    main()
