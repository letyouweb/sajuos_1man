# build_saju_db.py
import sqlite3
import json

def build_db():
    conn = sqlite3.connect('saju_rules.db')
    cur = conn.cursor()

    # 1. rule_cards 테이블 생성
    cur.execute("""
    CREATE TABLE IF NOT EXISTS rule_cards (
        id TEXT PRIMARY KEY,
        topic TEXT,
        priority INTEGER,
        trigger TEXT,
        mechanism TEXT,
        interpretation TEXT,
        action TEXT,
        tags TEXT,
        cautions TEXT
    )
    """)

    # 2. 테스트용 샘플 데이터 (2026년 병오년 관련 샘플)
    sample_rules = [
        (
            "RC-2026-001", 
            "TIMING", 
            10, 
            json.dumps({"target_year_ganji": "병오"}), 
            "병화의 확산력과 오화의 추진력이 결합되는 시기", 
            "2026년은 그동안 준비한 일이 세상에 강력하게 드러나는 해입니다.", 
            "새로운 프로젝트 런칭, 대외 활동 강화",
            json.dumps(["2026", "병오", "확산"]),
            json.dumps(["성급한 결정 주의"])
        ),
        (
            "RC-GEN-002", 
            "RELATION", 
            8, 
            json.dumps({"day_master": "무"}), 
            "무토 일간과 병화의 상생", 
            "무토 일간에게 병화는 든든한 지원군과 같습니다. 주변의 도움을 받기 좋은 시기입니다.", 
            "귀인과의 만남 추진, 협력 관계 구축",
            json.dumps(["무토", "편인", "도움"]),
            json.dumps(["의존성 심화 경계"])
        )
    ]

    cur.executemany("""
    INSERT OR REPLACE INTO rule_cards 
    (id, topic, priority, trigger, mechanism, interpretation, action, tags, cautions) 
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_rules)

    conn.commit()
    conn.close()
    print("✅ saju_rules.db 구축 완료! (rule_cards 테이블 생성 및 샘플 데이터 삽입)")

if __name__ == "__main__":
    build_db()