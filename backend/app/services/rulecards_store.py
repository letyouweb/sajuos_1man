from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
import json, os, math, logging, sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class RuleCard:
    """
    RuleCard 데이터클래스
    - content dict 기반 접근을 위한 property 포함
    """
    id: str
    topic: str
    tags: List[str]
    priority: float = 0.0
    trigger: Optional[str] = None
    mechanism: Optional[str] = None
    interpretation: Optional[str] = None
    action: Optional[str] = None
    cautions: Optional[List[str]] = None
    content: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    # property로 content dict 접근 지원 (getattr 대응)
    @property
    def content_mechanism(self) -> str:
        return self.mechanism or (self.content or {}).get("mechanism", "") or ""

    @property
    def content_interpretation(self) -> str:
        return self.interpretation or (self.content or {}).get("interpretation", "") or ""

    @property
    def content_action(self) -> str:
        return self.action or (self.content or {}).get("action", "") or ""

    @property
    def content_cautions(self) -> List[str]:
        if self.cautions:
            return self.cautions if isinstance(self.cautions, list) else [self.cautions]
        v = (self.content or {}).get("cautions", [])
        return v if isinstance(v, list) else ([v] if v else [])

    @property
    def subtopic(self) -> str:
        return (self.meta or {}).get("subtopic", "") or ""


TAG_NORMALIZE = {
    "정제": "정재", "편제": "편재", "겁제": "겁재",
    "식신생제": "식신생재", "상관생제": "상관생재", "식상생제": "식상생재",
    "간목": "인목", "신지금": "신금",
}


def canon_tag(t: str) -> str:
    s = " ".join(str(t).strip().split())
    return TAG_NORMALIZE.get(s, s)


def explode_tag_tokens(t: str) -> List[str]:
    c = canon_tag(t)
    parts = [canon_tag(p) for p in c.split(" ") if len(p) >= 2]
    out, seen = [], set()
    for x in [c] + parts:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def safe_priority(p) -> float:
    try:
        v = float(p)
    except Exception:
        return 0.0
    return min(v, 10.0) if v <= 10 else min(v, 100.0) / 10.0


