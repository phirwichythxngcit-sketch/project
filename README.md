# แบบสอบถามแนะแนวคณะ (Streamlit)

เว็บแอปช่วยแนะแนวคณะ/สาขา โดยรวม 3 ชิ้นประกอบ: MBTI (Cognitive Functions), ความสนใจ–ความถนัด 5 หมวด, และงบประมาณการศึกษา แล้วจัดอันดับคณะที่ Match % สูงสุดให้อัตโนมัติ

## ลำดับหน้า (state machine)

```
welcome → mbti_choice ─┬→ mbti_select ────┐
                       └→ function_test ──┴→ mbti_summary → interest_survey → budget → results
```

- **mbti_choice** — เลือกระหว่าง "รู้ MBTI อยู่แล้ว (เลือกเอง)" กับ "ทำแบบทดสอบ Cognitive Functions (80 ข้อ)"
- **mbti_select** — เลือก 1 จาก 16 type; คำนวณ functionStrength จาก function stack: `[100, 70, 35, 10]` (Dom→Aux→Tert→Inf) ฟังก์ชันนอก stack = 0
- **function_test** — 8 หน้าย่อย (ฟังก์ชันละ 10 ข้อ); raw 10–50 → normalize `(raw−10)/40×100`
- **mbti_summary** — กรณีทำแบบทดสอบจะหา "type ใกล้เคียงสุด" ด้วย weighted stack similarity
  (เรียง 8 ฟังก์ชันจากมากไปน้อย เทียบ stack 16 type น้ำหนัก `[0.4, 0.3, 0.2, 0.1]` normalize ด้วย `MAX_SCORE = 0.30`) + pie chart 8 ฟังก์ชัน
- **interest_survey** — 5 หมวด × 20 ข้อ (1–5); คะแนนหมวด = ผลรวม (20–100, max = 100)
- **budget** — B1 ≤15,000 / B2 15,001–40,000 / B3 ≥40,001 บาท/เทอม
- **results** — pie chart 3 อัน (Cognitive Functions / 5 หมวด / Top-5 คณะ), ตารางแนะนำ 10 อันดับ,
  ปุ่มบันทึกลง SQLite (`results.db`), sidebar toggle "ประวัติผลลัพธ์"

## สูตร Match %

```
mbtiScore: scope="D/A"      → max(strength ของฟังก์ชันที่คณะต้องการ)
           scope="Dominant" → ค่า max นั้น ×1.0 ถ้าฟังก์ชันสูงสุดของผู้ใช้อยู่ในลิสต์จริง ไม่งั้น ×0.5
           scope="Mixed"    → max(สองวิธีข้างบน)
subjScore: min ของ min(userScore/เกณฑ์×100, 100) ทุกเงื่อนไข
Match%   : 0.3×mbtiScore + 0.7×subjScore
```

ทั้งสองเส้นทาง MBTI จบลงด้วยโครงสร้างเดียวกัน — dict `functionStrength` 8 ฟังก์ชัน (0–100) — ทำให้โค้ดคำนวณ Match % เป็นชุดเดียว ไม่ต้องแยก branch

## โครงสร้างไฟล์

```
project/
├── app.py                  # แอปหลักทั้งหมด
├── data/
│   ├── MBTI_2.txt          # 80 ข้อ Cognitive Functions
│   ├── ความชอบ2.txt        # 100 ข้อความสนใจ 5 หมวด
│   ├── การเงิน.txt         # เกณฑ์งบ 3 ระดับ
│   ├── faculty_database_v2.json   # ฐานข้อมูลคณะ + budgetTiers
│   └── mbti_type_descriptions.json # 16 type: title/desc/function stack
├── results.db              # auto-created (gitignore แล้ว)
└── requirements.txt        # streamlit, pandas, plotly
```

## รันในเครื่อง

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy บน Streamlit Cloud

1. Push โปรเจกต์ขึ้น GitHub (repo public, `.gitignore` กันไฟล์ `*.db` ไว้แล้ว)
2. ไปที่ [share.streamlit.io](https://share.streamlit.io) → **New app**
3. เลือก repo / branch → Main file path: `app.py` → **Deploy**

> ⚠️ Streamlit Cloud เป็น ephemeral storage — ไฟล์ `results.db` จะหายเมื่อแอป redeploy
> ถ้าต้องการเก็บประวัติถาวร แนะนำเปลี่ยนไปใช้ Google Sheets / ฐานข้อมูลภายนอก

## หมายเหตุ

แบบทดสอบทั้งหมดเป็นเครื่องมือสำรวจตนเองเพื่อการแนะแนว ไม่ใช่ผลวินิจฉัยทางจิตวิทยาที่ผ่านการตรวจสอบ psychometric validation
