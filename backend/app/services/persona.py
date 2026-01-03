def classify_persona(saju_summary: dict) -> dict:
    tg = saju_summary.get("ten_gods_distribution", {}) or {}
    missing_elements = saju_summary.get("missing_elements", []) or []

    wealth = tg.get("정재", 0) + tg.get("편재", 0)
    official = tg.get("정관", 0) + tg.get("편관", 0)
    output = tg.get("식신", 0) + tg.get("상관", 0)
    resource = tg.get("정인", 0) + tg.get("편인", 0)
    peer = tg.get("비견", 0) + tg.get("겁재", 0)

    # 1) 결핍형: 무재/무관/오행 결핍 같은 “부재 신호”가 핵심
    if wealth == 0 or official == 0 or len(missing_elements) >= 2:
        reason = f"결핍 신호(wealth={wealth}, official={official}, missing={missing_elements})"
        return {"persona_id": "missing", "persona_reason": reason}

    # 2) 과다형: 한 덩어리가 과도하게 커져서 “가지치기”가 성과
    buckets = {"비겁": peer, "식상": output, "인성": resource, "재성": wealth, "관성": official}
    dominant = max(buckets, key=buckets.get)
    dom_val = buckets[dominant]
    total = sum(buckets.values()) or 1
    if dom_val >= 6 or (dom_val / total) >= 0.45:
        reason = f"과다 신호({dominant}={dom_val}, ratio={dom_val/total:.2f})"
        return {"persona_id": "overflow", "persona_reason": reason}

    # 3) 위기형: 변동성/불균형이 커서 “방어”가 우선
    if len(missing_elements) >= 3 or (peer >= 5 and wealth <= 1):
        reason = f"위기 신호(peer={peer}, wealth={wealth}, missing={missing_elements})"
        return {"persona_id": "crisis", "persona_reason": reason}

    return {"persona_id": "standard", "persona_reason": "상대적으로 균형"}
