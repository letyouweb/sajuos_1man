# match_rulecards_v0.py
import argparse, sqlite3, json, os
from typing import Any, Dict, List, Tuple
from datetime import datetime
from zoneinfo import ZoneInfo

GAN = list("갑을병정무기경신임계")
JI  = list("자축인묘진사오미신유술해")

GAN_ELEM = {
    "갑":"목","을":"목","병":"화","정":"화","무":"토","기":"토","경":"금","신":"금","임":"수","계":"수",
}
JI_ELEM = {
    "자":"수","축":"토","인":"목","묘":"목","진":"토","사":"화","오":"화","미":"토","신":"금","유":"금","술":"토","해":"수",
}

SEASON_BY_MONTH_BRANCH = {
    # 월지 기준(간단): 인묘진=봄, 사오미=여름, 신유술=가을, 해자축=겨울
    "인":"봄","묘":"봄","진":"봄",
    "사":"여름","오":"여름","미":"여름",
    "신":"가을","유":"가을","술":"가을",
    "해":"겨울","자":"겨울","축":"겨울",
}

PRODUCT_TOPIC_MAP = {
    "YEAR_2026": {
        "must": ["TIMING", "RELATION"],
        "opt":  ["ELEMENTS", "STRUCTURE", "GENERAL", "TEN_GODS", "CAREER", "WEALTH", "LOVE"],
        "k": 25
    }
}

def safe_json_load(s: Any, default):
    if s is None:
        return default
    if isinstance(s, (dict, list)):
        return s
    if isinstance(s, str):
        s = s.strip()
        if not s:
            return default
        try:
            return json.loads(s)
        except Exception:
            return default
    return default

def build_features_from_pillars(pillars: Dict[str, str]) -> Dict[str, Any]:
    """
    pillars: {"year":"무오","month":"정사","day":"무인","hour":"정사"(or None)}
    v0: 천간/지지/오행(표면) 카운트 + 태그셋 + 2026 상수 삽입
    """
    def split_ganji(x: str) -> Tuple[str, str]:
        if not x or len(x) < 2:
            return ("", "")
        return x[0], x[1]

    yg, yj = split_ganji(pillars.get("year",""))
    mg, mj = split_ganji(pillars.get("month",""))
    dg, dj = split_ganji(pillars.get("day",""))
    hg, hj = split_ganji(pillars.get("hour","") or "")

    stems = [g for g in [yg, mg, dg, hg] if g]
    branches = [j for j in [yj, mj, dj, hj] if j]

    elem_counts = {"목":0,"화":0,"토":0,"금":0,"수":0}
    for g in stems:
        e = GAN_ELEM.get(g)
        if e: elem_counts[e]+=1
    for j in branches:
        e = JI_ELEM.get(j)
        if e: elem_counts[e]+=1

    season = SEASON_BY_MONTH_BRANCH.get(mj, "미상")

    # 태그셋(매칭/FTS 보조)
    tags = set()
    # 간지 자체
    for p in [pillars.get("year",""), pillars.get("month",""), pillars.get("day",""), pillars.get("hour","")]:
        if p: tags.add(p)
    # 천간/지지
    tags.update(stems)
    tags.update(branches)
    # 오행
    for k,v in elem_counts.items():
        if v>0: tags.add(k)
    # 임수/무토 같은 형태
    for g in stems:
        e = GAN_ELEM.get(g)
        if e: tags.add(f"{g}{e}")
    for j in branches:
        e = JI_ELEM.get(j)
        if e: tags.add(f"{j}{e}")

    # 2026 상수(병오)
    tags.update(["2026","병오","병화","오화","화","확산","드러남","가속"])

    return {
        "pillars": pillars,
        "day_master": dg,          # 일간
        "month_branch": mj,        # 월지
        "season": season,
        "elements": elem_counts,   # v0 표면 카운트
        "tags": sorted(tags),
        "context": {
            "current_date": datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat(),
            "target_year": 2026,
            "target_year_ganji": "병오",
        }
    }

def write_sample_features(path: str):
    sample = build_features_from_pillars({
        "year":"무오",
        "month":"정사",
        "day":"무인",
        "hour":"정사",
    })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)
    print(f"✅ 샘플 user_features.json 생성 완료: {path}")

