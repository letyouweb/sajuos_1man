"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SQLite 저장 모듈
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
사주 계산 결과 및 매칭 결과를 SQLite에 저장
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class SajuOSDatabase:
    """사주 데이터베이스"""
    
    def __init__(self, db_path: str = "sajuos.db"):
        """
        Args:
            db_path: 데이터베이스 파일 경로
        """
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """데이터베이스 초기화"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 사주 계산 결과 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS saju_calculations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                birth_year INTEGER NOT NULL,
                birth_month INTEGER NOT NULL,
                birth_day INTEGER NOT NULL,
                birth_hour INTEGER,
                birth_minute INTEGER DEFAULT 0,
                
                -- 사주 8글자
                year_pillar TEXT NOT NULL,
                month_pillar TEXT NOT NULL,
                day_pillar TEXT NOT NULL,
                hour_pillar TEXT,
                
                -- 일간 정보
                day_master TEXT NOT NULL,
                day_master_element TEXT NOT NULL,
                day_master_yin_yang TEXT NOT NULL,
                
                -- 파생 특징 (JSON)
                features_json TEXT NOT NULL,
                
                -- 타임스탬프
                created_at TEXT NOT NULL,
                
                -- 인덱스용
                UNIQUE(birth_year, birth_month, birth_day, birth_hour)
            )
        """)
        
        # 룰카드 매칭 결과 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rulecard_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                calculation_id INTEGER NOT NULL,
                
                -- 매칭 메타데이터
                target_year INTEGER NOT NULL,
                total_sections INTEGER NOT NULL,
                total_matched_cards INTEGER NOT NULL,
                
                -- 섹션별 결과 (JSON)
                sections_json TEXT NOT NULL,
                
                -- Raw JSON (전체 결과)
                raw_json TEXT NOT NULL,
                
                -- 타임스탬프
                created_at TEXT NOT NULL,
                
                FOREIGN KEY (calculation_id) REFERENCES saju_calculations(id)
            )
        """)
        
        conn.commit()
        conn.close()
        
        logger.info(f"[Database] 초기화 완료: {self.db_path}")
    
    def save_calculation(
        self,
        birth_year: int,
        birth_month: int,
        birth_day: int,
        birth_hour: Optional[int],
        pillars: Dict[str, Any],
        features: Dict[str, Any]
    ) -> int:
        """
        사주 계산 결과 저장
        
        Returns:
            calculation_id
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO saju_calculations (
                    birth_year, birth_month, birth_day, birth_hour, birth_minute,
                    year_pillar, month_pillar, day_pillar, hour_pillar,
                    day_master, day_master_element, day_master_yin_yang,
                    features_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                birth_year,
                birth_month,
                birth_day,
                birth_hour,
                0,  # birth_minute
                pillars["year"]["ganji"],
                pillars["month"]["ganji"],
                pillars["day"]["ganji"],
                pillars["hour"]["ganji"] if pillars["hour"] else None,
                features["day_master"],
                features["day_master_element"],
                features["day_master_yin_yang"],
                json.dumps(features, ensure_ascii=False),
                datetime.now().isoformat()
            ))
            
            calculation_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"[Database] 계산 결과 저장 완료: ID={calculation_id}")
            
            return calculation_id
        
        except sqlite3.IntegrityError:
            # 이미 존재하는 경우 기존 ID 반환
            cursor.execute("""
                SELECT id FROM saju_calculations
                WHERE birth_year=? AND birth_month=? AND birth_day=? AND birth_hour=?
            """, (birth_year, birth_month, birth_day, birth_hour))
            
            row = cursor.fetchone()
            calculation_id = row[0] if row else None
            
            logger.info(f"[Database] 이미 존재하는 계산: ID={calculation_id}")
            
            return calculation_id
        
        finally:
            conn.close()
    
    def save_matches(
        self,
        calculation_id: int,
        target_year: int,
        matches: Dict[str, Any],
        raw_json: Dict[str, Any]
    ) -> int:
        """
        룰카드 매칭 결과 저장
        
        Returns:
            match_id
        """
        from dataclasses import asdict
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        total_sections = len(matches)
        
        # SectionMatch 객체를 딕셔너리로 변환
        first_value = list(matches.values())[0] if matches else None
        if first_value and hasattr(first_value, 'cards'):
            # SectionMatch 객체인 경우
            total_cards = sum(len(m.cards) for m in matches.values())
            sections_dict = {k: asdict(v) for k, v in matches.items()}
        else:
            # 이미 딕셔너리인 경우
            total_cards = sum(len(m["cards"]) for m in matches.values())
            sections_dict = matches
        
        cursor.execute("""
            INSERT INTO rulecard_matches (
                calculation_id, target_year,
                total_sections, total_matched_cards,
                sections_json, raw_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            calculation_id,
            target_year,
            total_sections,
            total_cards,
            json.dumps(sections_dict, ensure_ascii=False),
            json.dumps(raw_json, ensure_ascii=False),
            datetime.now().isoformat()
        ))
        
        match_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"[Database] 매칭 결과 저장 완료: ID={match_id}, 섹션={total_sections}, 카드={total_cards}")
        
        return match_id
    
    def get_calculation(self, calculation_id: int) -> Optional[Dict[str, Any]]:
        """계산 결과 조회"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM saju_calculations WHERE id=?
        """, (calculation_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            "id": row[0],
            "birth_year": row[1],
            "birth_month": row[2],
            "birth_day": row[3],
            "birth_hour": row[4],
            "birth_minute": row[5],
            "year_pillar": row[6],
            "month_pillar": row[7],
            "day_pillar": row[8],
            "hour_pillar": row[9],
            "day_master": row[10],
            "day_master_element": row[11],
            "day_master_yin_yang": row[12],
            "features_json": json.loads(row[13]),
            "created_at": row[14],
        }
    
    def get_matches(self, match_id: int) -> Optional[Dict[str, Any]]:
        """매칭 결과 조회"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM rulecard_matches WHERE id=?
        """, (match_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            "id": row[0],
            "calculation_id": row[1],
            "target_year": row[2],
            "total_sections": row[3],
            "total_matched_cards": row[4],
            "sections_json": json.loads(row[5]),
            "raw_json": json.loads(row[6]),
            "created_at": row[7],
        }


# 싱글톤 인스턴스
def get_database(db_path: str = "sajuos.db") -> SajuOSDatabase:
    """데이터베이스 인스턴스 가져오기"""
    return SajuOSDatabase(db_path)
