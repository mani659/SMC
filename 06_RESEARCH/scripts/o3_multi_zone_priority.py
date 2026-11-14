"""O3 — multi-zone priority: overlap clusters and counterfactual keep-sets.

Question (``OPEN_DECISIONS_RESEARCH_AGENDA.md`` §O3): when D1 / H4 / H1 / M15
armed zones overlap or conflict, what wins — and would a one-line priority rule
change the routed / C3-pass / filled set?

READ-ONLY AND OFFLINE. This script never runs the product composition: it
consumes the **O2 armed table** (``o2_htf_sweep_stage/armed_sweep_join.csv``),
produced by the frozen product composition on the frozen window with the full
D1/H4/H1/M15 detection set, whose funnel counts reconciled to O1 and post-C2
(441 armed / 149 routes / 11 fills). The table's SHA-256 is verified against the
O2 ``summary.json`` before use, so the reuse is provable, not assumed. No broker
path is re-simulated; fills are counted as outcome identities, never as PnL.

--------------------------------------------------------------------------
PRE-REGISTERED (frozen before any cluster or counterfactual was inspected)
--------------------------------------------------------------------------
OVERLAP (primary)
  Two armed POIs overlap when
    (a) OPPOSITE direction and their price ranges intersect, OR
    (b) SAME direction and their ranges intersect with
        intersection_height / min(height_a, height_b) >= 0.50.
  The 0.50 ratio is fixed and is not tuned.

TF ORDER (counterfactual priority)
  D1 > H4 > H1 > M15 (highest detection TF wins).

COUNTERFACTUALS (per overlap cluster; singletons always survive)
  CF0 ACTUAL     — the exported armed / routed / passed-C3 / filled sets.
  CF1 HIGHEST_TF — keep only the highest-TF arm (ties: earliest arm, then id).
  CF2 TIGHTEST   — keep the smallest zone height (ties: earliest arm, then id).
  CF3 FIRST_ARMED— keep the earliest arm (sanity: the product's own rule).

  VIEW A (PRIMARY, the pre-registered relation) — price-range overlap only.
  VIEW B (SECONDARY, exploratory) — the same relation restricted to arms that
  landed in the SAME detection batch (identical arm timestamp). A priority rule
  can only ever choose between zones that are live at the same instant, so this
  view shows the decision surface a rule would actually act on. It is reported
  separately and is NOT the basis for the lock reading, because it was added to
  the analysis after VIEW A showed transitive chaining through wide bodies.

CURRENT PRODUCT BEHAVIOUR (observed, not changed)
  ``multi_tf_runtime.ZoneDedup`` (class in that file, ~line 150) treats
  same-direction overlapping spans as ONE episode owned by whichever arm
  registered first; ``register`` runs only after an arm wins, and keys retire
  with their owner. The surviving member is therefore first-armed, and no TF
  rank exists anywhere in the runtime.
--------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# --- pre-registered constants ---------------------------------------------
OVERLAP_MIN_RATIO = 0.50
TF_ORDER = {"D1": 0, "H4": 1, "H1": 2, "M15": 3}
O2_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "open_decisions" / "o2_htf_sweep_stage"

CLUSTER_FIELDS = [
    "view", "cluster_id", "size", "tfs", "directions", "direction_conflict",
    "multi_tf", "zone_low", "zone_high", "members",
    "kept_cf1", "kept_cf2", "kept_cf3",
]
ARM_FIELDS = [
    "poi_id", "detection_tf", "direction", "zone_low", "zone_high",
    "zone_height", "arm_time", "routed", "passed_c3", "filled",
    "cluster_all", "cluster_batch",
    "dropped_cf1_all", "dropped_cf2_all", "dropped_cf3_all",
    "dropped_cf1_batch", "dropped_cf2_batch", "dropped_cf3_batch",
]
RULES = ("cf1", "cf2", "cf3")


def _height(row: dict) -> float:
    return float(row["zone_high"]) - float(row["zone_low"])


def _ranges_intersect(a: dict, b: dict) -> bool:
    return (min(float(a["zone_high"]), float(b["zone_high"]))
            > max(float(a["zone_low"]), float(b["zone_low"])))


def _overlap_ratio(a: dict, b: dict) -> float:
    inter = (min(float(a["zone_high"]), float(b["zone_high"]))
             - max(float(a["zone_low"]), float(b["zone_low"])))
    if inter <= 0:
        return 0.0
    smaller = min(_height(a), _height(b))
    return 0.0 if smaller <= 0 else inter / smaller


def _conflicts(a: dict, b: dict) -> str | None:
    """'direction' / 'same' when the pre-registered rule fires, else None."""
    if not _ranges_intersect(a, b):
        return None
    if a["direction"] != b["direction"]:
        return "direction"
    if _overlap_ratio(a, b) >= OVERLAP_MIN_RATIO:
        return "same"
    return None


def _pick(members: list[dict], rule: str) -> dict:
    if rule == "cf1":
        return sorted(members, key=lambda r: (TF_ORDER.get(r["detection_tf"], 99),
                                              r["arm_time"], r["poi_id"]))[0]
    if rule == "cf2":
        return sorted(members, key=lambda r: (_height(r), r["arm_time"],
                                              r["poi_id"]))[0]
    return sorted(members, key=lambda r: (r["arm_time"], r["poi_id"]))[0]


def _analyse(arms: list[dict], same_batch_only: bool) -> dict:
    """Union-find over the overlap relation, then the three counterfactuals."""
    parent = list(range(len(arms)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    pair_kinds = {"direction": 0, "same": 0}
    tf_pairs: dict[str, int] = {}
    direction_pairs: dict[str, int] = {}
    for i in range(len(arms)):
        for j in range(i + 1, len(arms)):
            if same_batch_only and arms[i]["arm_time"] != arms[j]["arm_time"]:
                continue
            kind = _conflicts(arms[i], arms[j])
            if kind is None:
                continue
            pair_kinds[kind] += 1
            union(i, j)
            a, b = arms[i]["detection_tf"], arms[j]["detection_tf"]
            key = "∩".join(sorted((a, b), key=lambda t: TF_ORDER.get(t, 99)))
            tf_pairs[key] = tf_pairs.get(key, 0) + 1
            if kind == "direction":
                dkey = "×".join(sorted((arms[i]["direction"], arms[j]["direction"])))
                direction_pairs[dkey] = direction_pairs.get(dkey, 0) + 1

    groups: dict[int, list[int]] = {}
    for idx in range(len(arms)):
        groups.setdefault(find(idx), []).append(idx)

    clusters, cluster_of, kept, dropped = [], {}, {r: set() for r in RULES}, {r: set() for r in RULES}
    for nth, members_idx in enumerate(sorted(groups.values(),
                                            key=lambda g: arms[g[0]]["arm_time"])):
        if len(members_idx) < 2:
            for idx in members_idx:
                cluster_of[arms[idx]["poi_id"]] = ""
            continue
        members = [arms[idx] for idx in members_idx]
        cid = f"c{nth:04d}"
        for idx in members_idx:
            cluster_of[arms[idx]["poi_id"]] = cid
        clusters.append({
            "cluster_id": cid,
            "members": sorted(members, key=lambda r: (r["arm_time"], r["poi_id"])),
            "direction_conflict": any(
                a["direction"] != b["direction"]
                for i, a in enumerate(members) for b in members[i + 1:]
                if _ranges_intersect(a, b)
            ),
        })
        for rule in RULES:
            keeper = _pick(members, rule)
            kept[rule].add(keeper["poi_id"])
            for member in members:
                if member["poi_id"] != keeper["poi_id"]:
                    dropped[rule].add(member["poi_id"])

    all_ids = {a["poi_id"] for a in arms}
    in_cluster = {a["poi_id"] for a in arms if cluster_of.get(a["poi_id"])}
    routed = {a["poi_id"] for a in arms if a["routed"]}
    passed = {a["poi_id"] for a in arms if a["passed_c3"]}
    fills = {a["poi_id"] for a in arms if a["filled"]}

    counterfactuals = {}
    for rule in RULES:
        survive = (all_ids - in_cluster) | kept[rule]
        gone = all_ids - survive
        counterfactuals[rule.upper()] = {
            "arms_kept": len(survive),
            "arms_dropped": len(gone),
            "routed_retained": len(routed & survive),
            "routed_dropped": len(routed & gone),
            "passed_c3_retained": len(passed & survive),
            "passed_c3_dropped": len(passed & gone),
            "fills_retained": len(fills & survive),
            "fills_dropped": len(fills & gone),
        }

    return {
        "counts": {
            "N_overlap_clusters": len(clusters),
            "N_arms_in_clusters": len(in_cluster),
            "share_arms_in_clusters": len(in_cluster) / len(arms) if arms else None,
            "N_singletons": len(arms) - len(in_cluster),
            "N_multi_tf_clusters": sum(
                1 for c in clusters
                if len({m["detection_tf"] for m in c["members"]}) > 1),
            "same_direction_pairs": pair_kinds["same"],
            "direction_conflict_pairs": pair_kinds["direction"],
            "N_direction_conflict_clusters": sum(
                1 for c in clusters if c["direction_conflict"]),
            "largest_cluster": max((len(c["members"]) for c in clusters), default=0),
        },
        "tf_pair_matrix": tf_pairs,
        "direction_pair_matrix": direction_pairs,
        "counterfactuals": counterfactuals,
        "clusters": clusters,
        "cluster_of": cluster_of,
        "dropped": dropped,
    }


def load_armed() -> tuple[list[dict], str]:
    csv_path = O2_DIR / "armed_sweep_join.csv"
    summary_path = O2_DIR / "summary.json"
    payload = csv_path.read_text(encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    expected = json.loads(summary_path.read_text(encoding="utf-8"))["checksum_armed_csv"]
    if digest != expected:
        raise SystemExit(f"O2 armed table checksum mismatch: {digest} != {expected}")
    rows = []
    for row in csv.DictReader(payload.splitlines()):
        rows.append({
            "poi_id": row["poi_id"],
            "detection_tf": row["detection_tf"],
            "direction": row["direction"],
            "zone_low": row["zone_low"],
            "zone_high": row["zone_high"],
            "arm_time": row["arm_time"],
            "routed": row["routed"] == "true",
            "passed_c3": row["passed_c3"] == "true",
            "filled": row["filled"] == "true",
        })
    return rows, digest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="O3 multi-zone priority")
    parser.add_argument("--tag", default="o3_multi_zone_priority")
    args = parser.parse_args(argv)
    out_dir = REPO_ROOT / "06_RESEARCH" / "results" / "open_decisions" / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)

    arms, source_checksum = load_armed()
    view_all = _analyse(arms, same_batch_only=False)
    view_batch = _analyse(arms, same_batch_only=True)

    fills = {a["poi_id"] for a in arms if a["filled"]}
    summary = {
        "window": {"load_from": "2025-05-01", "exec_from": "2025-10-01",
                   "exec_to": "2025-10-31"},
        "source": {"armed_table": str(O2_DIR / "armed_sweep_join.csv"),
                   "sha256": source_checksum,
                   "note": "O2 frozen composition run, full D1/H4/H1/M15 set"},
        "preregistered": {"overlap_min_ratio": OVERLAP_MIN_RATIO,
                          "tf_order": list(TF_ORDER),
                          "rules": ["CF0_ACTUAL", "CF1_HIGHEST_TF",
                                    "CF2_TIGHTEST", "CF3_FIRST_ARMED"],
                          "views": {"A_all_price_overlap": "PRIMARY",
                                    "B_same_batch": "SECONDARY (exploratory)"}},
        "current_behaviour": {
            "dedup": "multi_tf_runtime.ZoneDedup — same-direction overlapping "
                     "spans are one episode owned by the first registration; "
                     "keys retire with their owner",
            "priority": "none (first-armed wins; no TF rank in the runtime)",
        },
        "counts": {
            "N_armed": len(arms),
            "N_routed": sum(1 for a in arms if a["routed"]),
            "N_passed_c3": sum(1 for a in arms if a["passed_c3"]),
            "N_filled": len(fills),
            "viewA_all_price_overlap": view_all["counts"],
            "viewB_same_batch": view_batch["counts"],
        },
        "tf_pair_matrix": {"A_all": view_all["tf_pair_matrix"],
                           "B_same_batch": view_batch["tf_pair_matrix"]},
        "direction_pair_matrix": {"A_all": view_all["direction_pair_matrix"],
                                  "B_same_batch": view_batch["direction_pair_matrix"]},
        "counterfactuals": {"viewA_all": view_all["counterfactuals"],
                            "viewB_same_batch": view_batch["counterfactuals"]},
        "reconciliation": {
            "arms_csv_rows": len(arms),
            "clusters_csv_rows": max(len(view_all["clusters"]), len(view_batch["clusters"])),
            "arms_in_viewA_clusters": view_all["counts"]["N_arms_in_clusters"],
            "arms_in_viewB_clusters": view_batch["counts"]["N_arms_in_clusters"],
        },
    }

    cluster_rows = []
    for label, view in (("A_all", view_all), ("B_same_batch", view_batch)):
        keep_lookup = {rule: {c["cluster_id"]: _pick(c["members"], rule)["poi_id"]
                              for c in view["clusters"]} for rule in RULES}
        for cluster in view["clusters"]:
            members = cluster["members"]
            cluster_rows.append({
                "view": label,
                "cluster_id": cluster["cluster_id"],
                "size": len(members),
                "tfs": "+".join(sorted({m["detection_tf"] for m in members},
                                       key=lambda t: TF_ORDER.get(t, 99))),
                "directions": "+".join(sorted({m["direction"] for m in members})),
                "direction_conflict": cluster["direction_conflict"],
                "multi_tf": len({m["detection_tf"] for m in members}) > 1,
                "zone_low": min(float(m["zone_low"]) for m in members),
                "zone_high": max(float(m["zone_high"]) for m in members),
                "members": "+".join(m["poi_id"] for m in members),
                "kept_cf1": keep_lookup["cf1"][cluster["cluster_id"]],
                "kept_cf2": keep_lookup["cf2"][cluster["cluster_id"]],
                "kept_cf3": keep_lookup["cf3"][cluster["cluster_id"]],
            })

    arm_rows = []
    for arm in arms:
        row = {k: arm[k] for k in ("poi_id", "detection_tf", "direction",
                                   "zone_low", "zone_high", "arm_time",
                                   "routed", "passed_c3", "filled")}
        row["zone_height"] = _height(arm)
        row["cluster_all"] = view_all["cluster_of"].get(arm["poi_id"], "")
        row["cluster_batch"] = view_batch["cluster_of"].get(arm["poi_id"], "")
        for rule in RULES:
            row[f"dropped_{rule}_all"] = arm["poi_id"] in view_all["dropped"][rule]
            row[f"dropped_{rule}_batch"] = arm["poi_id"] in view_batch["dropped"][rule]
        arm_rows.append(row)

    def write_csv(path, fields, rows):
        lines = [",".join(fields)]
        for row in rows:
            cells = []
            for field in fields:
                value = row.get(field, "")
                if isinstance(value, bool):
                    value = "true" if value else "false"
                text = str(value)
                if "," in text:
                    text = '"' + text.replace('"', '""') + '"'
                cells.append(text)
            lines.append(",".join(cells))
        payload = "\n".join(lines) + "\n"
        path.write_text(payload, encoding="utf-8")
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    summary["checksum_clusters_csv"] = write_csv(out_dir / "clusters.csv",
                                                 CLUSTER_FIELDS, cluster_rows)
    summary["checksum_arms_csv"] = write_csv(out_dir / "arms.csv",
                                             ARM_FIELDS, arm_rows)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")

    print(json.dumps({"out_dir": str(out_dir), "counts": summary["counts"],
                      "tf_pair_matrix": summary["tf_pair_matrix"],
                      "counterfactuals": summary["counterfactuals"]},
                     indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