def detect_rule_cards_table(conn: sqlite3.Connection) -> str:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"DEBUG: 현재 DB에 존재하는 테이블들 -> {tables}") # 이 줄을 추가
    if "rule_cards" in tables:
        return "rule_cards"
    # 혹시 이름 다르면 후보 찾기
    for t in tables:
        if "rule" in t and "card" in t:
            return t
    raise RuntimeError("rule_cards 테이블을 못 찾았어. DB 테이블 이름 확인 필요.")

def get_table_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return [r[1] for r in cur.fetchall()]

def canonicalize(v: Any) -> Any:
    if isinstance(v, str):
        return v.strip()
    return v

def eval_op(left: Any, op: str, right: Any) -> bool:
    left = canonicalize(left)
    right = canonicalize(right)

    try:
        if op in ("==", "="):
            return left == right
        if op == "!=":
            return left != right
        if op == ">=":
            return float(left) >= float(right)
        if op == "<=":
            return float(left) <= float(right)
        if op == ">":
            return float(left) > float(right)
        if op == "<":
            return float(left) < float(right)
        if op == "in":
            if isinstance(right, list):
                if isinstance(left, list):
                    return any(x in right for x in left)
                return left in right
            return False
        if op == "not_in":
            if isinstance(right, list):
                if isinstance(left, list):
                    return all(x not in right for x in left)
                return left not in right
            return False
        if op == "contains":
            if isinstance(left, list):
                return right in left
            if isinstance(left, str):
                return str(right) in left
            return False
        if op == "not_contains":
            if isinstance(left, list):
                return right not in left
            if isinstance(left, str):
                return str(right) not in left
            return False
    except Exception:
        return False
    return False

def atomic_match(field: str, cond: Any, features: Dict[str, Any]) -> Tuple[bool, bool]:
    """
    returns: (matched, known)
    known=False if feature missing
    """
    # feature value 찾기 (2레벨까지)
    if field in features:
        val = features[field]
    elif field.startswith("pillars.") and isinstance(features.get("pillars"), dict):
        key = field.split(".", 1)[1]
        val = features["pillars"].get(key)
        if val is None:
            return (False, False)
    elif field.startswith("elements.") and isinstance(features.get("elements"), dict):
        key = field.split(".", 1)[1]
        val = features["elements"].get(key)
        if val is None:
            return (False, False)
    else:
        return (False, False)

    # cond 형태들 처리
    # 1) 스칼라/리스트: 기본 equality / membership
    if isinstance(cond, list):
        return (val in cond) if not isinstance(val, list) else (any(x in cond for x in val)), True
    if not isinstance(cond, dict):
        return (val == cond), True

    # 2) 연산자 dict: {">=": 3} / {"in":[...]} / {"contains":"..."}
    if len(cond) == 1:
        op, rhs = next(iter(cond.items()))
        return (eval_op(val, op, rhs), True)

    # 3) 복합: {"any":[{...},{...}]} or {"all":[...]}
    if "any" in cond and isinstance(cond["any"], list):
        known_any = False
        for sub in cond["any"]:
            m, k = atomic_match(field, sub, features) if not isinstance(sub, dict) else atomic_match(field, sub, features)
            known_any = known_any or k
            if k and m:
                return True, True
        return False, known_any

    if "all" in cond and isinstance(cond["all"], list):
        known_all = False
        for sub in cond["all"]:
            m, k = atomic_match(field, sub, features)
            known_all = known_all or k
            if k and not m:
                return False, True
        return True, known_all

    # 4) fallback: 모든 값 문자열화 후 태그 포함 여부로 판단
    tags = set(features.get("tags", []))
    flat = json.dumps(cond, ensure_ascii=False)
    return (any(t in flat for t in tags), True)

