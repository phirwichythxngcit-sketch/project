# -*- coding: utf-8 -*-
"""หน้าแสดงผลลัพธ์ MBTI แบบละเอียด

รับค่า type (เช่น "INTJ") จากแบบทดสอบ แล้วแสดง:
  1) แผงหัวเรื่อง: รหัส type + กลุ่ม + nickname + คำอธิบาย (แผงเดียว)
  2) Function stack 4 ตำแหน่ง เป็นการ์ดไล่ความเข้ม (Dominant -> Inferior)
  3) จุดแข็ง / จุดที่ควรพัฒนา แบบสองคอลัมน์ (panel เขียว/เหลือง)

ธีมสีแยกตามกลุ่ม: Analysts=ม่วง, Diplomats=เขียว,
Sentinels=น้ำเงิน, Explorers=ส้ม (ดูที่ mbti_data.py)

สไตล์การ์ดต่างๆ ใช้ class จาก APP_CSS ใน app.py
(mbti-panel, type-box, group-pill, stack-card, sw-panel)
"""

import streamlit as st

from mbti_data import FN_FULL, GROUPS, MBTI_DATA, STACK_ROLES, TYPE_GROUP


def _rgba(hex_color: str, alpha: float) -> str:
    """แปลงสี hex (#RRGGBB) เป็น rgba() เพื่อทำพื้นหลังโปร่งแสง"""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def _render_header(t: str, info: dict, group: dict, color: str) -> None:
    """แผงหัวเรื่อง: กล่องรหัส type + pill กลุ่ม + nickname + คำอธิบาย"""
    st.markdown(
        f"""
        <div class="mbti-panel" style="background:{_rgba(color, 0.12)};
                     border-left:6px solid {color};">
            <div class="type-box" style="border:1.5px solid {color};">
                <div class="type-code" style="color:{color};">{t}</div>
            </div>
            <div style="flex:1;">
                <span class="group-pill" style="background:{color};">
                    กลุ่ม{group['th']}</span>
                <div style="font-family:'Prompt','Sarabun',sans-serif;
                            font-size:1.35rem;font-weight:700;margin:.45rem 0 .1rem;">
                    {info['nickname']}</div>
                <p style="margin:.15rem 0 0;font-weight:600;line-height:1.55;">
                    {info['description']}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_stack(t: str, color: str) -> None:
    """Function stack 4 ตำแหน่ง — ไล่ความเข้มจาก Dominant ไป Inferior"""
    st.subheader("Function Stack (โครงสร้างฟังก์ชันทางความคิด)")
    cols = st.columns(4)
    alphas = [0.20, 0.14, 0.09, 0.05]  # Dominant เข้มสุด -> Inferior อ่อนสุด
    info = MBTI_DATA[t]
    for col, (fn_code, role_en), (_role_en_ref, role_th), bg_a in zip(
        cols, info["stack"], STACK_ROLES, alphas
    ):
        fn_full = FN_FULL[fn_code]
        card_html = (
            '<div class="stack-card" style="background:%(bg)s;'
            'border-color:%(bd)s;">'
            '<div class="sc-role">%(role_en)s · %(role_th)s</div>'
            '<div class="sc-code" style="color:%(accent)s;">%(code)s</div>'
            '<div class="sc-en">%(full_en)s</div>'
            '<div class="sc-th">%(full_th)s</div>'
            "</div>"
        ) % {
            "bg": _rgba(color, bg_a),
            "bd": _rgba(color, 0.22),
            "accent": color,
            "role_en": role_en,
            "role_th": role_th,
            "code": fn_code,
            "full_en": fn_full["en"],
            "full_th": fn_full["th"],
        }
        with col:
            st.markdown(card_html, unsafe_allow_html=True)


def _render_strengths_weaknesses(t: str) -> None:
    """จุดแข็ง (panel เขียว) เทียบกับ จุดที่ควรพัฒนา (panel เหลืองอบอุ่น)"""
    info = MBTI_DATA[t]
    strengths_li = "".join(f"<li>{item}</li>" for item in info["strengths"])
    weaknesses_li = "".join(f"<li>{item}</li>" for item in info["weaknesses"])
    col_s, col_w = st.columns(2)
    with col_s:
        st.markdown(
            '<div class="sw-panel strengths">'
            "<h4>✅ จุดแข็ง</h4>"
            f"<ul>{strengths_li}</ul></div>",
            unsafe_allow_html=True,
        )
    with col_w:
        st.markdown(
            '<div class="sw-panel grow">'
            "<h4>⚠️ จุดที่ควรพัฒนา</h4>"
            f"<ul>{weaknesses_li}</ul></div>",
            unsafe_allow_html=True,
        )


def display_mbti_result(mbti_type: str) -> None:
    """ฟังก์ชันหลัก: รับ type เช่น "intj" แล้ว normalize และแสดงผลทั้งหน้า

    - normalize ด้วย .strip() + .upper() เพื่อรับ "intj ", "Intj" ฯลฯ
    - ถ้า type ไม่ถูกต้อง แสดง st.error แล้วจบ (ไม่ raise)
    """
    if not isinstance(mbti_type, str) or not mbti_type.strip():
        st.error("ไม่พบประเภท MBTI กรุณาทำแบบทดสอบก่อน")
        return

    t = mbti_type.strip().upper()
    if t not in MBTI_DATA:
        st.error(
            f"ไม่พบข้อมูลสำหรับประเภท '{mbti_type}' "
            "กรุณาระบุรหัส 1 ใน 16 ประเภท เช่น INTJ, ENFP, ISTJ"
        )
        return

    color = GROUPS[TYPE_GROUP[t]]["color"]
    _render_header(t, MBTI_DATA[t], GROUPS[TYPE_GROUP[t]], color)
    st.markdown("")
    _render_stack(t, color)
    st.markdown("")
    _render_strengths_weaknesses(t)


if __name__ == "__main__":
    # ตัวอย่างการเรียกใช้งานแบบ standalone: streamlit run mbti_result.py
    st.set_page_config(page_title="ผลลัพธ์ MBTI", layout="wide")
    result_type = st.session_state.get("mbti_type", "INTJ")
    display_mbti_result(result_type)
