# -*- coding: utf-8 -*-
"""วางแผนการศึกษาต่อในระดับอุดมศึกษาของนักเรียนโรงเรียนสองพิทยาคม — Streamlit App

ลำดับหน้า (state machine ผ่าน st.session_state["step"]):
welcome -> mbti_choice -> (mbti_select | function_test) -> mbti_summary
        -> interest_survey -> budget -> results
"""

import hmac
import html
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from mbti_result import display_mbti_result

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "results.db"

FN_ORDER = ["Ti", "Te", "Fe", "Fi", "Se", "Si", "Ne", "Ni"]
FN_TH = {
    "Ti": "การคิดวิเคราะห์เชิงตรรกะภายใน",
    "Te": "การคิดจัดระเบียบเชิงตรรกะภายนอก",
    "Fe": "ความรู้สึกเชื่อมโยงภายนอก",
    "Fi": "ความรู้สึกยึดคุณค่าภายใน",
    "Se": "การรับรู้ผัสสะในปัจจุบันขณะ",
    "Si": "การรับรู้ผัสสะเชิงเปรียบเทียบกับอดีต",
    "Ne": "การหยั่งรู้ความเป็นไปได้หลากหลาย",
    "Ni": "การหยั่งรู้เชิงวิสัยทัศน์และแก่นแท้",
}
CAT_ORDER = ["M", "S", "L", "H", "A"]
CAT_TH = {
    "M": "คณิตศาสตร์และคอมพิวเตอร์",
    "S": "วิทยาศาสตร์และเทคโนโลยี",
    "L": "ภาษาและวรรณกรรม",
    "H": "สังคมศึกษาและมนุษยศาสตร์",
    "A": "ศิลปะ ดนตรี",
}
SELF_STRENGTH = [100, 70, 35, 10]  # Dom -> Aux -> Tert -> Inf
STACK_WEIGHTS = [0.4, 0.3, 0.2, 0.1]
MAX_STACK_SCORE = sum(STACK_WEIGHTS)
SCALE_0_5 = [str(i) for i in range(6)]
SCALE_LABELS = {
    0: "ไม่เห็นด้วยอย่างยิ่ง", 1: "ไม่เห็นด้วย", 2: "ค่อนข้างไม่เห็นด้วย",
    3: "ค่อนข้างเห็นด้วย", 4: "เห็นด้วย", 5: "เห็นด้วยอย่างยิ่ง",
}
DISCLAIMER = ("นี่คือผลโดยประมาณเพื่อการสำรวจตนเอง "
              "ไม่ใช่ผลวินิจฉัยที่ตายตัว")

# พาเลตต์ประจำแอป (teal-อบอุ่น + สีร้องเรียกแบบนุ่ม) ใช้ทั้ง pie chart และ UI
PIE_COLORS = ["#2A9D8F", "#E9C46A", "#E76F51", "#355070",
              "#6D597A", "#B56576", "#84A59D", "#F4A261"]

APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Prompt:wght@500;600;700&family=Sarabun:wght@400;500;600;700&display=swap');

:root{--ink:#25333B;--line:rgba(37,51,59,.14);--teal:#0F766E;}

/* ---------- typography : Prompt หัวข้อ / Sarabun เนื้อความ ---------- */
.stApp, .stMarkdown p, li, td, th, .stRadio, .stButton, .stTextInput, .stSelectbox,
.stMultiselect, [data-testid="stExpander"]{
    font-family:'Sarabun','Noto Sans Thai',system-ui,sans-serif;color:var(--ink);}
h1,h2,h3,h4,h5,.stMarkdown h1,.stMarkdown h2,.stMarkdown h3,.stMarkdown h4,
[data-testid="stExpander"] summary{
    font-family:'Prompt','Sarabun',sans-serif;}
h1,h2{letter-spacing:.005em}

/* ---------- long Thai application title ---------- */
.app-title{
    font-family:'Prompt','Sarabun',sans-serif;
    font-size:clamp(2rem,2.65vw,2.65rem);
    font-weight:700;
    line-height:1.34;
    letter-spacing:.005em;
    margin:0 0 .7rem;
}
h1,.stMarkdown h1{
    font-size:clamp(2rem,2.65vw,2.65rem);
    line-height:1.34;
    margin-bottom:.7rem;
}
.sidebar-title{
    font-family:'Prompt','Sarabun',sans-serif;
    font-size:1.08rem;
    font-weight:700;
    line-height:1.5;
    letter-spacing:0;
    margin:0 0 .8rem;
}
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] .stMarkdown h2{
    font-size:1.08rem;
    line-height:1.5;
    letter-spacing:0;
    overflow-wrap:anywhere;
    margin:0 0 .8rem;
}
@media (max-width: 640px){
    h1,.stMarkdown h1{font-size:1.85rem;line-height:1.35;}
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] .stMarkdown h2{font-size:1rem;}
}
[data-testid="stHeader"]{background:transparent}

/* ---------- layout rhythm ---------- */
.block-container{padding-top:1.4rem;padding-bottom:3rem;}
hr{border:none;border-top:1px dashed var(--line);margin:1.05rem 0;}
.stCaption, [data-testid="stCaptionContainer"]{opacity:.78}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"]{background:#F2EDE2;border-right:1px solid var(--line);}

/* ---------- buttons ---------- */
.stButton>button{border-radius:10px;padding:.48rem 1.15rem;font-weight:600;
    font-family:'Prompt','Sarabun',sans-serif;border:1px solid rgba(15,118,110,.35);
    transition:transform .08s ease, box-shadow .12s ease;}
