# generate_2026_report_v0_2_1.py
import os, json, argparse, sqlite3, math, time
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional

from openai import OpenAI

# =========================
# CONFIG
# =========================
DEFAULT_DB = r"D:\SajuOS_Data\sajuos_master.db"
STRICT_DAY_MASTER = True           # ✅ 일간 엄수
MIN_MATCH_SCORE = 1.0              # ✅ 이 점수 미만은 버림(필요시 0.5로 낮춰도 됨)
DROP_UNGROUNDED = True             # ✅ trigger/tags 둘다 없고 근거도 약한 카드 컷
K_PER_SECTION = 6                  # 섹션별로 뽑을 카드 수(전체 5섹션이면 총 30 전후)
MAX_RULECARDS_IN_PROMPT = 30       # LLM에 주입할 최대 카드 수

# =========================
# PROMPT (v0.2 Defensive)
# =========================
SYSTEM_PROMPT = """
# Role: SajuOS (Modern Saju Analysis Engine)
당신은 'SajuOS'라는 명리 데이터 분석 엔진이다.
목표: 제공된 RuleCard(JSON)의 논리만 사용하여, 사용자에게 현대적/실전형 2026년 운세 리포트를 생성한다.

# 절대 금지 (비인용/비식별)
- 원문 강의/전사 문장을 그대로 복사하거나 인용하지 마라. 반드시 재서술하라.
- "강의/수업/선생님/학자/누가 말했다" 같은 출처 암시는 절대 금지.
- 특정 인물 말투(구어체 강의톤) 금지.

# 비식별화 + 범주화(Defensive Abstraction)
- 육친을 단정하지 말고, 관계를 범주화해라.
  * 모친/부친 -> 윗사람/보호자/심리적 지지 기반
  * 자식 -> 내가 돌봐야 할 대상/결과물/하향 소통 채널
  * 상사 -> 권위자/시스템 통제권자
- 단정 대신 조건부/확률적 표현을 써라:
  "~일 가능성이 높음", "~한 경향", "만약 ~라면 ~가 유리"

# 구조 고정 (YEAR_2026 전용)
반드시 아래 5섹션을 포함한 JSON만 출력:
1_overview, 2_mechanics, 3_economic_flow, 4_interaction, 5_roadmap

# XAI(설명가능)
- 각 섹션에 사용한 근거 RuleCard id들을 ref_ids 배열로 포함한다.
- 화면 노출 여부는 상관없다. JSON에는 반드시 남겨라.

# 문체
- 정중하고 신뢰감 있는 전문가 톤.
- 예언이 아니라 '전략/경우의 수/행동 가이드' 중심.
""".strip()

