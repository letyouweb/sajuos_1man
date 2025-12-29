# search_sqlite.py
import argparse, sqlite3, json

def detect_fts_table(conn: sqlite3.Connection):
    # 흔한 이름 후보들. 너 build 스크립트랑 다를 수 있어서 자동탐색.
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    # FTS5는 보통 CREATE VIRTUAL TABLE ... USING fts5 로 생성됨
    fts_tables = []
    for t in tables:
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (t,))
        sql = cur.fetchone()
        if sql and sql[0] and "fts5" in sql[0].lower():
            fts_tables.append(t)
    return fts_tables

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="SQLite DB path (ex: D:\\SajuOS_Data\\sajuos_master.db)")
    ap.add_argument("--q", required=True, help="FTS query (ex: 재물, 현금흐름, 병오, 조후)")
    ap.add_argument("--k", type=int, default=10)
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    fts_tables = detect_fts_table(conn)
    if not fts_tables:
        raise RuntimeError("FTS5 테이블을 못 찾았어. build_sajuos_sqlite.py에서 만든 FTS 테이블 이름을 확인해줘.")

    # 가장 첫 FTS 테이블 사용
    fts = fts_tables[0]
    cur = conn.cursor()

    # FTS 테이블 컬럼 확인
    cur.execute(f"PRAGMA table_info({fts})")
    cols = [r[1] for r in cur.fetchall()]
    # 보통 id/topic/priority가 같이 있거나, content만 있을 수도 있음
    select_cols = cols[:]
    if len(select_cols) == 0:
        raise RuntimeError("FTS 테이블 컬럼을 못 읽었어.")

    # rank/score가 없다면 bm25 사용
    try:
        sql = f"""
        SELECT {", ".join(select_cols)}, bm25({fts}) as score
        FROM {fts}
        WHERE {fts} MATCH ?
        ORDER BY score
        LIMIT ?
        """
        rows = cur.execute(sql, (args.q, args.k)).fetchall()
    except sqlite3.OperationalError:
        # bm25 미지원이면 그냥 LIMIT
        sql = f"""
        SELECT {", ".join(select_cols)}
        FROM {fts}
        WHERE {fts} MATCH ?
        LIMIT ?
        """
        rows = cur.execute(sql, (args.q, args.k)).fetchall()

    print(f"FTS table: {fts}")
    print(f"Query: {args.q}\n")
    for i, r in enumerate(rows, 1):
        d = dict(r)
        # 너무 길면 축약
        for key in list(d.keys()):
            if isinstance(d[key], str) and len(d[key]) > 200:
                d[key] = d[key][:200] + "…"
        print(f"{i}. {json.dumps(d, ensure_ascii=False)}")

if __name__ == "__main__":
    main()
