import json
import argparse
import os
from fpdf import FPDF
from fpdf.enums import XPos, YPos

class PremiumSajuPDF(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_text_color(150, 150, 150)
            self.set_font("Nanum", "", 9)
            self.cell(0, 10, "2026 SAJUOS PREMIUM REPORT | LetYou Consulting", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_draw_color(200, 200, 200)
            self.line(10, 18, 200, 18)
            self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Nanum", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Copyright 2026. LetYou All rights reserved. | Page {self.page_no()}", align="C")

def draw_score_bar(pdf, score):
    pdf.set_font("NanumBold", "", 12)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 10, f"종합 에너지 지수: {score}점", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    # 게이지 배경
    pdf.set_fill_color(240, 240, 240)
    pdf.rect(10, pdf.get_y(), 190, 8, "F")
    # 점수 바
    pdf.set_fill_color(40, 60, 120) # 다크 네이비
    pdf.rect(10, pdf.get_y(), 190 * (score / 100), 8, "F")
    pdf.ln(12)

def create_premium_pdf(json_path, out_path, font_dir):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    report = data["report"]["report_structure"]
    pack = data["pack"]
    features = pack["features"]

    pdf = PremiumSajuPDF()
    # 폰트 3종 등록
    pdf.add_font("Nanum", "", os.path.join(font_dir, "NanumGothic-Regular.ttf"))
    pdf.add_font("NanumBold", "", os.path.join(font_dir, "NanumGothic-Bold.ttf"))
    pdf.add_font("NanumExtra", "", os.path.join(font_dir, "NanumGothic-ExtraBold.ttf"))
    
    # --- [Page 1: Premium Cover] ---
    pdf.add_page()
    pdf.set_fill_color(40, 60, 120)
    pdf.rect(0, 0, 210, 297, "F") # 배경색
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("NanumExtra", "", 32)
    pdf.ln(80)
    pdf.cell(0, 20, "2026 신년 운세 보고서", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.set_font("Nanum", "", 16)
    pdf.ln(5)
    pdf.cell(0, 10, f"{features['day_master']}토 일간 사용자를 위한 프리미엄 가이드", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.set_y(-50)
    pdf.set_font("Nanum", "", 11)
    pdf.cell(0, 10, f"분석 일자: {data['report']['meta']['asof_date']}", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 10, "SajuOS Analysis Engine v0.2.1", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # --- [Page 2: Analysis Detail] ---
    pdf.add_page()
    pdf.set_text_color(40, 60, 120)
    pdf.set_font("NanumExtra", "", 20)
    pdf.cell(0, 20, "1. 종합 분석 리포트", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    # 점수 바
    draw_score_bar(pdf, report["1_overview"]["score"])
    
    # 요약 정보
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("NanumBold", "", 14)
    pdf.cell(0, 10, "■ 2026년 총론", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Nanum", "", 11)
    pdf.multi_cell(0, 8, report["1_overview"]["summary"])
    pdf.ln(10)
    
    # 오행 박스
    pdf.set_fill_color(245, 247, 250)
    pdf.set_font("NanumBold", "", 12)
    pdf.cell(0, 10, "  오행 분포 및 균형도", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    pdf.set_font("Nanum", "", 11)
    for el, val in features["elements"].items():
        pdf.cell(38, 10, f"  {el}: {val}개", border="B")
    pdf.ln(20)

    # --- [Page 3: Mechanics & Economy] ---
    pdf.set_font("NanumExtra", "", 20)
    pdf.set_text_color(40, 60, 120)
    pdf.cell(0, 20, "2. 세부 운용 및 경제 전략", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("NanumBold", "", 13)
    pdf.cell(0, 10, "💡 핵심 운용 메커니즘", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Nanum", "", 11)
    mech = report["2_mechanics"][0]
    pdf.multi_cell(0, 7, f"원리분석: {mech['analysis']}")
    pdf.ln(5)
    
    pdf.set_fill_color(255, 250, 240)
    pdf.set_font("NanumBold", "", 13)
    pdf.cell(0, 10, "💰 경제적 흐름 및 재물운", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Nanum", "", 11)
    pdf.multi_cell(0, 8, report["3_economic_flow"]["analysis"])

    pdf.output(out_path)
    print(f"✅ 프리미엄 PDF 생성 완료: {out_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="D:\\SajuOS_Data\\report_2026_v0_2.json")
    parser.add_argument("--out", default="D:\\SajuOS_Data\\Premium_Report_2026.pdf")
    parser.add_argument("--font_dir", default="D:\\SajuOS_Data")
    args = parser.parse_args()
    
    create_premium_pdf(args.input, args.out, args.font_dir)