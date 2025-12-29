import os
import json
import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple



# =============================
# 자동 탐색 / 자동 생성 설정
# =============================
BASE_DIR = Path(r"D:\SajuOS_Data")

# JSONL을 못 찾으면, 아래 폴더(또는 유사 폴더)에서 JSON을 긁어서 JSONL로 만듦
RULECARDS_ROOT_CANDIDATES = [
    BASE_DIR / "3_SajuOS_RuleCards_JSON",
    BASE_DIR / "SajuOS_RuleCards_JSON",
    BASE_DIR / "RuleCards_JSON",
]

DEFAULT_JSONL_OUT = BASE_DIR / "sajuos_master_db.jsonl"
SQLITE_DB = BASE_DIR / "sajuos_master.db"

BATCH_SIZE = 500

# ===== 상품 매핑 테이블 (v1) =====
PRODUCT_TOPICS = {
    "YEAR_2026":      {"must": ["TIMING", "RELATION"], "opt": ["ELEMENTS", "GENERAL", "STRUCTURE"]},
    "LIFETIME":       {"must": ["STRUCTURE", "GENERAL"], "opt": ["ELEMENTS", "TEN_GODS", "RELATION"]},
    "TEN_YEAR":       {"must": ["TIMING", "STRUCTURE"], "opt": ["RELATION", "WEALTH", "CAREER", "GENERAL"]},
    "WEALTH":         {"must": ["WEALTH"], "opt": ["STRUCTURE", "TIMING", "GENERAL"]},
    "CAREER":         {"must": ["CAREER"], "opt": ["STRUCTURE", "TIMING", "GENERAL"]},
    "EXAM":           {"must": ["CAREER", "TIMING"], "opt": ["STRUCTURE", "GENERAL"]},
    "LOVE_SPOUSE":    {"must": ["LOVE", "RELATION"], "opt": ["TIMING", "ELEMENTS", "GENERAL"]},
    "LOVE_TIMING":    {"must": ["TIMING", "LOVE", "RELATION"], "opt": ["GENERAL", "ELEMENTS"]},
    "TOTAL":          {"must": ["GENERAL", "STRUCTURE"], "opt": ["WEALTH", "CAREER", "LOVE", "RELATION", "TIMING"]},
}

def connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path), timeout=30)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.execute("PRAGMA temp_store=MEMORY;")
    con.execute("PRAGMA cache_size=-200000;")  # ~200MB
    return con

def create_tables(con: sqlite3.Connection):
    con.execute("""
    CREATE TABLE IF NOT EXISTS rule_cards (
        id TEXT PRIMARY KEY,
        topic TEXT NOT NULL,
        priority INTEGER NOT NULL DEFAULT 5,
        trigger_json TEXT NOT NULL,
        mechanism TEXT NOT NULL,
        interpretation TEXT NOT NULL,
        action TEXT NOT NULL,
        tags_json TEXT NOT NULL,
        cautions_json TEXT NOT NULL,
        source_file TEXT,
        source_path TEXT,
        source_title TEXT
    );
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_rule_cards_topic ON rule_cards(topic);")
    con.execute("CREATE INDEX IF NOT EXISTS idx_rule_cards_priority ON rule_cards(priority DESC);")
    con.execute("CREATE INDEX IF NOT EXISTS idx_rule_cards_topic_priority ON rule_cards(topic, priority DESC);")

def try_create_fts(con: sqlite3.Connection) -> bool:
    try:
        con.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS rule_cards_fts USING fts5(
            id UNINDEXED,
            topic UNINDEXED,
            mechanism,
            interpretation,
            action,
            tags,
            content=''
        );
        """)
        return True
    except sqlite3.OperationalError:
        return False

def upsert_fts(con: sqlite3.Connection):
    con.execute("DELETE FROM rule_cards_fts;")
    con.execute("""
        INSERT INTO rule_cards_fts (id, topic, mechanism, interpretation, action, tags)
        SELECT
            id,
            topic,
            mechanism,
            interpretation,
            action,
            tags_json
        FROM rule_cards;
    """)

def find_any_jsonl(base: Path) -> Optional[Path]:
    # 우선 "sajuos_master_db.jsonl" 우선 탐색
    preferred = base / "sajuos_master_db.jsonl"
    if preferred.exists():
        return preferred

    # 그 외 jsonl 전체 탐색 (너무 느리지 않게 상위 몇 단계만)
    jsonls = list(base.rglob("*.jsonl"))
    if not jsonls:
        return None

    # 파일 크기 큰 것(= 카드 많을 가능성) 우선
    jsonls.sort(key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)
    return jsonls[0]

def guess_rulecards_root() -> Optional[Path]:
    for cand in RULECARDS_ROOT_CANDIDATES:
        if cand.exists():
            return cand

    # 후보가 없으면, BASE_DIR 아래에서 "RuleCards" 비슷한 폴더 찾아보기
    for p in BASE_DIR.rglob("*"):
        if p.is_dir() and ("rulecard" in p.name.lower() or "rulecards" in p.name.lower()):
            return p
    return None

