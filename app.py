# -*- coding: utf-8 -*-
"""แบบสอบถามแนะแนวคณะ — Streamlit App

ลำดับหน้า (state machine ผ่าน st.session_state["step"]):
welcome -> mbti_choice -> (mbti_select | function_test) -> mbti_summary
        -> interest_survey -> budget -> results
"""

import hmac
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

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
SCALE_1_5 = ["1 — ไม่เห็นด้วยอย่างยิ่ง", "2 — ไม่เห็นด้วย", "3 — เฉยๆ / ไม่แน่ใจ",
             "4 — เห็นด้วย", "5 — เห็นด้วยอย่างยิ่ง"]
DISCLAIMER = ("นี่คือผลโดยประมาณเพื่อการสำรวจตนเอง "
              "ไม่ใช่ผลวินิจฉัยที่ตายตัว")
EPHEMERAL_WARNING = (
    "**คำเตือน:** ถ้า deploy บน Streamlit Cloud ข้อมูลใน results.db จะหายเมื่อแอปถูก redeploy "
    "(ephemeral storage) หากต้องการเก็บประวัติถาวร แนะนำให้ใช้ Google Sheets หรือฐานข้อมูลภายนอกแทน")


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
def parse_interest_questions():
    """Parse ความชอบ2.txt -> {cat: {"title": ..., "questions": [20 items]}}"""
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


# ---------------------------------------------------------------- scoring core
def strengths_from_type(type_code):
    """เส้นทาง 'เลือกเอง': stack Dom->Aux->Tert->Inf => [100,70,35,10], นอก stack = 0"""
    stack = MBTI_TYPES[type_code]["stack"]
    s = {f: 0 for f in FN_ORDER}
    for f, v in zip(stack, SELF_STRENGTH):
        s[f] = float(v)
    return s


def strengths_from_raw(raw_scores):
    """เส้นทาง 'ทำแบบทดสอบ': normalize (raw-10)/40*100"""
    return {f: round((raw_scores[f] - 10) / 40 * 100, 1) for f in FN_ORDER}


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
    ratios = [min(cat_scores[c["cat"]] / c["min"] * 100, 100)
              for c in fac["conditions"]]
    return min(ratios)


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


def rank_faculties(strengths, cat_scores):
    rows = []
    for fac in FACULTIES:
        ms = mbti_score(fac, strengths)
        ss = subj_score(fac, cat_scores)
        match = round(0.3 * ms + 0.7 * ss, 1)
        rows.append({
            "name": fac["name"],
            "group": fac["group"],
            "mbtiScore": round(ms, 1),
            "subjScore": round(ss, 1),
            "match": match,
            "reason": build_reason(fac, strengths, cat_scores),
            "uni": fac["budget"].get(st.session_state.get("budget_tier"), "-"),
            "_fac": fac,
        })
    rows.sort(key=lambda r: (-r["match"], -r["subjScore"], r["name"]))
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


def load_history(db_path=DB_PATH):
    if not Path(db_path).exists():
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql("SELECT * FROM results ORDER BY id DESC", conn)
    finally:
        conn.close()
    return df


# ---------------------------------------------------------------- chart helpers
def pie_functions(strengths):
    labels = [f"{f} — {FN_TH[f]}" for f in FN_ORDER]
    fig = px.pie(names=labels, values=[strengths[f] for f in FN_ORDER],
                 hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2)
    fig.update_layout(title_text="สัดส่วนการใช้ Cognitive Functions ของคุณ",
                      title_x=0.5, legend_font_size=11)
    return fig


