"""Offline, time-split evaluation of InstaKill feed strategies."""
from __future__ import annotations

import argparse
import base64
from contextlib import closing
import hashlib
import html
import json
import io
import math
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.services.post_service import PostService
from app.services.model_scorer import load_model

STRATEGIES = ("chronological", "popularity", "for_you", "learned")
USER_GROUPS = ("new (<10 likes)", "casual (10-49)", "regular (50-199)", "power (200+)")
COLORS = {"chronological": "#4c78a8", "popularity": "#f58518", "for_you": "#54a24b", "learned": "#b279a2"}


def ndcg_at_10(ranked_ids, relevant_ids) -> float:
    """Binary NDCG@10 with an ideal ranking containing up to ten relevant items."""
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    dcg = sum(1.0 / math.log2(rank + 2) for rank, post_id in enumerate(ranked_ids[:10]) if post_id in relevant)
    ideal_n = min(len(relevant), 10)
    ideal = sum(1.0 / math.log2(rank + 2) for rank in range(ideal_n))
    return dcg / ideal


def group_for(n_likes: int) -> str:
    if n_likes < 10:
        return "new (<10 likes)"
    if n_likes < 50:
        return "casual (10-49)"
    if n_likes < 200:
        return "regular (50-199)"
    return "power (200+)"


def create_snapshot(source: Path, destination: Path, cutoff: str) -> None:
    """Copy the DB and retain only posts, likes and follows strictly before cutoff."""
    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(destination)) as dst:
        src.backup(dst)
        dst.execute("PRAGMA foreign_keys=OFF")
        historical_users = dst.execute(
            '''SELECT u.id,u.username,MIN(activity.created_at)
               FROM user u JOIN (
                   SELECT user_id AS id,created_at FROM "like" WHERE julianday(created_at)<julianday(?)
                   UNION ALL SELECT user_id AS id,created_at FROM post WHERE julianday(created_at)<julianday(?)
                   UNION ALL SELECT follower_id AS id,created_at FROM follow WHERE julianday(created_at)<julianday(?)
                   UNION ALL SELECT followee_id AS id,created_at FROM follow WHERE julianday(created_at)<julianday(?)
               ) activity ON activity.id=u.id GROUP BY u.id,u.username ORDER BY u.id''',
            (cutoff, cutoff, cutoff, cutoff),
        ).fetchall()
        dst.execute('DELETE FROM "like" WHERE julianday(created_at) >= julianday(?)', (cutoff,))
        dst.execute("DELETE FROM post WHERE julianday(created_at) >= julianday(?)", (cutoff,))
        dst.execute("DELETE FROM follow WHERE julianday(created_at) >= julianday(?)", (cutoff,))
        dst.execute("DELETE FROM user")
        dst.executemany("INSERT INTO user(id,username,created_at) VALUES (?,?,?)", historical_users)
        dst.commit()


def default_cutoff(conn: sqlite3.Connection) -> str:
    rows = [r[0] for r in conn.execute('SELECT created_at FROM "like" ORDER BY created_at, user_id, post_id')]
    if not rows:
        raise ValueError("Database contains no likes; cannot choose an 80% cutoff")
    return rows[max(0, math.ceil(0.8 * len(rows)) - 1)]


def bootstrap_interval(values, rng: np.random.Generator, iterations: int = 2000):
    values = np.asarray(values, dtype=float)
    if not len(values):
        return (float("nan"), float("nan"))
    draws = rng.integers(0, len(values), size=(iterations, len(values)))
    means = values[draws].mean(axis=1)
    return tuple(float(x) for x in np.quantile(means, [0.025, 0.975]))


def verdict(low: float, high: float) -> str:
    return "wins" if low > 0 else "loses" if high < 0 else "unclear"