def build_jsonl_from_rulecards(rulecards_root: Path, out_jsonl: Path) -> int:
    """
    폴더 안의 *.rulecards.json / *.json에서 rulecards 배열을 평탄화하여 jsonl 생성
    """
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)

    total_cards = 0
    with open(out_jsonl, "w", encoding="utf-8") as out:
        for fp in rulecards_root.rglob("*.json"):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            # 파일 레벨 메타
            source_title = data.get("title")
            source_file = fp.name
            source_path = str(fp)

            cards = data.get("rulecards")
            if not isinstance(cards, list):
                # 혹시 이미 카드 단일 구조면 스킵
                continue

            for card in cards:
                if not isinstance(card, dict):
                    continue

                # 출처 메타 부착
                card = dict(card)
                card["source_file"] = source_file
                card["source_path"] = source_path
                if source_title:
                    card["source_title"] = source_title

                out.write(json.dumps(card, ensure_ascii=False) + "\n")
                total_cards += 1

    return total_cards

def load_jsonl_to_sqlite(con: sqlite3.Connection, jsonl_path: Path):
    if not jsonl_path.exists():
        raise FileNotFoundError(f"JSONL 파일이 없습니다: {jsonl_path}")

    insert_sql = """
    INSERT OR IGNORE INTO rule_cards (
        id, topic, priority, trigger_json, mechanism, interpretation, action,
        tags_json, cautions_json, source_file, source_path, source_title
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    inserted = 0
    total = 0
    bad = 0
    batch: List[Tuple] = []

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                obj = json.loads(line)
                rid = str(obj.get("id", "")).strip()
                if not rid:
                    bad += 1
                    continue

                topic = str(obj.get("topic") or "GENERAL").strip() or "GENERAL"
                priority = int(obj.get("priority", 5))

                trigger_json = json.dumps(obj.get("trigger", {}), ensure_ascii=False)
                tags_json = json.dumps(obj.get("tags", []), ensure_ascii=False)
                cautions_json = json.dumps(obj.get("cautions", []), ensure_ascii=False)

                mechanism = str(obj.get("mechanism", "") or "")
                interpretation = str(obj.get("interpretation", "") or "")
                action = str(obj.get("action", "") or "")

                source_file = obj.get("source_file")
                source_path = obj.get("source_path")
                source_title = obj.get("source_title")

                batch.append((
                    rid, topic, priority, trigger_json, mechanism, interpretation, action,
                    tags_json, cautions_json, source_file, source_path, source_title
                ))

                if len(batch) >= BATCH_SIZE:
                    con.executemany(insert_sql, batch)
                    con.commit()
                    inserted += len(batch)
                    batch.clear()

            except Exception:
                bad += 1
                continue

    if batch:
        con.executemany(insert_sql, batch)
        con.commit()
        inserted += len(batch)

    print("✅ SQLite 적재 완료")
    print(f"- JSONL 라인: {total}")
    print(f"- 삽입 시도: {inserted} (중복은 IGNORE됨)")
    print(f"- 파손/스킵: {bad}")

def stats(con: sqlite3.Connection):
    total = con.execute("SELECT COUNT(*) FROM rule_cards;").fetchone()[0]
    print(f"\n📌 rule_cards 총 개수: {total}")

    print("\n📌 topic 상위 20개:")
    cur = con.execute("""
        SELECT topic, COUNT(*) as c
        FROM rule_cards
        GROUP BY topic
        ORDER BY c DESC
        LIMIT 20;
    """)
    for topic, c in cur.fetchall():
        print(f"- {topic}: {c}")

def pick_by_product(con: sqlite3.Connection, product_id: str, k: int = 15) -> List[Dict[str, Any]]:
    mp = PRODUCT_TOPICS.get(product_id)
    if not mp:
        raise ValueError(f"알 수 없는 product_id: {product_id}")

    must = mp["must"]
    opt = mp["opt"]
    topics = must + opt

    placeholders = ",".join(["?"] * len(topics))
    cur = con.execute(f"""
        SELECT id, topic, priority, trigger_json, mechanism, interpretation, action, tags_json, cautions_json
        FROM rule_cards
        WHERE topic IN ({placeholders})
        ORDER BY
            CASE
                WHEN topic IN ({",".join(["?"] * len(must))}) THEN 0
                ELSE 1
            END ASC,
            priority DESC
        LIMIT ?;
    """, topics + must + [k])

    rows = cur.fetchall()
    out = []
    for r in rows:
        out.append({
            "id": r[0],
            "topic": r[1],
            "priority": r[2],
            "trigger": json.loads(r[3]) if r[3] else {},
            "mechanism": r[4],
            "interpretation": r[5],
            "action": r[6],
            "tags": json.loads(r[7]) if r[7] else [],
            "cautions": json.loads(r[8]) if r[8] else [],
        })
    return out

def search_fts(con: sqlite3.Connection, query: str, k: int = 15, topics: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    try:
        if topics:
            placeholders = ",".join(["?"] * len(topics))
            cur = con.execute(f"""
                SELECT id, topic, bm25(rule_cards_fts) as score
                FROM rule_cards_fts
                WHERE rule_cards_fts MATCH ? AND topic IN ({placeholders})
                ORDER BY score
                LIMIT ?;
            """, [query] + topics + [k])
        else:
            cur = con.execute("""
                SELECT id, topic, bm25(rule_cards_fts) as score
                FROM rule_cards_fts
                WHERE rule_cards_fts MATCH ?
                ORDER BY score
                LIMIT ?;
            """, [query, k])

        hits = cur.fetchall()
        if not hits:
            return []

        ids = [h[0] for h in hits]
        placeholders = ",".join(["?"] * len(ids))
        cur2 = con.execute(f"""
            SELECT id, topic, priority, trigger_json, mechanism, interpretation, action, tags_json, cautions_json
            FROM rule_cards
            WHERE id IN ({placeholders});
        """, ids)

        by_id = {row[0]: row for row in cur2.fetchall()}
        out = []
        for rid, topic, _score in hits:
            row = by_id.get(rid)
            if not row:
                continue
            out.append({
                "id": row[0],
                "topic": row[1],
                "priority": row[2],
                "trigger": json.loads(row[3]) if row[3] else {},
                "mechanism": row[4],
                "interpretation": row[5],
                "action": row[6],
                "tags": json.loads(row[7]) if row[7] else [],
                "cautions": json.loads(row[8]) if row[8] else [],
            })
        return out

    except sqlite3.OperationalError:
        q = f"%{query}%"
        if topics:
            placeholders = ",".join(["?"] * len(topics))
            cur = con.execute(f"""
                SELECT id, topic, priority, trigger_json, mechanism, interpretation, action, tags_json, cautions_json
                FROM rule_cards
                WHERE topic IN ({placeholders})
                  AND (mechanism LIKE ? OR interpretation LIKE ? OR action LIKE ? OR tags_json LIKE ?)
                ORDER BY priority DESC
                LIMIT ?;
            """, topics + [q, q, q, q, k])
        else:
            cur = con.execute("""
                SELECT id, topic, priority, trigger_json, mechanism, interpretation, action, tags_json, cautions_json
                FROM rule_cards
                WHERE (mechanism LIKE ? OR interpretation LIKE ? OR action LIKE ? OR tags_json LIKE ?)
                ORDER BY priority DESC
                LIMIT ?;
            """, [q, q, q, q, k])

        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append({
                "id": r[0],
                "topic": r[1],
                "priority": r[2],
                "trigger": json.loads(r[3]) if r[3] else {},
                "mechanism": r[4],
                "interpretation": r[5],
                "action": r[6],
                "tags": json.loads(r[7]) if r[7] else [],
                "cautions": json.loads(r[8]) if r[8] else [],
            })
        return out

def main():
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    # 1) JSONL 자동 탐색
    jsonl = find_any_jsonl(BASE_DIR)
    if jsonl:
        print(f"✅ JSONL 발견: {jsonl}")
    else:
        # 2) JSONL이 없으면 RuleCards 폴더에서 생성
        rc_root = guess_rulecards_root()
        if not rc_root:
            raise RuntimeError(
                "JSONL도 없고 RuleCards 폴더도 못 찾았습니다.\n"
                "D:\\SajuOS_Data\\3_SajuOS_RuleCards_JSON 경로를 확인해주세요."
            )
        print(f"⚠️ JSONL 미발견 → RuleCards 폴더에서 생성합니다: {rc_root}")
        total = build_jsonl_from_rulecards(rc_root, DEFAULT_JSONL_OUT)
        print(f"✅ JSONL 생성 완료: {DEFAULT_JSONL_OUT} (cards={total})")
        jsonl = DEFAULT_JSONL_OUT

    # 3) SQLite 적재
    con = connect(SQLITE_DB)
    create_tables(con)

    print("🚀 JSONL → SQLite 적재 시작")
    load_jsonl_to_sqlite(con, jsonl)

    fts_ok = try_create_fts(con)
    if fts_ok:
        print("✅ FTS5 생성 성공 → 전문검색 활성화")
        upsert_fts(con)
        con.commit()
    else:
        print("⚠️ FTS5 미지원 환경 → LIKE 검색으로 폴백")

    stats(con)

    # 샘플 출력
    print("\n🔎 샘플: YEAR_2026 토픽 Top-K 15")
    sample = pick_by_product(con, "YEAR_2026", k=15)
    for i, rc in enumerate(sample[:5], 1):
        print(f"{i}. {rc['id']} | {rc['topic']} | P{rc['priority']} | tags={rc['tags'][:4]}")

    print("\n🔎 샘플: '재물' 키워드 검색 Top-K 10")
    hits = search_fts(con, "재물 OR 현금 OR 돈", k=10, topics=["WEALTH", "GENERAL", "STRUCTURE"])
    for i, rc in enumerate(hits[:5], 1):
        print(f"{i}. {rc['id']} | {rc['topic']} | P{rc['priority']}")

    con.close()
    print("\n🎉 완료! DB:", SQLITE_DB)

if __name__ == "__main__":
    main()