.stButton>button[kind="secondary"]{background:#fff;color:#134E4A;}
.stButton>button:hover{transform:translateY(-1px);}
.stButton>button[kind="primary"]:hover{box-shadow:0 3px 10px rgba(15,118,110,.22);}

/* ---------- inputs / selects ---------- */
[data-baseweb="select"]>div,[data-baseweb="input"],input[type="text"],
input[type="password"],textarea{border-radius:10px !important;}
input:focus,[data-baseweb="select"]>div:focus-within{
    border-color:var(--teal) !important;
    box-shadow:0 0 0 3px rgba(15,118,110,.15) !important;}

/* ---------- agreement scale: custom 0–5 circle buttons ---------- */
.agreement-question{font-weight:600;margin:.95rem 0 .3rem;}
[class*="st-key-score_"][class*="_option_"] button{
    width:52px !important;height:52px !important;min-height:52px !important;
    padding:0 !important;border-radius:999px !important;background:#fff !important;
    border:1.5px solid #D9D2C2 !important;color:#5F5A52 !important;
    font-family:'IBM Plex Mono','Sarabun',monospace !important;font-weight:700 !important;
    font-size:1rem !important;transition:transform .14s ease,background .14s ease,
    border-color .14s ease,box-shadow .14s ease !important;}
[class*="st-key-score_"][class*="_option_"] button:hover{
    border-color:#5B7B6F !important;transform:translateY(-1px);}
[class*="st-key-score_"][class*="_option_0"] button[kind="primary"]{
    background:#8A8175 !important;border:3px solid #8A8175 !important;color:#fff !important;}
[class*="st-key-score_"][class*="_option_1"] button[kind="primary"],
[class*="st-key-score_"][class*="_option_2"] button[kind="primary"],
[class*="st-key-score_"][class*="_option_3"] button[kind="primary"],
[class*="st-key-score_"][class*="_option_4"] button[kind="primary"],
[class*="st-key-score_"][class*="_option_5"] button[kind="primary"]{
    background:#20A464 !important;border:3px solid #20A464 !important;color:#fff !important;}
[class*="st-key-score_"][class*="_option_"] button[kind="primary"]{
    transform:scale(1.15);box-shadow:0 4px 12px rgba(91,123,111,.25) !important;}
@media (max-width: 640px){
    [class*="st-key-score_"][class*="_option_"] button{
        width:46px !important;height:46px !important;min-height:46px !important;}
}

/* ---------- progress ---------- */
[data-testid="stProgress"] [role="progressbar"]{height:9px;border-radius:999px;
    background:rgba(15,118,110,.14);overflow:hidden;}

/* ---------- alerts / expanders ---------- */
[data-testid="stAlert"]{border-radius:12px;border:1px solid var(--line);}
[data-testid="stExpander"]{border:1px solid var(--line);border-radius:12px;
    background:#fff;overflow:hidden;}
[data-testid="stExpanderDetails"]{background:#fff;}

/* ---------- welcome: ขั้นตอนแบบวงกลม ---------- */
.steps{display:flex;flex-direction:column;gap:.7rem;margin:.4rem 0 1rem;}
.step-row{display:flex;gap:.85rem;align-items:flex-start;}
.step-num{flex:0 0 auto;width:34px;height:34px;border-radius:999px;
    background:rgba(15,118,110,.12);color:var(--teal);display:flex;align-items:center;
    justify-content:center;font-family:'Prompt';font-weight:700;
    border:1.5px solid rgba(15,118,110,.4);}
.step-body b{font-family:'Prompt','Sarabun',sans-serif;}
.chip{display:inline-block;background:rgba(15,118,110,.10);
    border:1px solid rgba(15,118,110,.25);color:#134E4A;border-radius:999px;
    padding:.25rem .9rem;font-size:.85rem;font-weight:600;font-family:'Prompt';}

/* ---------- sidebar stepper ---------- */
.side-steps{display:flex;flex-direction:column;gap:.45rem;margin-bottom:.75rem;}
.sstep{display:flex;align-items:center;gap:.6rem;font-size:.93rem;}
.sstep.done{font-weight:600;}
.dot{width:22px;height:22px;border-radius:999px;display:inline-flex;align-items:center;
    justify-content:center;font-size:.72rem;font-weight:700;
    border:1.5px solid rgba(15,118,110,.45);color:var(--teal);background:#fff;}
.dot.done{background:var(--teal);color:#fff;border-color:var(--teal);}

/* ---------- MBTI result panels ---------- */
.mbti-panel{display:flex;gap:20px;align-items:flex-start;border-radius:14px;
    padding:20px 26px;}
.type-box{flex:0 0 auto;background:#fff;border-radius:12px;padding:10px 16px;}
.type-code{font-family:'Prompt';font-size:2.2rem;font-weight:700;line-height:1.1;}
.group-pill{display:inline-block;color:#fff;border-radius:999px;padding:3px 12px;
    font-size:.8rem;font-weight:600;font-family:'Prompt';}
.stack-card{border:1px solid;border-left-width:5px;border-radius:12px;
    padding:13px 15px;height:100%;}
.sc-role{font-size:.72rem;letter-spacing:.05em;opacity:.72;text-transform:uppercase;
    font-family:'Prompt';}
.sc-code{font-size:1.55rem;font-weight:700;font-family:'Prompt';margin:.2rem 0;}
.sc-en{font-size:.88rem;font-weight:600;}
.sc-th{font-size:.8rem;opacity:.72;margin-top:2px;}
.sw-panel{border-radius:12px;padding:6px 18px 16px;border:1px solid;height:100%;}
.sw-panel.strengths{background:#F0F7F1;border-color:rgba(5,150,105,.25);
    border-left:5px solid #059669;}
.sw-panel.grow{background:#FCF6EA;border-color:rgba(217,119,6,.28);
    border-left:5px solid #D97706;}
.sw-panel h4{margin:.55rem 0 .2rem;}
.sw-panel ul{padding-left:1.1rem;margin:.35rem 0 0;}
.sw-panel li{margin:.32rem 0;}

/* ---------- results rank table (เน้นอันดับ 1-3) ---------- */
.rank-table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:14px;
    background:#fff;}
table.rank-table{width:100%;border-collapse:collapse;font-size:.92rem;}
.rank-table th{font-family:'Prompt';font-weight:600;text-align:left;
    background:rgba(15,118,110,.10);padding:.6rem .75rem;white-space:nowrap;
    color:#134E4A;border-bottom:2px solid rgba(15,118,110,.25);}
.rank-table td{padding:.55rem .75rem;border-bottom:1px solid var(--line);
    vertical-align:top;}
.rank-table tbody tr:last-child td{border-bottom:none;}
.rank-table tr:nth-child(even):not(.top){background:rgba(37,51,59,.03);}
tr.rank1 td{background:rgba(233,196,106,.30);font-weight:600;}
tr.rank2 td{background:rgba(160,168,178,.18);font-weight:600;}
tr.rank3 td{background:rgba(180,121,74,.16);font-weight:600;}
.badge{display:inline-flex;min-width:26px;height:26px;border-radius:999px;
    align-items:center;justify-content:center;font-family:'Prompt';
    font-weight:700;padding:0 4px;}
.b1{background:#B8860B;color:#fff;}
.b2{background:#8A94A6;color:#fff;}
.b3{background:#B4794A;color:#fff;}
.bn{background:#EEF2F0;color:#40514B;border:1px solid var(--line);}
.matchbar{height:6px;border-radius:999px;background:rgba(15,118,110,.15);
    min-width:90px;margin-top:4px;}
.matchbar i{display:block;height:100%;border-radius:999px;background:var(--teal);}
.sort-score-note{margin-top:3px;color:#6B7280;font-size:.72rem;font-weight:400;
    line-height:1.25;}
.column-info{display:inline-flex;align-items:center;justify-content:center;
    width:16px;height:16px;margin-left:4px;border:1px solid currentColor;
    border-radius:999px;font-size:.68rem;vertical-align:middle;cursor:help;}
</style>
"""


def inject_css():
    st.markdown(APP_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------- data loading
@st.cache_data(show_spinner=False)
def load_json(name):
    with open(DATA_DIR / name, encoding="utf-8-sig") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def parse_function_questions():
    """Parse MBTI_2.txt -> {func: [10 questions]}"""
    text = (DATA_DIR / "MBTI_2.txt").read_text(encoding="utf-8-sig")
    result = {}
    current = None
    for line in text.splitlines():
        m = re.match(r"^##\s+(Ti|Te|Fe|Fi|Se|Si|Ne|Ni)\b", line)
        if m:
            current = m.group(1)
            result[current] = []
            continue
        if line.startswith("## "):
            current = None
            continue
        m = re.match(r"^\s*(\d+)\.\s+(.+)$", line)
        if m and current is not None and len(result[current]) < 10:
            result[current].append(m.group(2).strip())
    return {k: v for k, v in result.items() if len(v) == 10}


@st.cache_data(show_spinner=False)
def parse_interest_questions(file_mtime_ns):
    """Parse ความชอบ2.txt -> {cat: {"title": ..., "questions": [20 items]}}.

    The mtime is deliberately a cache key: changes to the question file must
    invalidate Streamlit's cached survey data.
    """
    text = (DATA_DIR / "ความชอบ2.txt").read_text(encoding="utf-8-sig")
    titles = {}
    questions = {}
    order = []
    current = None
    for i, line in enumerate(text.splitlines()):
        m = re.match(r"^##\s+(\d+)\.\s+(.+)$", line)
        if m and int(m.group(1)) <= 5:
            cat = CAT_ORDER[int(m.group(1)) - 1]
            current = cat
            titles[cat] = m.group(2).strip()
            questions[cat] = []
            order.append(cat)
            continue
        m = re.match(r"^\s*(\d+)\.\s+(.+)$", line)
        if m and current is not None and len(questions[current]) < 20:
            questions[current].append(m.group(2).strip())
    return ({c: {"title": titles[c], "questions": questions[c]}
             for c in order if len(questions[c]) == 20})


FACULTY_DB = load_json("faculty_database_v2.json")
MBTI_TYPES = load_json("mbti_type_descriptions.json")
BUDGET_TIERS = FACULTY_DB["budgetTiers"]
FACULTIES = FACULTY_DB["facultyDatabase"]

# เกณฑ์กลุ่มค่าเรียนจาก "จัดกลุ่มค่าเรียนแต่ละคณะ.docx".  กำหนด
# รายคณะโดยตรง (แทนการเดาจากข้อความค่าเทอมหรือชื่อ group) เพื่อให้
# การกรองผลลัพธ์เป็นเงื่อนไขจริง: คณะจะแสดงได้ก็ต่อเมื่องบที่เลือกตรงกัน.
FACULTY_FUNDING_TIERS = {
    # ระดับสูง
    "แพทยศาสตร์": "B3",
    "ทันตแพทยศาสตร์": "B3",
    "เภสัชศาสตร์": "B3",
    "สัตวแพทยศาสตร์": "B3",
    "ดุริยางคศาสตร์ (ดนตรี)": "B3",
    "ภาพยนตร์และสื่อดิจิทัล": "B3",
    "UX/UI Design": "B3",
    "Game Design": "B3",
    "Computer Graphics/Digital Animation": "B3",

    # ระดับปานกลาง
    "วิศวกรรมคอมพิวเตอร์/ซอฟต์แวร์": "B2",
    "วิทยาการคอมพิวเตอร์/IT": "B2",
    "วิศวกรรมไฟฟ้า/อิเล็กทรอนิกส์": "B2",
    "วิศวกรรมเครื่องกล": "B2",
    "วิศวกรรมโยธา": "B2",
    "วิศวกรรมเคมี": "B2",
    "วิศวกรรมอุตสาหการ": "B2",
    "วิศวกรรมการบิน/อวกาศ": "B2",
    "วิทยาการข้อมูล (Data Science)": "B2",
    "คณิตศาสตร์/สถิติประยุกต์": "B2",
    "วิทยาศาสตร์ (ฟิสิกส์/เคมี)": "B2",
    "วิทยาศาสตร์ (ชีววิทยา)": "B2",
    "วิทยาศาสตร์สิ่งแวดล้อม": "B2",
    "ธรณีวิทยา": "B2",
    "เกษตรศาสตร์/อุตสาหกรรมเกษตร": "B2",
    "สถาปัตยกรรมศาสตร์": "B2",
    "พยาบาลศาสตร์": "B2",
    "สหเวชศาสตร์/เทคนิคการแพทย์": "B2",
    "สาธารณสุขศาสตร์": "B2",
    "กายภาพบำบัด": "B2",
    "วิทยาศาสตร์การกีฬา": "B2",
    "แพทย์แผนไทยประยุกต์": "B2",
    "ทัศนมาตรศาสตร์ (Optometry)": "B2",
    "รังสีเทคนิค": "B2",
    "วิจิตรศิลป์": "B2",
    "ศิลปกรรมศาสตร์ (ออกแบบประยุกต์)": "B2",
    "มัณฑนศิลป์/ออกแบบภายใน": "B2",
    "นาฏศิลป์/การแสดง": "B2",
    "ออกแบบนิเทศศิลป์ (Graphic Design)": "B2",
    "แฟชั่นดีไซน์": "B2",
    "จิตวิทยาคลินิก": "B2",
    "คณิตศาสตร์ประกันภัย (Actuarial Science)": "B2",
    "FinTech": "B2",
    "ชีวสารสนเทศศาสตร์ (Bioinformatics)": "B2",

    # ระดับต่ำ
    "ประมง (Fisheries)": "B1",
    "อักษรศาสตร์/ศิลปศาสตร์ (ภาษาต่างประเทศ)": "B1",
    "ภาษาไทย/วรรณคดี": "B1",
    "ประวัติศาสตร์": "B1",
    "ปรัชญา": "B1",
    "ครุศาสตร์/ศึกษาศาสตร์": "B1",
    "บรรณารักษศาสตร์/สารสนเทศศาสตร์": "B1",
    "ภาษาศาสตร์ (Linguistics)": "B1",
    "รัฐศาสตร์ (การปกครอง)": "B1",
    "นิติศาสตร์": "B1",
    "เศรษฐศาสตร์": "B1",
    "บริหารธุรกิจ": "B1",
    "การบัญชี": "B1",
    "นิเทศศาสตร์/วารสารศาสตร์": "B1",
    "จิตวิทยา": "B1",
    "สังคมสงเคราะห์ศาสตร์": "B1",
    "สังคมวิทยาและมานุษยวิทยา": "B1",
    "การท่องเที่ยวและการโรงแรม": "B1",
    "รัฐประศาสนศาสตร์": "B1",
    "การจัดการทรัพยากรมนุษย์": "B1",
    "สังคมศาสตร์สิ่งแวดล้อม": "B1",
    "นโยบายสาธารณสุข": "B1",
    "ความสัมพันธ์ระหว่างประเทศ": "B1",
    "นักการทูต": "B1",
    "ธุรกิจ/การตลาดระหว่างประเทศ": "B1",
}


# ---------------------------------------------------------------- scoring core
def strengths_from_type(type_code):
    """เส้นทาง 'เลือกเอง': stack Dom->Aux->Tert->Inf => [100,70,35,10], นอก stack = 0"""
    stack = MBTI_TYPES[type_code]["stack"]
    s = {f: 0 for f in FN_ORDER}
    for f, v in zip(stack, SELF_STRENGTH):
        s[f] = float(v)
    return s


def strengths_from_raw(raw_scores):
    """เส้นทาง 'ทำแบบทดสอบ': normalize คะแนน 0–50 เป็น 0–100."""
    return {f: round(raw_scores[f] / 50 * 100, 1) for f in FN_ORDER}


def stack_similarity(top4, stack):
    """Return weighted positional similarity for two four-function stacks (0–1)."""
    score = sum(w for w, user_fn, type_fn
                in zip(STACK_WEIGHTS, top4, stack) if user_fn == type_fn)
    return score / MAX_STACK_SCORE


def closest_mbti_type(strengths):
    """Find the closest MBTI stack using weighted positional similarity."""
    top4 = sorted(FN_ORDER, key=lambda f: strengths[f], reverse=True)[:4]
    best_type, best_sim = None, -1.0
    for code, info in MBTI_TYPES.items():
        sim = stack_similarity(top4, info["stack"])
        if sim > best_sim:
            best_type, best_sim = code, sim
    return best_type, round(best_sim * 100, 1), top4


def mbti_score(fac, strengths):
    funcs = fac["functions"]
    scope = fac.get("scope", "D/A")
    da = max(strengths[f] for f in funcs)  # scope D/A -> max
    if scope == "D/A":
        return da
    if scope == "Mixed":
        function_scopes = fac.get("functionScopes")
        if function_scopes:
            da_funcs = function_scopes.get("D/A", [])
            dominant_funcs = function_scopes.get("Dominant", [])
            da_score = max((strengths[f] for f in da_funcs), default=0)
            dominant = max(FN_ORDER, key=lambda f: strengths[f])
            dominant_score = strengths[dominant] if dominant in dominant_funcs else 0
            return max(da_score, dominant_score)
        return da  # Backward compatibility for legacy Mixed records.
    dominant = max(FN_ORDER, key=lambda f: strengths[f])
    dom_method = da if dominant in funcs else da * 0.5
    return dom_method


def subj_score(fac, cat_scores):
    """Score shown to users: each condition ratio is capped at 100%."""
    ratios = [min(cat_scores[c["cat"]] / c["min"] * 100, 100)
              for c in fac["conditions"]]
    return min(ratios)


def mbti_score_uncapped(fac, strengths):
    """Ranking-only MBTI score.

    Function strengths already lie in the 0–100 range, so the display score is
    also the uncapped score.
    """
    return mbti_score(fac, strengths)


def subj_score_uncapped(fac, cat_scores):
    """Ranking-only subject score: preserve how far a score exceeds the threshold."""
    ratios = [cat_scores[c["cat"]] / c["min"] * 100
              for c in fac["conditions"]]
    return min(ratios)


def has_no_interest_preference(cat_scores):
    """Return True only when all five interest-category totals are zero."""
    return all(cat_scores.get(category, 0) == 0 for category in CAT_ORDER)


def build_reason(fac, strengths, cat_scores):
    parts = []
    fn_pairs = sorted(((f, round(strengths[f])) for f in fac["functions"]),
                      key=lambda x: -x[1])
    strong = [f"{f} {v}%" for f, v in fn_pairs[:2] if v >= 50]
    if strong:
        parts.append("ฟังก์ชันเด่นตรง: " + ", ".join(strong))
    for c in fac["conditions"]:
        ok = "ผ่าน" if cat_scores[c["cat"]] >= c["min"] else "ไม่ผ่าน"
        parts.append(f"{c['cat']} {ok} ({round(cat_scores[c['cat']])}/{c['min']})")
    return " · ".join(parts)


def funding_tier_for_faculty(fac):
    """Return the explicit funding tier for a faculty, or None if it is unknown."""
    return FACULTY_FUNDING_TIERS.get(fac["name"])


FUNDING_TIER_ORDER = ("B1", "B2", "B3")


def affordable_funding_tiers(budget_tier):
    """Return the selected tier and every lower tier, highest one first."""
    if budget_tier not in FUNDING_TIER_ORDER:
        raise ValueError(f"Unknown budget tier: {budget_tier}")
    selected_index = FUNDING_TIER_ORDER.index(budget_tier)
    return tuple(reversed(FUNDING_TIER_ORDER[:selected_index + 1]))


def order_rows_by_funding_tier(rows, budget_tier):
    """Group affordable results from the highest affordable tier to the lowest.

    Python's stable sort preserves the existing Match% / sortScore order within
    every funding group, so this does not change the ranking tie-break rule.
    """
    tier_priority = {tier: index for index, tier in enumerate(
        affordable_funding_tiers(budget_tier)
    )}
    return sorted(rows, key=lambda row: tier_priority[
        funding_tier_for_faculty(row["_fac"])
    ])


def rank_faculties(strengths, cat_scores, budget_tier=None):
    """Rank faculties that do not exceed the user's selected funding tier."""
    if budget_tier is not None and budget_tier not in BUDGET_TIERS:
        raise ValueError(f"Unknown budget tier: {budget_tier}")

    affordable_tiers = (affordable_funding_tiers(budget_tier)
                         if budget_tier is not None else None)
    rows = []
    for fac in FACULTIES:
        if (affordable_tiers is not None
                and funding_tier_for_faculty(fac) not in affordable_tiers):
            continue
        ms = mbti_score(fac, strengths)
        ss = subj_score(fac, cat_scores)
        ms_uncapped = mbti_score_uncapped(fac, strengths)
        ss_uncapped = subj_score_uncapped(fac, cat_scores)
        match = round(0.3 * ms + 0.7 * ss, 1)
        sort_score = 0.3 * ms_uncapped + 0.7 * ss_uncapped
        rows.append({
            "name": fac["name"],
            "group": fac["group"],
            "mbtiScore": round(ms, 1),
            "subjScore": round(ss, 1),
            "match": match,
            "sortScore": sort_score,
            "reason": build_reason(fac, strengths, cat_scores),
            "_fac": fac,
        })
    # Keep the table in descending order of the Match% shown to users.
    # sortScore resolves only equal displayed percentages, then name resolves
    # exact ties deterministically.
    rows.sort(key=lambda r: (-r["match"], -r["sortScore"], r["name"]))
    return rows


# ---------------------------------------------------------------- sqlite
def init_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        name TEXT,
        mbti_method TEXT,
        mbti_type TEXT,
        Ti REAL, Te REAL, Fe REAL, Fi REAL,
        Se REAL, Si REAL, Ne REAL, Ni REAL,
        M INTEGER, S INTEGER, L INTEGER, H INTEGER, A INTEGER,
        budget TEXT,
        top_faculties TEXT)""")
    conn.commit()
    return conn


def save_result(payload, db_path=DB_PATH):
    conn = init_db(db_path)
    cols = ",".join(payload.keys())
    marks = ",".join("?" * len(payload))
    conn.execute(f"INSERT INTO results ({cols}) VALUES ({marks})",
                 tuple(payload.values()))
    conn.commit()
    rid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return rid


def result_payload(strengths, cat_scores, budget):
    """Build the history record at the moment a user confirms their budget."""
    rows = order_rows_by_funding_tier(
        rank_faculties(strengths, cat_scores, budget), budget
    )
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "name": st.session_state["name"],
        "mbti_method": "เลือกเอง" if st.session_state["mbti_route"] == "self"
                       else "ทำแบบทดสอบ",
        "mbti_type": st.session_state["derived_type"],
        **{f: round(strengths[f], 1) for f in FN_ORDER},
        **{c: int(cat_scores[c]) for c in CAT_ORDER},
        "budget": budget,
        "top_faculties": " | ".join(
            f"{i}. {r['name']} ({r['match']}%)"
            for i, r in enumerate(rows[:3], 1)),
    }


def load_history(db_path=DB_PATH):
    if not Path(db_path).exists():
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql("SELECT * FROM results ORDER BY id DESC", conn)
    finally:
        conn.close()
    return df


def delete_result(record_id, db_path=DB_PATH):
    """ลบเรคคอร์ดตาม id (ไม่แก้ schema)"""
    conn = init_db(db_path)
    conn.execute("DELETE FROM results WHERE id = ?", (int(record_id),))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------- chart helpers
def _style_pie(fig, title, legend_size=11):
    """จัดสไตล์ร่วมของ pie ทุกตัว: ฟอนต์/พื้นหลังโปร่ง/margin เดียวกันทั้งแอป"""
    fig.update_traces(hole=0.45, marker_line_color="#FFFFFF",
                      marker_line_width=2)
    fig.update_layout(title_text=title, title_x=0.5,
                      title_font={"family": "Prompt, sans-serif", "size": 16},
                      legend_font={"family": "Sarabun, sans-serif",
                                   "size": legend_size},
                      paper_bgcolor="rgba(0,0,0,0)",
                      margin=dict(t=52, b=10, l=10, r=10))
    return fig


def pie_functions(strengths):
    labels = [f"{f} — {FN_TH[f]}" for f in FN_ORDER]
    fig = px.pie(names=labels, values=[strengths[f] for f in FN_ORDER],
                 color_discrete_sequence=PIE_COLORS)
    return _style_pie(fig, "สัดส่วนการใช้ Cognitive Functions ของคุณ")


def pie_categories(cat_scores):
    labels = [f"{c} — {CAT_TH[c]}" for c in CAT_ORDER]
    fig = px.pie(names=labels, values=[cat_scores[c] for c in CAT_ORDER],
                 color_discrete_sequence=PIE_COLORS)
    return _style_pie(fig, "ความชอบ 5 หมวด (M, S, L, H, A)")


def pie_top_faculties(top10_rows):
    """Build the faculty chart from the same sorted top-10 data as the table."""
    top = top10_rows[:5]
    fig = px.pie(names=[f"{r['name']} ({r['match']}%)" for r in top],
                 values=[r["match"] for r in top],
                 color_discrete_sequence=PIE_COLORS)
    fig.update_layout(legend_font_size=9)
    return _style_pie(fig, "5 คณะที่ Match % สูงสุด")


# ---------------------------------------------------------------- session state
def init_session():
    defaults = {
        "step": "welcome",
        "name": "",
        "mbti_route": None,       # "self" | "test"
        "chosen_type": None,
        "fn_index": 0,
        "func_raw": {},
        "function_strengths": None,
        "derived_type": None,
        "type_similarity": None,
        "interest_index": 0,
        "interest_answers": {},
        "cat_scores": None,
        "budget_tier": None,
        "saved_id": None,
        "show_history": False,
        "admin_authenticated": False,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def goto(step):
    st.session_state["step"] = step
    st.rerun()


def logout_admin():
    """Clear admin-only UI state before Streamlit renders its widgets again."""
    st.session_state["admin_authenticated"] = False
    st.session_state["show_history"] = False


def nav_back(step):
    if st.button("← ย้อนกลับ"):
        goto(step)


def saved_answer_at(answers, index):
    """Return a previously saved survey answer from either legacy dict or list data."""
    if isinstance(answers, list):
        return answers[index] if 0 <= index < len(answers) else None
    if isinstance(answers, dict):
        return answers.get(index)
    return None


def render_agreement_selector(question, key, default=None):
    """Render the 0–5 forced-choice agreement control and return None or 0–5."""
    state_key = f"score_{key}"
    if state_key not in st.session_state and default in SCALE_LABELS:
        st.session_state[state_key] = default

    st.markdown(f'<div class="agreement-question">{html.escape(question)}</div>',
                unsafe_allow_html=True)
    cols = st.columns(6)
    for score, col in enumerate(cols):
        selected = st.session_state.get(state_key) == score
        with col:
            if st.button(str(score), key=f"{state_key}_option_{score}",
                         type="primary" if selected else "secondary",
                         help=SCALE_LABELS[score], use_container_width=True):
                st.session_state[state_key] = score
                st.rerun()
    return st.session_state.get(state_key)


def admin_password():
    """Return the configured Streamlit Secrets password, if one exists."""
    try:
        return st.secrets.get("ADMIN_PASSWORD")
    except FileNotFoundError:
        return None


def is_admin_password(password):
    """Check an administrator password stored only in Streamlit Secrets."""
    expected = admin_password()
    return bool(expected) and hmac.compare_digest(password, expected)


# ---------------------------------------------------------------- pages
def page_welcome():
    st.markdown(
        '<h1 class="app-title">วางแผนการศึกษาต่อในระดับอุดมศึกษา<br>'
        'ของนักเรียนโรงเรียนสองพิทยาคม</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        "แอปนี้ช่วยให้คุณรู้จักตัวเองมากขึ้น "
        "แล้วจับคู่กับ **คณะ/สาขาที่เหมาะกับคุณ** ผ่าน 3 ส่วนประกอบ:"
    )
    st.markdown(
        """
        <div class="steps">
          <div class="step-row"><div class="step-num">1</div>
            <div class="step-body"><b>Cognitive Functions (MBTI)</b> —
            เลือก type ที่รู้แล้ว หรือทำแบบทดสอบ 80 ข้อ</div></div>
          <div class="step-row"><div class="step-num">2</div>
            <div class="step-body"><b>ความชอบ</b> —
            แบบสำรวจ 5 หมวด (100 ข้อ แบ่ง 5 หน้า)</div></div>
          <div class="step-row"><div class="step-num">3</div>
            <div class="step-body"><b>งบประมาณการศึกษา</b> —
            เพื่อแนะนำมหาวิทยาลัยที่เหมาะกับกำลังจ่าย</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<span class="chip">⏱ ใช้เวลารวมประมาณ 15–25 นาที · '
                "ไม่มีคำตอบถูกหรือผิด ตอบตามความจริงใจของตัวเองได้เลย</span>",
                unsafe_allow_html=True)
    st.markdown("")
    name = st.text_input("ชื่อ / ชื่อเล่น", value=st.session_state["name"])
    if st.button("เริ่ม", type="primary", disabled=(not name.strip())):
        st.session_state["name"] = name.strip()
        goto("mbti_choice")


def page_mbti_choice():
    st.header("คุณรู้ผล MBTI ของคุณหรือไม่?")
    choice = st.radio(
        "เลือกทางเลือกที่ตรงกับคุณ:",
        options=["ฉันรู้ผล MBTI ของตัวเองอยู่แล้ว (จะเลือกเอง)",
                 "ฉันยังไม่รู้ อยากทำแบบทดสอบ Cognitive Functions (80 ข้อ)"],
        index=None,
    )
    c1, c2 = st.columns([1, 1])
    with c1:
        nav_back("welcome")
    with c2:
        if st.button("ถัดไป →", type="primary", disabled=(choice is None)):
            if choice.startswith("ฉันรู้ผล"):
                st.session_state["mbti_route"] = "self"
                goto("mbti_select")
            else:
                st.session_state["mbti_route"] = "test"
                st.session_state["fn_index"] = 0
                st.session_state["func_raw"] = {}
                goto("function_test")


def page_mbti_select():
    st.header("เลือกประเภท MBTI ของคุณ")
    options = [f"{code} — {info['title']}" for code, info in MBTI_TYPES.items()]
    sel = st.selectbox("ประเภท MBTI (16 แบบ)", options, index=None,
                       placeholder="— เลือกประเภท —")
    c1, c2 = st.columns([1, 1])
    with c1:
        nav_back("mbti_choice")
    with c2:
        if st.button("ยืนยันและดูสรุป →", type="primary", disabled=(sel is None)):
            code = sel.split(" — ")[0]
            st.session_state["chosen_type"] = code
            st.session_state["derived_type"] = code
            st.session_state["type_similarity"] = None
            st.session_state["function_strengths"] = strengths_from_type(code)
            goto("mbti_summary")


def page_function_test(fn_questions):
    idx = st.session_state["fn_index"]
    func = FN_ORDER[idx]
    done = len(st.session_state["func_raw"])
    st.caption(f"ความคืบหน้า {done}/8 ฟังก์ชัน")
    st.progress(done / 8)
    st.header(f"ฟังก์ชัน {func} — {FN_TH[func]}")
    st.caption(f"หน้า {idx + 1} / 8 · ข้อ {idx * 10 + 1}–{idx * 10 + 10}")

    unanswered = []
    for i, q in enumerate(fn_questions[func]):
        key = f"ans_{func}_{i}"
        val = render_agreement_selector(f"{idx * 10 + i + 1}. {q}", key)
        if val is None:
            unanswered.append(idx * 10 + i + 1)

    label = ("เสร็จสิ้น — ดูผล MBTI" if idx == 7 else "ถัดไป (ฟังก์ชันถัดไป)")
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("← ฟังก์ชันก่อนหน้า", disabled=(idx == 0)):
            st.session_state["fn_index"] -= 1
            st.rerun()
    with c2:
        if st.button(label, type="primary"):
            if unanswered:
                st.warning("กรุณาตอบให้ครบทุกข้อก่อนไปต่อ "
                           "(ข้อที่ยังไม่ได้ตอบ: "
                           + ", ".join(map(str, unanswered)) + ")")
            else:
                raw = sum(st.session_state[f"score_ans_{func}_{i}"] for i in range(10))
                st.session_state["func_raw"][func] = raw
                if idx == 7:
                    st.session_state["function_strengths"] = \
                        strengths_from_raw(st.session_state["func_raw"])
                    best, sim, _ = closest_mbti_type(st.session_state["function_strengths"])
                    st.session_state["derived_type"] = best
                    st.session_state["type_similarity"] = sim
                    goto("mbti_summary")
                else:
                    st.session_state["fn_index"] += 1
                    st.rerun()


def page_mbti_summary():
    route = st.session_state["mbti_route"]
    code = st.session_state["derived_type"]
    info = MBTI_TYPES[code]
    st.subheader(f"สรุปผล MBTI ของคุณ{name_suffix()}")

    if route == "self":
        st.success(f"คุณเลือกประเภทของตัวเอง: **{code} — {info['title']}**")
    else:
        sim = st.session_state["type_similarity"]
        st.success(f"จากแบบทดสอบ ประเภทที่ใกล้เคียงที่สุดของคุณคือ "
                   f"**{code} — {info['title']}** (ความเข้ากันได้ ~{sim}%)")

    # หน้าแสดงผลลัพธ์ MBTI แบบละเอียด (nickname, function stack, จุดแข็ง–จุดที่ควรพัฒนา)
    display_mbti_result(code)

    st.caption(DISCLAIMER)

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("← เปลี่ยนวิธีหา MBTI"):
            for k in ("mbti_route", "chosen_type", "derived_type",
                      "type_similarity", "function_strengths"):
                st.session_state[k] = None
            st.session_state["func_raw"] = {}
            goto("mbti_choice")
    with c2:
        if st.button("ทำแบบสำรวจความชอบต่อ →", type="primary"):
            st.session_state["interest_index"] = 0
            goto("interest_survey")


def page_interest_survey(survey):
    idx = st.session_state["interest_index"]
    cat = CAT_ORDER[idx]
    block = survey[cat]
    completed = len(st.session_state["interest_answers"])
    st.caption(f"ความคืบหน้า: ทำเสร็จแล้ว {completed}/5 หมวด")
    st.progress(completed / 5)
    st.header(f"หมวด {idx + 1}/5: {block['title']}")
    st.caption("เลือกคำตอบที่ใกล้กับความเห็นของคุณที่สุด (0–5)")

    answers = st.session_state["interest_answers"].get(cat, {})
    unanswered = []
    for i, q in enumerate(block["questions"]):
        key = f"in_{cat}_{i}"
        default = saved_answer_at(answers, i)
        val = render_agreement_selector(f"{i + 1}. {q}", key, default)
        if val is None:
            unanswered.append(i + 1)

    label = "เสร็จสิ้นหมวดนี้ — ไปเลือกงบประมาณ" if idx == 4 else "ถัดไป (หมวดถัดไป)"
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("← หมวดก่อนหน้า", disabled=(idx == 0)):
            st.session_state["interest_index"] -= 1
            st.rerun()
    with c2:
        if st.button(label, type="primary"):
            if unanswered:
                st.warning("กรุณาตอบให้ครบทุกข้อก่อนไปต่อ "
                           "(ข้อที่ยังไม่ได้ตอบ: "
                           + ", ".join(map(str, unanswered)) + ")")
            else:
                vals = [st.session_state[f"score_in_{cat}_{i}"] for i in range(20)]
                st.session_state["interest_answers"][cat] = vals
                if idx == 4:
                    st.session_state["cat_scores"] = {
                        c: sum(v) for c, v in st.session_state["interest_answers"].items()}
                    goto("budget")
                else:
                    st.session_state["interest_index"] += 1
                    st.rerun()


def page_budget():
    st.header("ระดับงบประมาณการศึกษาต่อเทอม")
    st.caption("เกณฑ์กำลังจ่ายจริงของครอบครัว (จาก การเงิน.txt) — B1 ≤15,000 / "
               "B2 15,001–40,000 / B3 ≥40,001 บาท/เทอม")
    tier_keys = ["B1", "B2", "B3"]
    opts = [f"{t['label']} — {t['desc']}" for t in
            (BUDGET_TIERS[k] for k in tier_keys)]
    sel = st.radio("เลือกระดับงบ:", opts, index=None)
    c1, c2 = st.columns([1, 1])
    with c1:
        nav_back("interest_survey")
    with c2:
        if st.button("ยืนยันและดูผลลัพธ์ →", type="primary", disabled=(sel is None)):
            budget = tier_keys[opts.index(sel)]
            try:
                payload = result_payload(
                    st.session_state["function_strengths"],
                    st.session_state["cat_scores"],
                    budget,
                )
                st.session_state["saved_id"] = save_result(payload)
                st.session_state["budget_tier"] = budget
                goto("results")
            except Exception as e:
                st.error(f"บันทึกประวัติไม่สำเร็จ: {e}")


def page_results():
    strengths = st.session_state["function_strengths"]
    cat_scores = st.session_state["cat_scores"]
    budget = st.session_state.get("budget_tier")
    rows = rank_faculties(strengths, cat_scores, budget)
    rows = order_rows_by_funding_tier(rows, budget)
    top10 = rows[:10]
    tier_desc = BUDGET_TIERS[budget]["label"]

    st.header(f"ผลลัพธ์ของ{name_suffix()}")
    st.success(f"MBTI: **{st.session_state['derived_type']}** · "
               f"งบ: **{budget} ({tier_desc})**")
    if st.session_state.get("saved_id") is not None:
        st.caption("บันทึกผลลัพธ์ลงประวัติเรียบร้อยแล้ว")
    if has_no_interest_preference(cat_scores):
        st.warning("ไม่พบคณะที่เข้ากันได้จากความชอบ เนื่องจากคะแนนความชอบทุกหมวดเป็น 0 "
                   "จึงแสดงผลคณะที่เข้ากับ MBTI ให้แทน")

    if top10:
        # คณะที่ Match สูงสุด 3 อันดับ แสดงก่อนตาราง
        medals = ["🥇", "🥈", "🥉"]
        for i, r in enumerate(top10[:3], start=1):
            fac = r["_fac"]
            with st.expander(f"{medals[i - 1]} #{i} {r['name']} — Match {r['match']}%"):
                st.write("**ฟังก์ชันที่ต้องการ:** "
                         + ", ".join(fac["functions"]) + f" (scope: {fac['scope']})")
                st.write("**เงื่อนไขความชอบ:** "
                         + "; ".join(f"{c['cat']} ≥ {c['min']}" for c in fac["conditions"]))

        st.subheader("คณะแนะนำ 10 อันดับแรก")
        render_rank_table(top10)
    else:
        st.warning("ไม่พบคณะที่ตรงกับระดับเงินทุนที่เลือก")

    if st.button("เริ่มใหม่ทั้งหมด"):
        for k in list(st.session_state.keys()):
            if k not in ("show_history",):
                del st.session_state[k]
        goto("welcome")


def name_suffix():
    n = st.session_state.get("name")
    return f" {n}" if n else ""


def render_rank_table(rows):
    """ตารางแนะนำ 10 อันดับ — เน้นแถวอันดับ 1-3 ให้เด่นกว่าอันดับที่เหลือ"""
    match_header = (
        'Match %<span class="column-info" title="เมื่อ Match % เท่ากัน '
        'ระบบเรียงต่อด้วยคะแนนจัดอันดับนี้ (ไม่ปัดเศษ) แล้วจึงเรียงตามชื่อคณะ '
        'ก-ฮ เป็นลำดับสุดท้าย" aria-label="คำอธิบายการจัดอันดับ">ⓘ</span>'
    )
    head_cols = ["อันดับ", "คณะ/สาขา", match_header, "MBTI Score", "Subj Score"]
    head = "".join(f"<th>{c}</th>" for c in head_cols)
    body = []
    for i, r in enumerate(rows):
        cls = ("rank1 top" if i == 0 else "rank2 top" if i == 1
               else "rank3 top" if i == 2 else "")
        badge_cls = f"b{i + 1}" if i < 3 else "bn"
        pct = min(max(r["match"], 0), 100)
        sort_score_note = (
            f'<div class="sort-score-note">คะแนนจัดอันดับ: '
            f'{round(r["sortScore"], 1)}</div>'
        )
        cells = [
            f'<td><span class="badge {badge_cls}">{i + 1}</span></td>',
            f'<td><b>{html.escape(r["name"])}</b></td>',
            '<td style="min-width:110px">'
            f'<div style="font-weight:700">{r["match"]}%</div>'
            f'{sort_score_note}'
            f'<div class="matchbar"><i style="width:{pct}%"></i></div></td>',
            f'<td>{r["mbtiScore"]}</td>',
            f'<td>{r["subjScore"]}</td>',
        ]
        body.append(f'<tr class="{cls}">' + "".join(cells) + "</tr>")
    st.markdown(
        '<div class="rank-table-wrap"><table class="rank-table">'
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody>"
        "</table></div>",
        unsafe_allow_html=True,
    )


def parse_top_faculties(text):
    """Parse '1. ชื่อคณะ (xx.x%) | 2. ...' จากคอลัมน์ top_faculties -> [(name, match)]"""
    out = []
    if isinstance(text, str) and text.strip():
        for part in text.split("|"):
            m = re.match(r"\s*\d+\.\s*(.+?)\s*\(\s*([\d.]+)\s*%\s*\)", part)
            if m:
                out.append((m.group(1), float(m.group(2))))
    return out


def render_history():
    df = load_history()
    st.divider()
    st.subheader("ประวัติผลลัพธ์ที่บันทึกไว้ (results.db)")
    if df.empty:
        st.info("ยังไม่มีข้อมูลที่บันทึกไว้")
        return

    # สรุปข้อมูลจากทุกเรคคอร์ด เป็นแผนภูมิวงกลม 2 อัน (แสดงก่อนตาราง)
    mbti_counts = df["mbti_type"].value_counts()
    fac_counts = {}
    for _, r in df.iterrows():
        tops = parse_top_faculties(r["top_faculties"])
        if tops:
            fac_counts[tops[0][0]] = fac_counts.get(tops[0][0], 0) + 1

    fig_m = px.pie(names=list(mbti_counts.index), values=mbti_counts.values,
                   color_discrete_sequence=PIE_COLORS)
    _style_pie(fig_m, "สรุปผล MBTI ทั้งหมด")

    if not fac_counts:
        st.plotly_chart(fig_m, use_container_width=True)
    else:
        fig_f = px.pie(names=list(fac_counts.keys()),
                       values=list(fac_counts.values()),
                       color_discrete_sequence=PIE_COLORS)
        _style_pie(fig_f, "สรุปคณะที่ได้ทั้งหมด", legend_size=9)
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(fig_m, use_container_width=True)
        with c2:
            st.plotly_chart(fig_f, use_container_width=True)

    # ตารางภาพรวมทุกเรคคอร์ด
    overview = []
    for _, r in df.iterrows():
        tops = parse_top_faculties(r["top_faculties"])
        overview.append({
            "_id": r["id"],
            "ชื่อ": r["name"],
            "วันเวลา": r["timestamp"],
            "MBTI ที่ได้": r["mbti_type"],
            "คณะอันดับ 1": tops[0][0] if tops else "-",
            "งบที่เลือก": r["budget"],
        })
    st.dataframe(pd.DataFrame(overview).drop(columns="_id"),
                 hide_index=True, use_container_width=True)

    # ลบรายการที่เลือก (map label -> id เพื่อไม่แยกด้วย split)
    label_by_id = {f"#{o['_id']} {o['ชื่อ']} — {o['วันเวลา']}": o["_id"]
                   for o in overview}
    to_delete = st.multiselect("เลือกรายการที่ต้องการลบ", list(label_by_id.keys()))
    if to_delete and st.button("ลบรายการที่เลือก", type="primary"):
        for lab in to_delete:
            delete_result(label_by_id[lab])
        st.success(f"ลบแล้ว {len(to_delete)} รายการ")
        st.rerun()


# ---------------------------------------------------------------- main
def main():
    st.set_page_config(page_title="วางแผนการศึกษาต่อในระดับอุดมศึกษาของนักเรียนโรงเรียนสองพิทยาคม", page_icon="🎓", layout="wide")
    inject_css()
    init_session()

    fn_questions = parse_function_questions()
    interest_file = DATA_DIR / "ความชอบ2.txt"
    survey = parse_interest_questions(interest_file.stat().st_mtime_ns)

    with st.sidebar:
        st.markdown(
            '<div class="sidebar-title">วางแผนการศึกษาต่อ<br>'
            'ระดับอุดมศึกษาของนักเรียน<br>'
            'โรงเรียนสองพิทยาคม</div>',
            unsafe_allow_html=True,
        )
        done_flags = [
            ("1. เริ่มต้น", bool(st.session_state["name"])),
            ("2. ผล MBTI", st.session_state["function_strengths"] is not None),
            ("3. ความชอบ", st.session_state["cat_scores"] is not None),
            ("4. งบประมาณ", st.session_state["budget_tier"] is not None),
            ("5. ผลลัพธ์", st.session_state["step"] == "results"),
        ]
        rows = "".join(
            '<div class="sstep{cls}"><span class="dot{dcls}">{mark}</span>'
            "{label}</div>".format(
                cls=" done" if ok else "",
                dcls=" done" if ok else "",
                mark="✓" if ok else i + 1,
                label=label,
            )
            for i, (label, ok) in enumerate(done_flags)
        )
        st.markdown(f'<div class="side-steps">{rows}</div>',
                    unsafe_allow_html=True)
        if st.session_state["name"]:
            st.write(f"ผู้ใช้: **{st.session_state['name']}**")
        if st.session_state["admin_authenticated"]:
            st.checkbox("ประวัติผลลัพธ์", key="show_history")
            st.button("ออกจากโหมดผู้ดูแล", on_click=logout_admin)
        elif admin_password():
            with st.expander("สำหรับผู้ดูแล"):
                password = st.text_input("รหัสผ่านผู้ดูแล", type="password")
                if st.button("เข้าสู่ระบบผู้ดูแล"):
                    if is_admin_password(password):
                        st.session_state["admin_authenticated"] = True
                        st.rerun()
                    else:
                        st.error("รหัสผ่านไม่ถูกต้อง")

    if (st.session_state.get("show_history")
            and st.session_state.get("admin_authenticated")):
        render_history()

    step = st.session_state["step"]
    if step == "welcome":
        page_welcome()
    elif step == "mbti_choice":
        page_mbti_choice()
    elif step == "mbti_select":
        page_mbti_select()
    elif step == "function_test":
        page_function_test(fn_questions)
    elif step == "mbti_summary":
        page_mbti_summary()
    elif step == "interest_survey":
        page_interest_survey(survey)
    elif step == "budget":
        page_budget()
    elif step == "results":
        page_results()


if __name__ == "__main__":
    main()
