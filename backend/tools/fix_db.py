import sqlite3

db_path = r"D:\SajuOS_Data\sajuos_master.db"

def fix_database():
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 추가할 컬럼들 리스트
        new_columns = [
            ("trigger", "TEXT"),
            ("mechanism", "TEXT"),
            ("interpretation", "TEXT"),
            ("action", "TEXT"),
            ("cautions", "TEXT"),
            ("tags", "TEXT")
        ]
        
        for col_name, col_type in new_columns:
            try:
                # 컬럼 추가 시도
                cursor.execute(f"ALTER TABLE rule_cards ADD COLUMN {col_name} {col_type}")
                print(f"✅ 컬럼 추가 완료: {col_name}")
            except sqlite3.OperationalError:
                # 이미 컬럼이 존재하는 경우 에러가 나므로 무시
                print(f"ℹ️ 이미 존재함: {col_name}")
        
        conn.commit()
        conn.close()
        print("\n🚀 DB 구조 수정이 모두 완료되었습니다!")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    fix_database()