# =========================
# Helpers
# =========================
def jload(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def jdump(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def safe_json(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return v
    if isinstance(v, str):
        v = v.strip()
        if not v:
            return None
        try:
            return json.loads(v)
        except Exception:
            return None
    return None

def setify(x: Any) -> set:
    if x is None:
        return set()
    if isinstance(x, list):
        return set([str(i).strip() for i in x if str(i).strip()])
    if isinstance(x, str):
        # "a, b, c" 형태도 방어
        parts = [p.strip() for p in x.replace("\n", ",").split(",")]
        return set([p for p in parts if p])
    return set([str(x)])

def clamp(n: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, n))

def compute_balance_score(elements: Dict[str, int]) -> int:
    """
    아주 단순하지만 '그럴듯한' 점수:
    - 오행 편중이 심할수록 감점
    - 2026(병오) = 화 강함 → 사용자 화가 이미 높으면 추가 감점
    """
    # keys: wood/fire/earth/metal/water 혹은 목화토금수 형태 섞일 수 있으니 보정
    def get(k1, k2):
        return int(elements.get(k1, elements.get(k2, 0)) or 0)

    wood  = get("wood", "목")
    fire  = get("fire", "화")
    earth = get("earth", "토")
    metal = get("metal", "금")
    water = get("water", "수")

    vals = [wood, fire, earth, metal, water]
    total = sum(vals) if sum(vals) > 0 else 1
    mean = total / 5.0
    var = sum((v - mean) ** 2 for v in vals) / 5.0
    std = math.sqrt(var)

    # 기본 85에서 편중 감점
    score = 85 - std * 10  # std 2면 -20 정도
    # 2026 화 강함 보정
    if fire >= 4:
        score -= 8
    elif fire <= 1:
        score += 4

    return int(clamp(score, 45, 95))

def trigger_hard_match(trigger: Optional[Dict[str, Any]], features: Dict[str, Any]) -> Tuple[bool, float]:
    """
    trigger에 명시된 '딱 떨어지는 조건'이 있으면 반드시 일치해야 함.
    일치하면 가산점 반환.
    """
    if not trigger:
        return True, 0.0

    score = 0.0

    user_day_master = features.get("day_master")
    user_pillars = features.get("pillars", {}) or {}
    user_day_pillar = user_pillars.get("day") or features.get("day_pillar")
    user_month_pillar = user_pillars.get("month") or features.get("month_pillar")
    user_month_branch = features.get("month_branch")

    # day_master
    if "day_master" in trigger and trigger["day_master"]:
        if str(trigger["day_master"]).strip() != str(user_day_master).strip():
            return False, -999.0
        score += 5.0

    # day_pillar
    if "day_pillar" in trigger and trigger["day_pillar"]:
        if str(trigger["day_pillar"]).strip() != str(user_day_pillar).strip():
            return False, -999.0
        score += 4.0

    # month_pillar
    if "month_pillar" in trigger and trigger["month_pillar"]:
        if str(trigger["month_pillar"]).strip() != str(user_month_pillar).strip():
            return False, -999.0
        score += 3.0

    # month_branch
    if "month_branch" in trigger and trigger["month_branch"]:
        if str(trigger["month_branch"]).strip() != str(user_month_branch).strip():
            return False, -999.0
        score += 2.0

    return True, score

def is_ungrounded(card: Dict[str, Any]) -> bool:
    trig = card.get("trigger")
    tags = card.get("tags")
    mech = (card.get("mechanism") or "").strip()
    interp = (card.get("interpretation") or "").strip()
    # trigger/tags 둘 다 없고, 본문도 짧으면 근거 부족으로 간주
    if (not trig) and (not tags) and (len(mech) < 20) and (len(interp) < 20):
        return True
    return False

def score_card(card: Dict[str, Any], features: Dict[str, Any], user_tags: set) -> float:
    trig = card.get("trigger") or {}
    tags = setify(card.get("tags"))

    ok, trig_score = trigger_hard_match(trig, features)
    if not ok:
        return -999.0

    tag_hits = len(tags & user_tags)
    priority = float(card.get("priority", 5) or 5)

    # ✅ tags/trigger 매칭이 없는 카드는 점수 낮게
    base = (priority * 0.03) + (tag_hits * 1.0) + (trig_score * 1.2)

    # 근거 부족 카드 패널티
    if DROP_UNGROUNDED and is_ungrounded(card):
        base -= 2.5

    return base

def fetch_candidates(conn: sqlite3.Connection, topics: List[str]) -> List[Dict[str, Any]]:
    q = f"""
    SELECT id, topic, priority, trigger, mechanism, interpretation, action, cautions, tags, source_file
    FROM rule_cards
    WHERE topic IN ({",".join(["?"] * len(topics))})
    """
    cur = conn.cursor()
    cur.execute(q, topics)
    rows = cur.fetchall()

    out = []
    for (id_, topic, priority, trigger, mechanism, interpretation, action, cautions, tags, source_file) in rows:
        card = {
            "id": id_,
            "topic": topic,
            "priority": int(priority or 5),
            "trigger": safe_json(trigger),
            "mechanism": mechanism,
            "interpretation": interpretation,
            "action": action,
            "cautions": safe_json(cautions) or [],
            "tags": safe_json(tags) or [],
            "source_file": source_file,
        }
        out.append(card)
    return out

def pick_topk(cards: List[Dict[str, Any]], features: Dict[str, Any], user_tags: set, k: int) -> List[Dict[str, Any]]:
    scored = []
    for c in cards:
        # ✅ trigger/tags 둘 다 없고 내용도 빈약한 건 컷
        if DROP_UNGROUNDED and is_ungrounded(c):
            continue

        s = score_card(c, features, user_tags)
        if s >= MIN_MATCH_SCORE:
            scored.append((s, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    picked = [c for _, c in scored[:k]]

    # 만약 너무 적게 뽑혔으면(과도 필터링) 완화: MIN_MATCH_SCORE 기준을 잠깐 내리고 채움
    if len(picked) < max(2, k // 2):
        relaxed = []
        for c in cards:
            s = score_card(c, features, user_tags)
            if s > 0:
                relaxed.append((s, c))
        relaxed.sort(key=lambda x: x[0], reverse=True)
        picked = [c for _, c in relaxed[:k]]

    return picked

def build_pack(conn: sqlite3.Connection, features: Dict[str, Any]) -> Dict[str, Any]:
    # user_tags는 features.tags + 요소/십성 같은 키워드를 합쳐서 확장 가능
    user_tags = setify(features.get("tags"))

    # 일간을 tags에 박아주면 태그 매칭이 훨씬 안정됨
    if features.get("day_master"):
        user_tags.add(str(features["day_master"]))

    # 오행 많은 것(상위 2개)을 태그로 추가(간단 강화)
    elements = features.get("elements", {}) or {}
    if isinstance(elements, dict) and elements:
        sorted_e = sorted(elements.items(), key=lambda x: int(x[1] or 0), reverse=True)
        for k, v in sorted_e[:2]:
            if int(v or 0) >= 3:
                user_tags.add(str(k))

    sections = {
        "mechanics": ["TIMING", "STRUCTURE", "ELEMENTS", "GENERAL"],
        "economic": ["WEALTH", "CAREER", "STRUCTURE", "TEN_GODS"],
        "interaction": ["RELATION", "LOVE", "GENERAL"],
        "roadmap": ["TIMING", "GENERAL"],
    }

    packs = {}
    for key, topics in sections.items():
        candidates = fetch_candidates(conn, topics)
        topk = pick_topk(candidates, features, user_tags, K_PER_SECTION)
        packs[key] = {
            "topics": topics,
            "k": K_PER_SECTION,
            "selected_rulecards": topk,
        }

    # 전체 주입 카드 풀(중복 제거)
    all_cards = []
    seen = set()
    for key in packs:
        for c in packs[key]["selected_rulecards"]:
            if c["id"] not in seen:
                seen.add(c["id"])
                all_cards.append(c)

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "features": features,
        "user_tags": sorted(list(user_tags)),
        "rulepacks": packs,
        "selected_rulecards": all_cards[:MAX_RULECARDS_IN_PROMPT],
    }

def call_llm_json(client: OpenAI, model: str, system_prompt: str, user_prompt: str, retries: int = 3) -> Dict[str, Any]:
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=4096,
            )
            text = resp.choices[0].message.content.strip()
            return json.loads(text)
        except Exception as e:
            last_err = e
            time.sleep(1.5 * attempt)

    raise RuntimeError(f"LLM failed: {last_err}")

def fallback_report(pack: Dict[str, Any]) -> Dict[str, Any]:
    """
    LLM이 죽어도 파이프라인이 멈추지 않게,
    선택된 RuleCard를 기반으로 '기계식' 리포트 JSON 생성.
    """
    features = pack["features"]
    elements = features.get("elements", {}) or {}
    score = compute_balance_score(elements)

    def refs(key):
        return [c["id"] for c in pack["rulepacks"][key]["selected_rulecards"]]

    return {
        "product_id": "YEAR_2026_PREMIUM",
        "report_structure": {
            "1_overview": {
                "score": score,
                "headline": "2026년은 에너지가 빠르게 확산되는 해 — ‘과부하 관리’가 성패를 가릅니다.",
                "summary": "전체 흐름은 ‘확장/가속’ 쪽으로 기울어 있습니다. 다만 본인 오행 편중이 강하면 속도보다 안정 장치가 먼저입니다.",
                "ref_ids": refs("mechanics"),
            },
            "2_mechanics": [
                {
                    "logic": "선택된 규칙 기반 핵심 메커니즘",
                    "description": "룰카드 근거를 우선으로 조립했습니다(LLM 미사용 fallback).",
                    "ref_ids": refs("mechanics"),
                }
            ],
            "3_economic_flow": {
                "analysis": "재물/커리어는 ‘확장’보다 ‘구조화’에 유리합니다. 수익이 새는 구멍부터 막는 쪽이 ROI가 큽니다.",
                "action_items": ["고정비/변동비 분리", "현금흐름 점검", "핵심 스킬/포지션 명확화"],
                "ref_ids": refs("economic"),
            },
            "4_interaction": {
                "analysis": "관계는 단정 대신 ‘상호 기대치 조율’로 접근하는 게 안전합니다. 가까운 관계일수록 역할/경계 설정이 중요합니다.",
                "suggestion": "감정 소모를 줄이기 위해 ‘요구-합의-실행’ 순서로 대화하십시오.",
                "ref_ids": refs("interaction"),
            },
            "5_roadmap": {
                "best_months": [1, 2, 5],
                "caution_months": [11, 12],
                "monthly_advice": "상반기는 실행/확장, 하반기는 리스크/정리 중심으로 운영하십시오.",
                "ref_ids": refs("roadmap"),
            },
        },
        "meta": {
            "mode": "fallback_no_llm",
            "generated_at": datetime.utcnow().isoformat() + "Z",
        },
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--in", dest="in_path", required=True)
    ap.add_argument("--out", dest="out_path", required=True)
    ap.add_argument("--model", default="gpt-4o-mini")
    args = ap.parse_args()

    src = jload(args.in_path)

    # 입력 JSON에서 features 위치 방어 (케이스가 여러개일 수 있음)
    features = src.get("features") or src.get("pack", {}).get("features") or {}
    if not features:
        raise RuntimeError("입력 JSON에서 features를 찾지 못했습니다. (features 키가 필요)")

    # ✅ 일간 엄수: day_master 없으면 여기서부터 신뢰도 무너짐
    if STRICT_DAY_MASTER and not features.get("day_master"):
        raise RuntimeError("features.day_master가 없습니다. 일간(day_master)은 필수입니다.")

    conn = sqlite3.connect(args.db)
    pack = build_pack(conn, features)

    elements = features.get("elements", {}) or {}
    score = compute_balance_score(elements)

    # LLM 입력(룰카드 요약 주입)
    # - 원문 인용 금지라서, 카드 전체를 넣기보다 "핵심만" 전달
    cards_for_prompt = []
    for c in pack["selected_rulecards"]:
        cards_for_prompt.append({
            "id": c["id"],
            "topic": c["topic"],
            "priority": c["priority"],
            "trigger": c.get("trigger") or {},
            "mechanism": (c.get("mechanism") or "")[:800],
            "interpretation": (c.get("interpretation") or "")[:800],
            "action": (c.get("action") or "")[:600],
            "cautions": c.get("cautions") or [],
            "tags": c.get("tags") or [],
        })

    user_prompt = {
        "product_id": "YEAR_2026_PREMIUM",
        "fixed_year": 2026,
        "today": datetime.now().strftime("%Y-%m-%d"),
        "user_features": features,
        "balance_score_hint": score,
        "rulecards": cards_for_prompt
    }

    out = {
        "pack": pack,
        "report": None,
    }

    # LLM 호출 (쿼터/429 대비)
    try:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY 환경변수가 없습니다.")
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        report = call_llm_json(client, args.model, SYSTEM_PROMPT, json.dumps(user_prompt, ensure_ascii=False), retries=3)
        out["report"] = report
        out["report"]["_meta"] = {"generated_at": datetime.utcnow().isoformat() + "Z", "mode": "llm"}
    except Exception as e:
        out["report"] = fallback_report(pack)
        out["report"]["_meta_error"] = str(e)

    jdump(args.out_path, out)
    print(f"✅ 완료: {args.out_path}")

if __name__ == "__main__":
    main()