class RuleCardStore:
    """JSONL/SQLite 룰카드 로드 + 토픽 인덱스 + IDF"""

    def __init__(self, path: str = None, cards: List[RuleCard] = None):
        self.path = path
        self.cards: List[RuleCard] = cards or []
        self.by_topic: Dict[str, List[RuleCard]] = {}
        self.idf: Dict[str, float] = {}
        self.source: str = "unknown"
        
        if cards:
            self.by_topic = self._build_topic_index(cards)
            self.idf = self._build_idf(cards)

    @classmethod
    def load_from_sqlite_master(cls, db_path: str) -> "RuleCardStore":
        """sajuos_master.db에서 룰카드 로드"""
        p = Path(db_path)
        if not p.exists():
            raise FileNotFoundError(f"master db not found: {db_path}")

        conn = sqlite3.connect(str(p))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT id, topic, priority, trigger_json, tags_json, 
                   interpretation, mechanism, action, cautions_json
            FROM rule_cards
        """).fetchall()
        conn.close()

        cards = []
        for r in rows:
            # trigger_json 파싱
            trigger_obj = {}
            trigger_list = []
            try:
                trigger_obj = json.loads(r["trigger_json"] or "{}")
                if isinstance(trigger_obj, dict):
                    kw = trigger_obj.get("keywords", [])
                    if isinstance(kw, list):
                        trigger_list = [str(x).strip() for x in kw if str(x).strip()]
            except:
                pass

            # tags_json 파싱
            tags = []
            try:
                tags = json.loads(r["tags_json"] or "[]")
                if not isinstance(tags, list):
                    tags = []
            except:
                tags = []

            # tags 비어있으면 keywords로 채움
            if not tags and trigger_list:
                tags = trigger_list[:]
            if not tags:
                tags = [r["topic"] or "GENERAL"]

            # cautions_json 파싱
            cautions = []
            try:
                cautions = json.loads(r["cautions_json"] or "[]")
                if not isinstance(cautions, list):
                    cautions = [cautions] if cautions else []
            except:
                cautions = []

            # content dict 구성
            content = {
                "interpretation": r["interpretation"] or "",
                "mechanism": r["mechanism"] or "",
                "action": r["action"] or "",
                "cautions": cautions,
            }

            cards.append(RuleCard(
                id=r["id"],
                topic=r["topic"] or "GENERAL",
                priority=safe_priority(r["priority"]),
                trigger=json.dumps(trigger_obj) if trigger_obj else None,
                tags=[canon_tag(x) for x in tags if x],
                mechanism=r["mechanism"] or "",
                interpretation=r["interpretation"] or "",
                action=r["action"] or "",
                cautions=cautions,
                content=content,
                meta={"trigger": trigger_obj},
            ))

        store = cls(path=db_path, cards=cards)
        store.source = "master_db"
        logger.info(f"[RuleCardStore] ✅ master_db 로드: {len(cards)}장")
        print(f"✅ RuleCards loaded from master db: {len(cards)}")
        return store

    def load(self) -> None:
        """JSONL에서 룰카드 로드"""
        p = self.path
        if not os.path.exists(p):
            raise FileNotFoundError(f"Rulecards JSONL not found: {p}")

        cards: List[RuleCard] = []
        skipped = 0

        with open(p, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    skipped += 1
                    continue

                if not obj.get("id") or not obj.get("topic"):
                    skipped += 1
                    continue

                tags = obj.get("tags", [])
                if not tags:
                    trigger = obj.get("trigger")
                    if trigger:
                        if isinstance(trigger, list):
                            tags = [str(t) for t in trigger if t]
                        elif isinstance(trigger, str):
                            try:
                                parsed = json.loads(trigger)
                                if isinstance(parsed, list):
                                    tags = [str(t) for t in parsed if t]
                                elif isinstance(parsed, dict):
                                    for v in parsed.values():
                                        if isinstance(v, list):
                                            tags.extend([str(t) for t in v if t])
                            except:
                                tags = [trigger]
                if not tags:
                    tags = [obj.get("topic")]

                cautions = obj.get("cautions", [])
                if not isinstance(cautions, list):
                    cautions = [cautions] if cautions else []

                content = {
                    "interpretation": obj.get("interpretation", ""),
                    "mechanism": obj.get("mechanism", ""),
                    "action": obj.get("action", ""),
                    "cautions": cautions,
                }

                cards.append(RuleCard(
                    id=obj["id"],
                    topic=obj["topic"],
                    tags=[canon_tag(x) for x in tags],
                    priority=safe_priority(obj.get("priority", 0)),
                    trigger=obj.get("trigger"),
                    mechanism=obj.get("mechanism"),
                    interpretation=obj.get("interpretation"),
                    action=obj.get("action"),
                    cautions=cautions,
                    content=content,
                    meta={},
                ))

        self.cards = cards
        self.by_topic = self._build_topic_index(cards)
        self.idf = self._build_idf(cards)
        self.source = "jsonl"
        logger.info(f"[RuleCardStore] ✅ JSONL 로드: {len(cards)}장 (스킵: {skipped})")
        print(f"✅ RuleCards loaded from jsonl: {len(cards)}")

    def _build_topic_index(self, cards: List[RuleCard]) -> Dict[str, List[RuleCard]]:
        m: Dict[str, List[RuleCard]] = {}
        for c in cards:
            m.setdefault(c.topic, []).append(c)
        for k in list(m.keys()):
            m[k].sort(key=lambda x: x.priority, reverse=True)
        return m

    def _build_idf(self, cards: List[RuleCard]) -> Dict[str, float]:
        df: Dict[str, int] = {}
        N = len(cards)
        for c in cards:
            token_set: Set[str] = set()
            for t in c.tags:
                for x in explode_tag_tokens(t):
                    token_set.add(x)
            for t in token_set:
                df[t] = df.get(t, 0) + 1

        idf: Dict[str, float] = {}
        for t, d in df.items():
            idf[t] = math.log((N + 1) / (d + 1)) + 1.0
        return idf