def pie_categories(cat_scores):
    labels = [f"{c} — {CAT_TH[c]}" for c in CAT_ORDER]
    fig = px.pie(names=labels, values=[cat_scores[c] for c in CAT_ORDER],
                 hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
    fig.update_layout(title_text="ความถนัด 5 หมวด (M, S, L, H, A)", title_x=0.5,
                      legend_font_size=11)
    return fig


def pie_top_faculties(rows):
    top = rows[:5]
    fig = px.pie(names=[f"{r['name']} ({r['match']}%)" for r in top],
                 values=[r["match"] for r in top], hole=0.4,
                 color_discrete_sequence=px.colors.qualitative.Bold)
    fig.update_layout(title_text="5 คณะที่ Match % สูงสุด", title_x=0.5,
                      legend_font_size=11)
    return fig


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
        "show_calc": False,
        "admin_authenticated": False,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def goto(step):
    st.session_state["step"] = step
    st.rerun()


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


def is_admin_password(password):
    """Check an administrator password stored only in Streamlit Secrets."""
    expected = st.secrets.get("ADMIN_PASSWORD")
    return bool(expected) and hmac.compare_digest(password, expected)


# ---------------------------------------------------------------- pages
def page_welcome():
    st.title("แบบสอบถามแนะแนวคณะ")
    st.markdown(
        """
        แอปนี้ช่วยให้คุณรู้จักตัวเองมากขึ้น แล้วจับคู่กับ **คณะ/สาขาที่เหมาะกับคุณ**
        ผ่าน 3 ชิ้นประกอบ:

        1. **Cognitive Functions (MBTI)** — เลือก type ที่รู้แล้ว หรือทำแบบทดสอบ 80 ข้อ
        2. **ความสนใจและความถนัด** — แบบสำรวจ 5 หมวด (100 ข้อ แบ่ง 5 หน้า)
        3. **งบประมาณการศึกษา** — เพื่อแนะนำมหาวิทยาลัยที่เหมาะกับกำลังจ่าย

        ใช้เวลารวมประมาณ 15–25 นาที ไม่มีคำตอบถูกหรือผิด ตอบตามความจริงใจของตัวเองได้เลย
        """
    )
    name = st.text_input("ชื่อ / ชื่อเล่น", value=st.session_state["name"])
    if st.button("เริ่ม", type="primary", disabled=(not name.strip())):
        st.session_state["name"] = name.strip()
        goto("mbti_choice")


def page_mbti_choice():
    st.header("ผล MBTI ของคุณมาจากไหน?")
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
    st.progress(done / 8, text=f"ความคืบหน้า {done}/8 ฟังก์ชัน")
    st.header(f"ฟังก์ชัน {func} — {FN_TH[func]}")
    st.caption(f"หน้า {idx + 1} / 8 · ข้อ {idx * 10 + 1}–{idx * 10 + 10}")

    unanswered = []
    for i, q in enumerate(fn_questions[func]):
        key = f"ans_{func}_{i}"
        val = st.radio(f"{idx * 10 + i + 1}. {q}", SCALE_1_5, index=None,
                       key=key, horizontal=False)
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
                raw = sum(int(st.session_state[f"ans_{func}_{i}"][0]) for i in range(10))
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

    st.markdown(info["desc"])

    strengths = st.session_state["function_strengths"]
    top4 = sorted(FN_ORDER, key=lambda f: strengths[f], reverse=True)[:4]
    st.info("Function Stack ของคุณ: "
            + " → ".join(f"{f} ({strengths[f]:.0f}%)" for f in top4))

    st.plotly_chart(pie_functions(strengths))

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
        if st.button("ทำแบบสำรวจความถนัดต่อ →", type="primary"):
            st.session_state["interest_index"] = 0
            goto("interest_survey")


def page_interest_survey(survey):
    idx = st.session_state["interest_index"]
    cat = CAT_ORDER[idx]
    block = survey[cat]
    st.progress(len(st.session_state["interest_answers"]) / 5,
                text=f"หมวดที่ {len(st.session_state['interest_answers'])}/5 เสร็จสิ้น")
    st.header(f"หมวด {idx + 1}/5: {block['title']}")
    st.caption("ให้คะแนนแต่ละข้อ 1–5 (1 = ไม่ใช่เลย, 5 = ใช่มากที่สุด)")

    answers = st.session_state["interest_answers"].get(cat, {})
    unanswered = []
    for i, q in enumerate(block["questions"]):
        key = f"in_{cat}_{i}"
        default = saved_answer_at(answers, i)
        d_idx = default - 1 if isinstance(default, int) else None
        val = st.radio(f"{i + 1}. {q}", SCALE_1_5, index=d_idx, key=key)
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
                vals = [int(st.session_state[f"in_{cat}_{i}"][0]) for i in range(20)]
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
            st.session_state["budget_tier"] = tier_keys[opts.index(sel)]
            goto("results")


def page_results():
    strengths = st.session_state["function_strengths"]
    cat_scores = st.session_state["cat_scores"]
    budget = st.session_state.get("budget_tier")
    rows = rank_faculties(strengths, cat_scores)
    tier_desc = BUDGET_TIERS[budget]["label"]

    st.header(f"ผลลัพธ์ของ{name_suffix()}")
    st.success(f"MBTI: **{st.session_state['derived_type']}** · "
               f"งบ: **{budget} ({tier_desc})**")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.plotly_chart(pie_functions(strengths))
    with col2:
        st.plotly_chart(pie_categories(cat_scores))
    with col3:
        st.plotly_chart(pie_top_faculties(rows))

    st.subheader("คณะแนะนำ 10 อันดับแรก")
    table = pd.DataFrame([
        {"อันดับ": i + 1, "คณะ/สาขา": r["name"], "Match %": r["match"],
         "MBTI Score": r["mbtiScore"], "Subj Score": r["subjScore"],
         "เหตุผล": r["reason"], f"ตัวอย่างมหาวิทยาลัย ({budget})": r["uni"]}
        for i, r in enumerate(rows[:10])
    ])
    st.table(table)

    for i, r in enumerate(rows[:3], start=1):
        fac = r["_fac"]
        with st.expander(f"#{i} {r['name']} — Match {r['match']}%"):
            st.write("**ฟังก์ชันที่ต้องการ:** "
                     + ", ".join(fac["functions"]) + f" (scope: {fac['scope']})")
            st.write("**เงื่อนไขความถนัด:** "
                     + "; ".join(f"{c['cat']} ≥ {c['min']}" for c in fac["conditions"]))
            for k in tier_keys_all():
                b = fac["budget"].get(k, "-")
                t = BUDGET_TIERS[k]
                st.write(f"- **{k} ({t['label']})**: {b}")

    st.divider()
    st.subheader("บันทึกผลลัพธ์")
    st.caption(EPHEMERAL_WARNING)
    if st.session_state.get("saved_id") is not None:
        st.info(f"บันทึกเรียบร้อยแล้ว (record id = {st.session_state['saved_id']})")
    else:
        if st.button("บันทึกผลลัพธ์ลง SQLite (results.db)", type="primary"):
            payload = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "name": st.session_state["name"],
                "mbti_method": "เลือกเอง" if st.session_state["mbti_route"] == "self"
                               else "ทำแบบทดสอบ",
                "mbti_type": st.session_state["derived_type"],
                **{f: round(strengths[f], 1) for f in FN_ORDER},
                **{c: int(cat_scores[c]) for c in CAT_ORDER},
                "budget": budget,
                "top_faculties": " | ".join(
                    f"{i}. {r['name']} ({r['match']}%)" for i, r in enumerate(rows[:3], 1)),
            }
            try:
                st.session_state["saved_id"] = save_result(payload)
                st.success(f"บันทึกสำเร็จ (record id = {st.session_state['saved_id']})")
            except Exception as e:
                st.error(f"บันทึกไม่สำเร็จ: {e}")

    if st.button("เริ่มใหม่ทั้งหมด"):
        for k in list(st.session_state.keys()):
            if k not in ("show_history",):
                del st.session_state[k]
        goto("welcome")


