import sqlite3

conn = sqlite3.connect('saju_rules.db')
cur = conn.cursor()

# 최소한의 rule_cards 테이블 생성
cur.execute("""
CREATE TABLE IF NOT EXISTS rule_cards (
    id TEXT PRIMARY KEY,
    topic TEXT,
    priority INTEGER,
    trigger TEXT,
    mechanism TEXT,
    interpretation TEXT,
    action TEXT
)
""")

# 샘플 데이터 하나 삽입 (테스트용)
cur.execute("""
INSERT OR REPLACE INTO rule_cards (id, topic, priority, trigger, interpretation)
VALUES ('RC-TEST-01', 'TIMING', 5, '{"day_master":"무"}', '테스트용 해석입니다.')
""")

conn.commit()
conn.close()
print("✅ saju_rules.db에 rule_cards 테이블을 생성했습니다.")