def git_code_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "log", "-1", "--format=%H", "--", "scripts/evaluate.py", "app/services/post_service.py", "app/db/database.py"],
            cwd=ROOT, text=True, stderr=subprocess.DEVNULL,
        ).strip() or "uncommitted"
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def evaluation_fingerprint(db_path: Path, cutoff: str) -> str:
    """Hash canonical evaluation-relevant rows, independent of SQLite page layout."""
    with sqlite3.connect(db_path) as conn:
        payload = {
            "users": [tuple(r) for r in conn.execute("SELECT id FROM user ORDER BY id")],
            "posts": [tuple(r) for r in conn.execute(
                "SELECT id,user_id,content,created_at FROM post WHERE julianday(created_at)<julianday(?) ORDER BY id", (cutoff,))],
            "likes": [tuple(r) for r in conn.execute(
                'SELECT l.user_id,l.post_id,l.created_at FROM "like" l JOIN post p ON p.id=l.post_id '
                'WHERE julianday(p.created_at)<julianday(?) ORDER BY l.user_id,l.post_id', (cutoff,))],
            "follows": [tuple(r) for r in conn.execute(
                "SELECT follower_id,followee_id,created_at FROM follow WHERE julianday(created_at)<julianday(?) ORDER BY follower_id,followee_id", (cutoff,))],
        }
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def evaluate(db_path: Path, cutoff_arg: str | None, seed: int, out_dir: Path):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cutoff = cutoff_arg or default_cutoff(conn)
        source_users = conn.execute("SELECT COUNT(*) FROM user").fetchone()[0]
        source_posts = conn.execute("SELECT COUNT(*) FROM post").fetchone()[0]
        # Parse and normalize an explicit ISO date/time to UTC for consistent SQL ordering.
        parsed = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        cutoff = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        all_posts = {r["id"]: r["user_id"] for r in conn.execute("SELECT id,user_id FROM post WHERE julianday(created_at) < julianday(?)", (cutoff,))}
        before = conn.execute('SELECT user_id,post_id FROM "like" WHERE julianday(created_at) < julianday(?)', (cutoff,)).fetchall()
        after = conn.execute('SELECT user_id,post_id FROM "like" WHERE julianday(created_at) >= julianday(?)', (cutoff,)).fetchall()
        before_counts: dict[int, int] = {}
        for row in before:
            before_counts[row["user_id"]] = before_counts.get(row["user_id"], 0) + 1
        relevant: dict[int, set[int]] = {}
        for row in after:
            uid, pid = row["user_id"], row["post_id"]
            if pid in all_posts:
                relevant.setdefault(uid, set()).add(pid)
        users = sorted(uid for uid, n in before_counts.items() if n >= 3 and relevant.get(uid))

    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    if not load_model():
        raise RuntimeError("Could not load like_model.npz required for learned evaluation")
    rows = []
    with tempfile.TemporaryDirectory(prefix="instakill-eval-") as tmp:
        snapshot = Path(tmp) / "snapshot.db"
        create_snapshot(db_path, snapshot, cutoff)
        snapshot_conn = sqlite3.connect(snapshot)
        snapshot_conn.row_factory = sqlite3.Row
        popularity = {r["post_id"]: r["n"] for r in snapshot_conn.execute('SELECT post_id,COUNT(*) n FROM "like" GROUP BY post_id')}
        service = PostService()
        replay_now = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
        for uid in users:
            group = group_for(before_counts[uid])
            relevant_ids = relevant[uid]
            # Three strategies are evaluated through the same service method GET /feed uses.
            for strategy in ("chronological", "for_you", "learned"):
                feed = service.get_feed(uid, limit=10, strategy=strategy, now=replay_now, db_path=str(snapshot))
                score = ndcg_at_10([p["post_id"] for p in feed], relevant_ids)
                rows.append({"user_id": uid, "strategy": strategy, "ndcg_at_10": score,
                             "n_relevant": len(relevant_ids), "user_group": group})
            # popularity is a report-only baseline; it never enters GET /feed.
            liked = {r[0] for r in snapshot_conn.execute('SELECT post_id FROM "like" WHERE user_id=?', (uid,))}
            candidates = [(pid, owner) for pid, owner in all_posts.items() if owner != uid and pid not in liked]
            candidates.sort(key=lambda item: (-popularity.get(item[0], 0), item[0]))
            rows.append({"user_id": uid, "strategy": "popularity",
                         "ndcg_at_10": ndcg_at_10([p for p, _ in candidates[:10]], relevant_ids),
                         "n_relevant": len(relevant_ids), "user_group": group})
        snapshot_conn.close()

    rows.sort(key=lambda r: (r["user_id"], STRATEGIES.index(r["strategy"])))
    csv_path = out_dir / "eval_results.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        f.write("user_id,strategy,ndcg_at_10,n_relevant,user_group\n")
        for row in rows:
            f.write(f'{row["user_id"]},{row["strategy"]},{row["ndcg_at_10"]:.12g},{row["n_relevant"]},{row["user_group"]}\n')

    fingerprint = evaluation_fingerprint(db_path, cutoff)
    revision = git_code_revision()
    relevant_likes = sum(len(relevant[uid]) for uid in users)
    table = build_report(rows, cutoff, seed, fingerprint, revision, rng, relevant_likes,
                         source_users, source_posts, len(all_posts))
    (out_dir / "baseline_table.md").write_text(table, encoding="utf-8", newline="\n")
    dashboard = build_dashboard(rows, cutoff, seed, fingerprint, revision, table, rng)
    (out_dir / "dashboard.html").write_text(dashboard, encoding="utf-8", newline="\n")
    return rows