def tier_keys_all():
    return ["B1", "B2", "B3"]


def name_suffix():
    n = st.session_state.get("name")
    return f" {n}" if n else ""


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
        st.warning(EPHEMERAL_WARNING)
        return

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
    st.dataframe(pd.DataFrame(overview).drop(columns="_id"))

    labels = [f"{o['ชื่อ']} — {o['วันเวลา']}" for o in overview]
    sel = st.selectbox("เลือกดูรายละเอียดรายบุคคล (แผนภูมิ 3 แผนภูมิ)", labels)
    if sel is None:
        return
    rec = df.iloc[labels.index(sel)]

    tops = parse_top_faculties(rec["top_faculties"])
    func_scores = {f: float(rec[f]) for f in FN_ORDER}
    cat_scores = {c: int(rec[c]) for c in CAT_ORDER}
    top1_name = tops[0][0] if tops else "-"

    st.markdown(f"**{rec['name']}** · MBTI ใกล้เคียงที่สุด: "
                f"**{rec['mbti_type']}** · คณะอันดับ 1: **{top1_name}**")

    fig1 = pie_functions(func_scores)
    fig1.update_layout(title_text="สัดส่วนการใช้ Cognitive Functions")
    fig2 = pie_categories(cat_scores)
    fig2.update_layout(title_text="สัดส่วนความถนัด 5 หมวดวิชา")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.plotly_chart(fig1)
    with c2:
        st.plotly_chart(fig2)
    with c3:
        if tops:
            fig3 = pie_top_faculties([{"name": n, "match": v} for n, v in tops])
            fig3.update_layout(title_text="คณะที่เหมาะกับคุณ",
                               legend_font_size=9)
            st.plotly_chart(fig3)
        else:
            st.info("ไม่มีข้อมูลคณะที่บันทึกไว้ในแถวนี้")

    st.warning(EPHEMERAL_WARNING)