def trigger_score(trigger: Dict[str, Any], features: Dict[str, Any]) -> Tuple[float, Dict[str, int]]:
    """
    점수는 v0 휴리스틱.
    - 만족: +w
    - 불만족(known): -1.5w
    - unknown: 0
    """
    if not trigger:
        return 0.0, {"matched":0, "failed":0, "unknown":0, "total":0}

    weights = {
        "pillars.year": 3.0, "pillars.month": 3.0, "pillars.day": 3.5, "pillars.hour": 3.0,
        "day_master": 2.5, "month_branch": 2.0, "season": 1.5,
        # elements.* 는 기본 1.2
    }

    score = 0.0
    matched = failed = unknown = total = 0

    for k, cond in trigger.items():
        # trigger 키가 복잡하면 기본 경로로 매핑 시도
        field = k
        if k in ("year","month","day","hour"):
            field = f"pillars.{k}"
        if k in ("day_gan","day_master"):
            field = "day_master"
        if k in ("month_ji","month_branch"):
            field = "month_branch"
        if k in ("elements","five_elements"):
            # elements 전체 비교는 v0에서 skip
            continue
        # elements 하위키 지원: {"fire_count":{">=":3}} 같은 경우
        if k.endswith("_count"):
            # fire_count -> elements.화
            base = k.replace("_count","")
            elem_map = {"wood":"목","fire":"화","earth":"토","metal":"금","water":"수",
                        "목":"목","화":"화","토":"토","금":"금","수":"수"}
            elem = elem_map.get(base, None)
            if elem:
                field = f"elements.{elem}"

        w = weights.get(field, 1.2 if field.startswith("elements.") else 1.0)
        total += 1
        m, known = atomic_match(field, cond, features)
        if not known:
            unknown += 1
            continue
        if m:
            matched += 1
            score += w
        else:
            failed += 1
            score -= (1.5 * w)

    return score, {"matched":matched, "failed":failed, "unknown":unknown, "total":total}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--product", default="YEAR_2026")
    ap.add_argument("--features", required=True, help="user_features.json path")
    ap.add_argument("--out", default="top_k_rulecards.json")
    ap.add_argument("--make-sample", action="store_true", help="샘플 features 파일 생성 후 종료")
    args = ap.parse_args()

    if args.make_sample:
        write_sample_features(args.features)
        return

    product = PRODUCT_TOPIC_MAP.get(args.product)
    if not product:
        raise RuntimeError(f"Unknown product: {args.product}")

    with open(args.features, "r", encoding="utf-8") as f:
        features = json.load(f)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    table = detect_rule_cards_table(conn)
    cols = set(get_table_columns(conn, table))

    # 컬럼명 유연 대응
    col_id = "id" if "id" in cols else "card_id"
    col_topic = "topic" if "topic" in cols else "rule_topic"
    col_priority = "priority" if "priority" in cols else None
    col_trigger = "trigger" if "trigger" in cols else ("trigger_json" if "trigger_json" in cols else None)
    col_mech = "mechanism" if "mechanism" in cols else None
    col_interp = "interpretation" if "interpretation" in cols else None
    col_action = "action" if "action" in cols else None
    col_tags = "tags" if "tags" in cols else ("tags_json" if "tags_json" in cols else None)
    col_cautions = "cautions" if "cautions" in cols else ("cautions_json" if "cautions_json" in cols else None)

    must = product["must"]
    opt = product["opt"]
    topics = must + opt

    # 후보 로드
    cur = conn.cursor()
    q = f"SELECT * FROM {table} WHERE {col_topic} IN ({','.join(['?']*len(topics))})"
    rows = cur.execute(q, topics).fetchall()

    ranked = []
    for r in rows:
        rc = dict(r)
        trigger = safe_json_load(rc.get(col_trigger), {})
        tags = safe_json_load(rc.get(col_tags), [])
        cautions = safe_json_load(rc.get(col_cautions), [])

        base_score, stats = trigger_score(trigger, features)

        pr = int(rc.get(col_priority) or 5)
        topic = rc.get(col_topic)

        # 가중치: must 토픽 우대
        topic_boost = 2.0 if topic in must else 0.5
        pr_boost = pr * 0.35

        # 태그 겹침 보너스
        ftags = set(features.get("tags", []))
        tset = set(tags) if isinstance(tags, list) else set()
        overlap = len(ftags.intersection(tset))
        tag_boost = min(3.0, overlap * 0.4)

        final = base_score + topic_boost + pr_boost + tag_boost

        ranked.append({
            "id": rc.get(col_id),
            "topic": topic,
            "priority": pr,
            "score": round(final, 4),
            "match_stats": stats,
            "trigger": trigger,
            "mechanism": rc.get(col_mech, ""),
            "interpretation": rc.get(col_interp, ""),
            "action": rc.get(col_action, ""),
            "cautions": cautions if isinstance(cautions, list) else [],
            "tags": tags if isinstance(tags, list) else [],
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    topk = ranked[: product["k"]]

    payload = {
        "product": args.product,
        "k": product["k"],
        "generated_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "features": features,
        "top_k_rulecards": topk
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"✅ Top-K 저장 완료: {args.out}")
    print("Top 5:")
    for i, x in enumerate(topk[:5], 1):
        print(f"{i}. {x['id']} | {x['topic']} | P{x['priority']} | score={x['score']} | matched={x['match_stats']['matched']}/{x['match_stats']['total']}")

if __name__ == "__main__":
    main()
