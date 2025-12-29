import sqlite3
import json

def quota_selector(features, tags, k=25, db_path="sajuos_master.db"):
    """태그 기반 정밀 RuleCard 셀렉터"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 태그 매칭 쿼리 (80% 우선순위)
    tag_conditions = " OR ".join([f"tags LIKE '%{t}%'" for t in tags])
    
    query = f"""
    SELECT id, topic, priority, mechanism, interpretation, action, tags
    FROM rule_cards 
    WHERE ({tag_conditions})
       OR topic IN ('TIMING', 'RELATION', 'ELEMENTS', 'STRUCTURE')
    ORDER BY 
        CASE WHEN ({tag_conditions}) THEN 1 ELSE 2 END,  -- 태그 완전 일치 우선
        priority DESC,
        LENGTH(tags) ASC  -- 태그 많은 카드 우선
    LIMIT {k}
    """
    
    cursor.execute(query)
    cards = []
    for row in cursor.fetchall():
        cards.append({
            "id": row[0], "topic": row[1], "priority": row[2],
            "mechanism": row[3], "interpretation": row[4],
            "action": row[5], "tags": json.loads(row[6] or "[]")
        })
    
    conn.close()
    return cards

# 테스트
if __name__ == "__main__":
    features = {"day_master": "무토", "elements": {"화":5}}
    tags = ["무토", "병오", "화강", "2026"]
    
    matched = quota_selector(features, tags, k=10)
    print(f"✅ {len(matched)}개 카드 매칭 완료")
    for card in matched[:3]:
        print(f"  {card['id']} | {card['topic']} | {card['tags'][:3]}")