def matrix(rows):
    users = sorted({r["user_id"] for r in rows})
    lookup = {(r["user_id"], r["strategy"]): r for r in rows}
    return users, lookup


def summarize(values, rng):
    mean = float(np.mean(values)) if len(values) else float("nan")
    lo, hi = bootstrap_interval(values, rng)
    return mean, lo, hi


def comparison(rows, selected_users, rng):
    _, lookup = matrix(rows)
    chosen = [uid for uid in selected_users if (uid, "learned") in lookup]
    if not chosen:
        return (0.0, 0.0, 0.0, 0, "unclear", "none")
    baseline = max(("chronological", "popularity", "for_you"),
                   key=lambda s: np.mean([lookup[(u, s)]["ndcg_at_10"] for u in chosen]))
    diffs = [lookup[(u, "learned")]["ndcg_at_10"] - lookup[(u, baseline)]["ndcg_at_10"] for u in chosen]
    mean, low, high = summarize(diffs, rng)
    return mean, low, high, len(chosen), verdict(low, high), baseline


def build_report(rows, cutoff, seed, fingerprint, revision, rng, relevant_likes=0,
                 source_users=0, source_posts=0, snapshot_posts=0):
    _, lookup = matrix(rows)
    users = sorted({r["user_id"] for r in rows})
    lines = ["# InstaKill offline evaluation", "", "## Mean NDCG@10 by strategy", "",
             "| Strategy | Mean | 95% user bootstrap interval | Users |", "|---|---:|---:|---:|"]
    for strategy in STRATEGIES:
        vals = [lookup[(u, strategy)]["ndcg_at_10"] for u in users]
        mean, lo, hi = summarize(vals, rng)
        lines.append(f"| {strategy} | {mean:.4f} | [{lo:.4f}, {hi:.4f}] | {len(vals)} |")
    lines.extend(["", "## learned minus best baseline", "", "| Slice | Best baseline | Mean difference | 95% paired interval | Users | Verdict |", "|---|---|---:|---:|---:|---|"])
    groups = ["overall", *USER_GROUPS]
    for group in groups:
        selected = users if group == "overall" else [u for u in users if lookup[(u, "learned")]["user_group"] == group]
        if not selected:
            lines.append(f"| {group} | N/A | N/A | N/A | 0 | not estimable |")
            continue
        mean, lo, hi, n, result, base = comparison(rows, selected, rng)
        lines.append(f"| {group} | {base} | {mean:.4f} | [{lo:.4f}, {hi:.4f}] | {n} | {result} |")
    lines.extend(["", "## Run metadata", "", f"- Cut-off (UTC): `{cutoff}`", f"- Bootstrap seed: `{seed}` (2,000 paired user resamples)",
                  f"- Evaluated users: `{len(users)}`", f"- Database SHA-256: `{fingerprint}`", f"- Evaluation code commit: `{revision}`", ""])
    lines.insert(-1, f"- Future relevant likes for evaluated users: `{relevant_likes}`")
    lines.insert(-1, "- Model training cutoff: `not stored in like_model.npz`")
    lines.insert(-1, f"- Source database: `{source_users}` users, `{source_posts}` posts")
    lines.insert(-1, f"- Snapshot posts before T: `{snapshot_posts}`")
    return "\n".join(lines)


def chart_png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def render_report_html(markdown: str) -> str:
    """Render this report's small Markdown subset as readable static HTML."""
    output = []
    table_rows = []
    list_open = False

    def flush_table():
        if not table_rows:
            return
        header, *body = table_rows
        output.append("<table><thead><tr>" + "".join(f"<th>{cell}</th>" for cell in header) + "</tr></thead><tbody>")
        for row in body:
            output.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>")
        output.append("</tbody></table>")
        table_rows.clear()

    def close_list():
        nonlocal list_open
        if list_open:
            output.append("</ul>")
            list_open = False

    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            close_list()
            cells = [html.escape(cell.strip()) for cell in stripped.strip("|").split("|")]
            if all(set(cell.replace(":", "").strip()) <= {"-"} for cell in cells):
                continue
            table_rows.append(cells)
            continue
        flush_table()
        if not stripped:
            close_list()
        elif stripped.startswith("# "):
            close_list(); output.append(f"<h1>{html.escape(stripped[2:])}</h1>")
        elif stripped.startswith("## "):
            close_list(); output.append(f"<h3>{html.escape(stripped[3:])}</h3>")
        elif stripped.startswith("- "):
            if not list_open:
                output.append("<ul>"); list_open = True
            item = html.escape(stripped[2:]).replace("`", "")
            output.append(f"<li>{item}</li>")
        else:
            close_list()
            output.append(f"<p>{html.escape(stripped).replace('`', '')}</p>")
    flush_table()
    close_list()
    return "".join(output)


