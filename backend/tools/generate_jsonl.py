import os
import json
import re
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ===== 설정 =====
INPUT_DIR = r"D:\SajuOS_Data\3_SajuOS_RuleCards_JSON"
OUTPUT_FILE = r"D:\SajuOS_Data\sajuos_master_db.jsonl"
REPORT_FILE = r"D:\SajuOS_Data\sajuos_master_db_report.json"

# [비식별/비인용] 제거 규칙 (필요하면 더 추가)
CITE_PATTERN = re.compile(r"\[cite:\s*.*?\]", re.IGNORECASE)
NAME_BLOCKLIST = ["정동찬"]  # 혹시 남아있으면 제거

def scrub_text(s: Any) -> str:
    if s is None:
        return ""
    s = str(s)
    s = CITE_PATTERN.sub("", s)
    for name in NAME_BLOCKLIST:
        s = s.replace(name, "")
    # 불필요한 공백 정리
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s

def stable_id(card: Dict[str, Any]) -> str:
    # id가 없거나 비정상일 때 생성 (내용 기반 해시)
    payload = {
        "topic": card.get("topic", ""),
        "trigger": card.get("trigger", {}),
        "mechanism": scrub_text(card.get("mechanism", "")),
        "interpretation": scrub_text(card.get("interpretation", "")),
        "action": scrub_text(card.get("action", "")),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    h = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"RC-{h}"

def normalize_card(card: Dict[str, Any], source_file: str, source_path: str, source_title: str) -> Dict[str, Any]:
    # 필수 스키마 강제
    norm: Dict[str, Any] = {}
    norm["id"] = str(card.get("id") or "").strip() or stable_id(card)

    norm["topic"] = str(card.get("topic") or "GENERAL").strip() or "GENERAL"

    try:
        norm["priority"] = int(card.get("priority", 5))
    except:
        norm["priority"] = 5

    trigger = card.get("trigger", {})
    if isinstance(trigger, str):
        # trigger가 문자열로 들어온 케이스 방어
        try:
            trigger = json.loads(trigger)
        except:
            trigger = {"raw": trigger}
    if not isinstance(trigger, dict):
        trigger = {"raw": trigger}
    norm["trigger"] = trigger

    # 본문 텍스트(비인용/비식별 스크럽 포함)
    norm["mechanism"] = scrub_text(card.get("mechanism", ""))
    norm["interpretation"] = scrub_text(card.get("interpretation", ""))
    norm["action"] = scrub_text(card.get("action", ""))

    # 부가 필드
    tags = card.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in re.split(r"[,\s]+", tags) if t.strip()]
    if not isinstance(tags, list):
        tags = []
    norm["tags"] = tags

    cautions = card.get("cautions", [])
    if isinstance(cautions, str):
        cautions = [c.strip() for c in cautions.split("\n") if c.strip()]
    if not isinstance(cautions, list):
        cautions = []
    norm["cautions"] = [scrub_text(x) for x in cautions if scrub_text(x)]

    norm["source_file"] = source_file
    norm["source_path"] = source_path
    norm["source_title"] = source_title

    return norm

def iter_rulecards(data: Any) -> List[Dict[str, Any]]:
    # 파일 구조가 {rulecards:[...]} 또는 그냥 [...] 인 케이스 대응
    if isinstance(data, dict) and isinstance(data.get("rulecards"), list):
        return data["rulecards"]
    if isinstance(data, list):
        return data
    return []

def build_master_db():
    seen_ids = set()
    total_files = 0
    total_cards = 0
    written = 0
    skipped_dup = 0
    skipped_bad = 0

    topic_count = {}
    priority_count = {}

    out_path = Path(OUTPUT_FILE)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        for p in sorted(Path(INPUT_DIR).rglob("*.json")):
            total_files += 1
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                skipped_bad += 1
                continue

            source_title = ""
            if isinstance(data, dict):
                source_title = str(data.get("title") or data.get("name") or "").strip()
            if not source_title:
                source_title = p.stem

            cards = iter_rulecards(data)
            total_cards += len(cards)

            for card in cards:
                if not isinstance(card, dict):
                    skipped_bad += 1
                    continue

                norm = normalize_card(
                    card=card,
                    source_file=p.name,
                    source_path=str(p),
                    source_title=source_title
                )

                rid = norm["id"]
                if rid in seen_ids:
                    skipped_dup += 1
                    continue
                seen_ids.add(rid)

                out.write(json.dumps(norm, ensure_ascii=False) + "\n")
                written += 1

                t = norm["topic"]
                topic_count[t] = topic_count.get(t, 0) + 1
                pr = str(norm["priority"])
                priority_count[pr] = priority_count.get(pr, 0) + 1

    report = {
        "input_dir": INPUT_DIR,
        "output_file": OUTPUT_FILE,
        "total_files": total_files,
        "total_cards_found": total_cards,
        "written_records": written,
        "skipped_dup": skipped_dup,
        "skipped_bad": skipped_bad,
        "topic_count": dict(sorted(topic_count.items(), key=lambda x: -x[1])),
        "priority_count": dict(sorted(priority_count.items(), key=lambda x: int(x[0]))),
    }

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("🎉 통합 완료!")
    print(f"- 파일: {total_files}개")
    print(f"- 카드 발견: {total_cards}개")
    print(f"- 기록됨: {written}개")
    print(f"- 중복 스킵: {skipped_dup}개 / 파손 스킵: {skipped_bad}개")
    print(f"- JSONL: {OUTPUT_FILE}")
    print(f"- 리포트: {REPORT_FILE}")

if __name__ == "__main__":
    build_master_db()