# ---------------------------------------------------------------- calc explainer
DEMO_STRENGTHS = {"Ti": 65.0, "Te": 40.0, "Fe": 20.0, "Fi": 30.0,
                  "Se": 15.0, "Si": 25.0, "Ne": 45.0, "Ni": 55.0}
DEMO_CATS = {"M": 70, "S": 50, "L": 35, "H": 45, "A": 30}


def bool_condition_str(fac):
    fn_clause = " ∨ ".join(f"{f}∈D/A" for f in fac["functions"])
    cond_clause = " ∧ ".join(f"{c['cat']} ≥ {c['min']}%" for c in fac["conditions"])
    return " ∧ ".join([f"( {fn_clause} )", cond_clause])


def render_calc_explanation():
    st.divider()
    st.header("วิธีคำนวณ Match %")

    # ---------- ส่วนที่ 1: ทฤษฎี ----------
    st.subheader("ส่วนที่ 1 · ทฤษฎี: จาก Boolean สู่ Fuzzy")
    st.markdown(
        "เงื่อนไขรับเข้าของแต่ละคณะถูกเขียนครั้งแรกเป็น **ตรรกศาสตร์เชิงประพจน์แบบ Boolean** "
        "(แต่ละเงื่อนไข \"ผ่าน/ไม่ผ่าน\" = 1/0) จากนั้นระบบจึงแปลงเป็น **Fuzzy Logic** "
        "เพื่อให้ได้ % ความเข้ากันได้แบบ **ต่อเนื่อง 0–100** แทนที่จะเหลือแค่สองค่า"
    )
    st.markdown(
        """
| ตัวเชื่อม Boolean | สูตร Fuzzy | เหตุผล |
|---|---|---|
| A ∧ B (AND) | `min(A, B)` | AND แข็งแรงเท่ากับจุดอ่อนที่สุดในกลุ่ม |
| A ∨ B (OR) | `max(A, B)` | OR แค่ต้องมีตัวที่ดีที่สุดในกลุ่มพอ |
"""
    )
    st.latex(r"A \wedge B \;\longrightarrow\; \min(A,\ B)"
             r"\qquad A \vee B \;\longrightarrow\; \max(A,\ B)")

    # ---------- ส่วนที่ 2: สาธิตด้วยค่าจริง ----------
    st.subheader("ส่วนที่ 2 · สาธิต step-by-step ด้วยค่าของคุณ")
    strengths = st.session_state.get("function_strengths")
    cats = st.session_state.get("cat_scores")
    if strengths and cats:
        top = rank_faculties(strengths, cats)[0]
        fac = top["_fac"]
        st.success(f"ใช้ค่าจริงของคุณ — คณะที่ Match % สูงสุด: "
                   f"**{top['name']} ({top['match']}%)**")
    else:
        strengths, cats = DEMO_STRENGTHS, DEMO_CATS
        fac = next(f for f in FACULTIES if f["name"] == "วิทยาการคอมพิวเตอร์/IT")
        st.warning("ยังไม่มีผลทดสอบในเซสชันนี้ — ใช้ **ตัวเลขตัวอย่าง** แทน "
                   "(Ti 65%, Te 40%, M 70, S 50)")

    scope = fac.get("scope", "D/A")

    st.markdown("**ขั้นที่ 1 — เขียนเงื่อนไข Boolean ดั้งเดิมของคณะ**")
    st.code(bool_condition_str(fac), language=None)
    if scope == "Dominant":
        st.caption("โน้ต: scope = Dominant → ฟังก์ชันสูงสุดของผู้ใช้ต้องอยู่ในลิสต์ของคณะ "
                   "ไม่เช่นนั้นคะแนน × 0.5")
    elif scope == "Mixed":
        st.caption("โน้ต: scope = Mixed → เอาค่ามากกว่าระหว่างวิธี D/A (max) กับวิธี Dominant")

    st.markdown("**ขั้นที่ 2 — แทนค่าจริงของคุณลงในตัวแปร**")
    lines = [f"{f} ของคุณ = {strengths[f]:g}%" for f in fac["functions"]]
    lines += [f"{c['cat']} ของคุณ = {int(cats[c['cat']])} (เกณฑ์ ≥ {c['min']})"
              for c in fac["conditions"]]
    st.code("\n".join(lines), language=None)

    st.markdown("**ขั้นที่ 3 — mbtiScore: ฝั่งฟังก์ชัน (OR → max)**")
    ms = round(mbti_score(fac, strengths), 1)
    vals = ",\\ ".join(f"{strengths[f]:g}" for f in fac["functions"])
    st.latex(r"\text{mbtiScore} = \max(\," + vals + r"\,) = " + f"{ms:g}")
    st.caption("ใช้ max เพราะเงื่อนไขฟังก์ชันเป็น OR (∨): "
               + " หรือ ".join(fac["functions"])
               + " — ตัวใดตัวหนึ่งแข็งแรงก็เพียงพอ")
    if scope != "D/A":
        dom_f = max(FN_ORDER, key=lambda f: strengths[f])
        factor = 1.0 if dom_f in fac["functions"] else 0.5
        pos = "อยู่" if dom_f in fac["functions"] else "ไม่อยู่"
        st.caption(f"[scope {scope}] ฟังก์ชันสูงสุดของคุณคือ {dom_f} → {pos}ในลิสต์ของคณะ "
                   f"⇒ คูณ {factor:g}")

    st.markdown("**ขั้นที่ 4 — subjScore: ฝั่งความถนัด (AND → min)**")
    ss = round(subj_score(fac, cats), 1)
    argstr = ",\\ ".join(f"{int(cats[c['cat']])}/{c['min']}\\times 100"
                         for c in fac["conditions"])
    st.latex(r"\text{subjScore} = \min(\," + argstr + r"\,) = " + f"{ss:g}")
    details = []
    for c in fac["conditions"]:
        raw = int(cats[c["cat"]]) / c["min"] * 100
        capped = min(raw, 100)
        details.append(f"{c['cat']}: {int(cats[c['cat']])}/{c['min']} × 100 = "
                       f"{raw:.1f} → ตัดที่ 100 = {capped:.1f}")
    st.code("\n".join(details), language=None)
    st.caption("ใช้ min เพราะเงื่อนไขความถนัดเชื่อมด้วย AND (∧): "
               "หมวดที่อ่อนที่สุดกำหนดคะแนนรวม")

    st.markdown("**ขั้นที่ 5 — สมการสุดท้าย**")
    match_val = round(0.3 * ms + 0.7 * ss, 1)
    st.latex(r"\text{Match\%} = 0.3\times\text{mbtiScore}"
             r" + 0.7\times\text{subjScore}")
    st.latex(r"\text{Match\%} = 0.3\times" + f"{ms:g}" +
             r" + 0.7\times" + f"{ss:g} = " + f"{match_val:g}")