def build_dashboard(rows, cutoff, seed, fingerprint, revision, table, rng):
    users, lookup = matrix(rows)
    means, lows, highs = [], [], []
    for s in STRATEGIES:
        m, lo, hi = summarize([lookup[(u, s)]["ndcg_at_10"] for u in users], rng)
        means.append(m); lows.append(m-lo); highs.append(hi-m)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(4)
    ax.bar(x, means, color=[COLORS[s] for s in STRATEGIES])
    ax.errorbar(x, means, yerr=[lows, highs], fmt="none", ecolor="#222", capsize=4)
    ax.set(title="Which feed strategy ranks later likes highest?", ylabel="Mean NDCG@10", xlabel="Feed strategy", xticks=x, xticklabels=STRATEGIES)
    ax.set_ylim(0, max(0.05, max(means, default=0)+max(highs, default=0)+0.05))
    image1 = chart_png(fig)

    groups = list(USER_GROUPS)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    cmap = plt.get_cmap("RdYlGn")
    visible_bounds = [0.0]
    for i, group in enumerate(groups):
        selected = [u for u in users if lookup[(u, "learned")]["user_group"] == group]
        if not selected:
            ax.text(0.02, i, "n=0; not estimable", transform=ax.get_yaxis_transform(),
                    ha="left", va="center", color="#555", fontsize=9)
            continue
        mean, lo, hi, _, _, _ = comparison(rows, selected, rng)
        ax.barh(i, mean, color=cmap((float(np.clip(mean, -1, 1)) + 1) / 2))
        ax.errorbar(mean, i, xerr=[[mean-lo], [hi-mean]], fmt="none", ecolor="#222", capsize=4)
        visible_bounds.extend([lo, hi])
    ax.axvline(0, color="#333", linewidth=1)
    bound = max(0.05, max(abs(value) for value in visible_bounds) * 1.1)
    ax.set_xlim(-bound, bound)
    ax.set(title="Where does learned beat the best baseline?", xlabel="NDCG@10 difference (learned − baseline)", ylabel="User activity slice", yticks=np.arange(len(groups)), yticklabels=groups)
    image2 = chart_png(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    counts = [sum(lookup[(u, "learned")]["user_group"] == g for u in users) for g in groups]
    ax.bar(np.arange(len(groups)), counts, color=COLORS["learned"])
    for i, count in enumerate(counts):
        ax.text(i, count + 0.05, str(count), ha="center", va="bottom")
    ax.set_ylim(0, max(counts, default=0) + 1)
    ax.set(title="How many evaluated users are in each activity slice?", xlabel="User activity slice", ylabel="Users", xticks=np.arange(len(groups)), xticklabels=groups)
    image3 = chart_png(fig)
    metadata = f"Cut-off UTC: {cutoff} · Seed: {seed} · Users: {len(users)} · DB SHA-256: {fingerprint} · Code commit: {revision}"
    chart_sections = "".join([
        f'<section><h2>{title}</h2><img alt="{alt}" src="{image}"></section>'
        for title, alt, image in [
            ("Which feed strategy ranks later likes highest?", "Mean NDCG by strategy with 95% intervals", image1),
            ("Where does learned beat the best baseline?", "Learned minus best baseline per user slice with intervals", image2),
            ("How many evaluated users are in each activity slice?", "User counts by slice", image3),
        ]
    ])
    report_html = render_report_html(table)
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width"><title>InstaKill evaluation</title>'
        '<style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#222}'
        'img{max-width:100%;height:auto}table{border-collapse:collapse;width:100%;margin:1rem 0}'
        'th,td{padding:.55rem .7rem;border:1px solid #ddd;text-align:left}th{background:#f2f4f7}'
        'tr:nth-child(even){background:#fafafa}li{margin:.3rem 0}'
        'section{margin:2rem 0}</style><h1>InstaKill offline evaluation</h1><p>'
        + metadata + '</p>' + chart_sections + '<section><h2>Baseline table and run details</h2>'
        + report_html + '</section></html>'
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="instakill.db")
    parser.add_argument("--cutoff", help="ISO date or datetime; default is the 80th percentile of likes")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="reports/")
    args = parser.parse_args()
    evaluate(Path(args.db).resolve(), args.cutoff, args.seed, Path(args.out).resolve())


if __name__ == "__main__":
    main()
