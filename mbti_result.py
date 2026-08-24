# -*- coding: utf-8 -*-
"""หน้าแสดงผลลัพธ์ MBTI แบบละเอียด

รับค่า type (เช่น "INTJ") จากแบบทดสอบ แล้วแสดง:
  1) ชื่อ type + nickname + คำอธิบาย
  2) Function stack 4 ตำแหน่ง เป็นการ์ดสี (Dominant -> Inferior)
  3) จุดแข็ง / จุดที่ควรพัฒนา แบบสองคอลัมน์

ธีมสีแยกตามกลุ่ม: Analysts=ม่วง, Diplomats=เขียว,
Sentinels=น้ำเงิน, Explorers=ส้ม (ดูที่ mbti_data.py)
"""

import streamlit as st

from mbti_data import FN_FULL, GROUPS, MBTI_DATA, STACK_ROLES, TYPE_GROUP


def _rgba(hex_color: str, alpha: float) -> str:
    """แปลงสี hex (#RRGGBB) เป็น rgba() เพื่อทำพื้นหลังโปร่งแสง"""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def _render_header(t: str, info: dict, group: dict, color: str) -> None:
    """หัวหน้า: แถบสีกลุ่ม + ชื่อ type + nickname + คำอธิบาย"""
    st.markdown(
        f"""
        <div style="background:{_rgba(color, 0.14)};
                    border:1px solid {_rgba(color, 0.35)};
                    border-radius:16px; padding:18px 24px;">
            <span style="background:{color}; color:#fff;
                         padding:4px 14px; border-radius:999px;
                         font-size:0.95em; font-weight:600;">กลุ่ม{group['th']}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    # ชื่อ type + nickname
    st.header(f"{t} — {info['nickname']}")
    # คำอธิบาย แสดงเป็นตัวหนาเพื่อให้อ่านชัดขึ้น
    st.markdown(f"**{info['description']}**")


def _render_stack(t: str, color: str) -> None:
    """Function stack 4 ตำแหน่ง เป็นการ์ด 4 ใบ พื้นหลังไล่จากเข้มไปอ่อน"""
    st.subheader("Function Stack (โครงสร้างฟังก์ชันทางความคิด)")
    cols = st.columns(4)
    alphas = [0.32, 0.21, 0.13, 0.07]  # Dominant เข้มสุด -> Inferior อ่อนสุด
    info = MBTI_DATA[t]
    for col, (fn_code, role_en), (role_en_ref, role_th), bg_a in zip(
        cols, info["stack"], STACK_ROLES, alphas
    ):
        fn_full = FN_FULL[fn_code]
        card_html = (
            '<div style="background:%(bg)s; border-left:6px solid %(accent)s; '
            'border-radius:12px; padding:14px 16px; height:100%%;">'
            '<div style="font-size:0.72em; letter-spacing:0.08em; opacity:0.8;">'
            "%(role_en)s · %(role_th)s</div>"
            '<div style="font-size:1.6em; font-weight:700; margin:4px 0;">%(code)s</div>'
            '<div style="font-size:0.9em; font-weight:600;">%(full_en)s</div>'
            '<div style="font-size:0.82em; opacity:0.75; margin-top:2px;">%(full_th)s</div>'
            "</div>"
        ) % {
            "bg": _rgba(color, bg_a),
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
    """จุดแข็ง (ซ้าย) เทียบกับ จุดที่ควรพัฒนา (ขวา)"""
    info = MBTI_DATA[t]
    col_s, col_w = st.columns(2)
    with col_s:
        st.markdown("#### ✅ จุดแข็ง")
        for item in info["strengths"]:
            st.markdown(f"- {item}")
    with col_w:
        st.markdown("#### ⚠️ จุดที่ควรพัฒนา")
        for item in info["weaknesses"]:
            st.markdown(f"- {item}")


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

    group = GROUPS[TYPE_GROUP[t]]
    color = group["color"]

    st.markdown("---")
    _render_header(t, MBTI_DATA[t], group, color)

    st.markdown("---")
    _render_stack(t, color)

    st.markdown("---")
    _render_strengths_weaknesses(t)


if __name__ == "__main__":
    # ตัวอย่างการเรียกใช้แบบ standalone: streamlit run mbti_result.py
    st.set_page_config(page_title="ผลลัพธ์ MBTI", layout="wide")
    result_type = st.session_state.get("mbti_type", "INTJ")
    display_mbti_result(result_type)