# ---------------------------------------------------------------- main
def main():
    st.set_page_config(page_title="แนะแนวคณะ", layout="wide")
    init_session()

    fn_questions = parse_function_questions()
    survey = parse_interest_questions()

    with st.sidebar:
        st.header("แบบสอบถามแนะแนวคณะ")
        done_flags = [
            ("1. เริ่มต้น", bool(st.session_state["name"])),
            ("2. ผล MBTI", st.session_state["function_strengths"] is not None),
            ("3. ความถนัด", st.session_state["cat_scores"] is not None),
            ("4. งบประมาณ", st.session_state["budget_tier"] is not None),
            ("5. ผลลัพธ์", st.session_state["step"] == "results"),
        ]
        for label, ok in done_flags:
            st.write(("✔ " if ok else "○ ") + label)
        if st.session_state["name"]:
            st.write(f"ผู้ใช้: **{st.session_state['name']}**")
        st.checkbox("วิธีคำนวณ", key="show_calc")
        if st.session_state["admin_authenticated"]:
            st.checkbox("ประวัติผลลัพธ์", key="show_history")
            if st.button("ออกจากโหมดผู้ดูแล"):
                st.session_state["admin_authenticated"] = False
                st.session_state["show_history"] = False
                st.rerun()
        elif st.secrets.get("ADMIN_PASSWORD"):
            with st.expander("สำหรับผู้ดูแล"):
                password = st.text_input("รหัสผ่านผู้ดูแล", type="password")
                if st.button("เข้าสู่ระบบผู้ดูแล"):
                    if is_admin_password(password):
                        st.session_state["admin_authenticated"] = True
                        st.rerun()
                    else:
                        st.error("รหัสผ่านไม่ถูกต้อง")

    if st.session_state.get("show_calc"):
        render_calc_explanation()

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
