#!/usr/bin/env python3
"""
SBTI reverse research script.

What it does:
1) Fetches public page HTML.
2) Extracts NORMAL_TYPES and core constants by regex.
3) Reconstructs matching algorithm.
4) Computes exact distribution across full answer space.
5) Writes machine-readable outputs for GitHub Pages.

Run:
  python scripts/analyze_sbti.py
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import requests

URL = "https://sbti.unun.dev/"
DIM_ORDER = ["S1", "S2", "S3", "E1", "E2", "E3", "A1", "A2", "A3", "Ac1", "Ac2", "Ac3", "So1", "So2", "So3"]

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DATA = DOCS / "data"
DATA.mkdir(parents=True, exist_ok=True)


def extract_normal_types(html: str):
    m = re.search(r"const NORMAL_TYPES = (\[.*?\n\s*\]);", html, flags=re.S)
    if not m:
        raise RuntimeError("Cannot locate NORMAL_TYPES in HTML")
    block = m.group(1)
    pairs = re.findall(r'"code":\s*"([^"]+)"\s*,\s*"pattern":\s*"([LMH\-]+)"', block)
    if not pairs:
        raise RuntimeError("Failed to parse NORMAL_TYPES code/pattern pairs")
    return pairs


def extract_type_cn_map(html: str):
    # best-effort extraction from TYPE_LIBRARY entries
    pairs = re.findall(r'"([^"]+)":\s*\{\s*"code":\s*"[^"]+",\s*"cn":\s*"([^"]+)"', html)
    return dict(pairs)


def extract_type_images(html: str):
    m = re.search(r"const TYPE_IMAGES = (\{.*?\n\s*\});", html, flags=re.S)
    if not m:
        return {}
    block = m.group(1)
    # match "CODE": "..." or "CODE": null
    pairs = re.findall(r'"([^"]+)":\s*("(?:[^"\\]|\\.)*"|null)', block)
    out = {}
    for code, raw in pairs:
        if raw == "null":
            out[code] = None
        else:
            # remove surrounding quotes and unescape
            s = raw[1:-1]
            s = s.encode("utf-8").decode("unicode_escape")
            out[code] = s
    return out


def parse_branch_info(html: str):
    # best-effort parse of special question options from public script
    gate_q1 = re.search(r"id:\s*'drink_gate_q1'.*?options:\s*\[(.*?)\]", html, flags=re.S)
    gate_q2 = re.search(r"id:\s*'drink_gate_q2'.*?options:\s*\[(.*?)\]", html, flags=re.S)

    def count_values(block_match):
        if not block_match:
            return None, []
        block = block_match.group(1)
        vals = re.findall(r"value:\s*(\d+)", block)
        vals = [int(v) for v in vals]
        return len(vals), vals

    q1_n, q1_vals = count_values(gate_q1)
    q2_n, q2_vals = count_values(gate_q2)
    return {
        "drink_gate_q1_options": q1_n,
        "drink_gate_q1_values": q1_vals,
        "drink_gate_q2_options": q2_n,
        "drink_gate_q2_values": q2_vals,
    }


def similarity_from_distance(d: np.ndarray) -> np.ndarray:
    # same formula as observed in page
    return np.maximum(0, np.rint((1 - d / 30) * 100).astype(int))


def compute_level_space_distribution(codes, patterns):
    # template vectors: shape (T, 15)
    map_num = {"L": 1, "M": 2, "H": 3}
    V = np.array([[map_num[c] for c in p.replace("-", "")] for p in patterns], dtype=np.int8)

    # all 3^15 level states
    axes = [np.array([1, 2, 3], dtype=np.int8)] * 15
    G = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 15)

    N = G.shape[0]
    best_idx = np.empty(N, dtype=np.int16)
    best_dist = np.empty(N, dtype=np.int16)

    # chunk to avoid huge peak memory
    chunk = 300_000
    for s in range(0, N, chunk):
        e = min(N, s + chunk)
        X = G[s:e]  # (m,15)

        diff = np.abs(X[:, None, :] - V[None, :, :])  # (m,T,15)
        d = diff.sum(axis=2)  # (m,T)
        exact = (diff == 0).sum(axis=2)

        min_d = d.min(axis=1, keepdims=True)
        mask = d == min_d

        # tie-break: max exact among min distance
        ex = np.where(mask, exact, -1)
        max_ex = ex.max(axis=1, keepdims=True)
        chosen = mask & (exact == max_ex)

        # final tie-break in source is similarity (monotonic in distance);
        # if still tied, keep first by order.
        idx = np.argmax(chosen, axis=1)

        best_idx[s:e] = idx
        best_dist[s:e] = d[np.arange(e - s), idx]

    sim = similarity_from_distance(best_dist)
    normal_ok = sim >= 60

    cnt = Counter()
    for i, code in enumerate(codes):
        cnt[code] = int(((best_idx == i) & normal_ok).sum())
    cnt["HHHH"] = int((~normal_ok).sum())

    return cnt


def lift_to_answer_space(level_counts: Counter, branch_info: dict):
    # Under current observed structure:
    # - normal questions: 30x(1..3)
    # - level states: 3^15
    # - each level state has 3^15 normal-answer preimages (2 q per dim, sum->L/M/H)
    # - gate q1 has 4 options
    # - DRUNK branch when q1=3 and q2=2
    three15 = 3 ** 15
    three30 = 3 ** 30

    total_combos = 5 * three30  # 3*q1 non-branch + 2*q2 branch when q1=3

    full_counts = {}
    for k, v in level_counts.items():
        # non-DRUNK paths contribute factor 4 over gate branching:
        # q1!=3  (3 ways)  + q1=3,q2=1 (1 way) = 4
        full_counts[k] = v * (4 * three15)

    full_counts["DRUNK"] = three30  # q1=3 and q2=2 across 30 normal q answers

    probs = {k: full_counts[k] / total_combos for k in full_counts}

    return {
        "total_answer_combinations": total_combos,
        "full_counts": full_counts,
        "probabilities": probs,
    }


def main():
    print(f"Fetching {URL} ...")
    html = requests.get(URL, timeout=30).text

    normal_types = extract_normal_types(html)
    codes = [c for c, _ in normal_types]
    patterns = [p for _, p in normal_types]
    cn_map = extract_type_cn_map(html)
    type_images = extract_type_images(html)

    branch_info = parse_branch_info(html)

    level_counts = compute_level_space_distribution(codes, patterns)
    lifted = lift_to_answer_space(level_counts, branch_info)

    probs = lifted["probabilities"]

    # full distribution
    rows = sorted(probs.items(), key=lambda kv: -kv[1])
    df = pd.DataFrame(rows, columns=["type", "probability"])
    df["percentage"] = df["probability"] * 100
    df.to_csv(DATA / "type_distribution_full.csv", index=False)

    # non-drunk normalized
    non_drunk_mass = 1 - probs.get("DRUNK", 0)
    rows_non = [(k, v / non_drunk_mass) for k, v in probs.items() if k != "DRUNK"]
    rows_non = sorted(rows_non, key=lambda kv: -kv[1])
    df_non = pd.DataFrame(rows_non, columns=["type", "probability_non_drunk"])
    df_non["percentage_non_drunk"] = df_non["probability_non_drunk"] * 100
    df_non.to_csv(DATA / "type_distribution_non_drunk.csv", index=False)

    # mapping example output
    map_df = pd.DataFrame({
        "code": codes,
        "cn": [cn_map.get(c, "") for c in codes],
        "pattern": patterns,
        "has_image": [bool(type_images.get(c)) for c in codes],
    })
    map_df.to_csv(DATA / "mapping_example.csv", index=False)
    map_df.to_csv(DATA / "type_meta.csv", index=False)

    summary = {
        "url": URL,
        "normal_type_count": len(normal_types),
        "branch_info": branch_info,
        "total_answer_combinations": lifted["total_answer_combinations"],
        "top10_full": [
            {"type": t, "percentage": round(p * 100, 4)} for t, p in rows[:10]
        ],
        "top10_non_drunk": [
            {"type": t, "percentage": round(p * 100, 4)} for t, p in rows_non[:10]
        ],
        "image_count": sum(1 for v in type_images.values() if v),
    }

    with open(DATA / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    with open(DATA / "type_images.json", "w", encoding="utf-8") as f:
        json.dump(type_images, f, ensure_ascii=False)

    print("Done.")
    print("Top 10 full distribution:")
    for r in summary["top10_full"]:
        print(f"  {r['type']}: {r['percentage']}%")


if __name__ == "__main__":
    main()
