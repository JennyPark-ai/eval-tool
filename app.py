"""
app.py — 팀원 연말 인사 평가 & 100점 총량 환산 도구 (Streamlit)

실행 방법
    pip install -r requirements.txt
    streamlit run app.py
"""

from datetime import date

import pandas as pd
import streamlit as st

from eval_logic import (
    CRITERIA,
    INPUT_COLS,
    MAX_SCORES,
    SCORE_COLS,
    STAR,
    TEAM_SIZE,
    clean_scores,
    compute_results,
    default_members,
    load_from_excel,
    to_excel_bytes,
)

st.set_page_config(page_title="연말 인사 평가", page_icon="⭐", layout="wide")

# ─────────────────────────────────────────────
# 세션 상태 초기화 (새로고침 전까지 입력값 유지)
# ─────────────────────────────────────────────
if "members" not in st.session_state:
    st.session_state.members = default_members()
if "leader" not in st.session_state:
    st.session_state.leader = {"이름": "팀장", "직책": "팀장", "주요 담당 사업": "", "팀장 총평 / 코멘트": ""}
if "editor_ver" not in st.session_state:
    st.session_state.editor_ver = 0  # 파일을 불러오면 표를 새로 그리기 위한 버전 번호

# ─────────────────────────────────────────────
# 사이드바: 승진 추천 기준 / 불러오기 / 평가 기준 안내
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("⭐ 승진 추천 기준")
    top_n = st.number_input("상위 몇 명을 추천할까요?", min_value=0, max_value=TEAM_SIZE, value=1, step=1)
    min_raw = st.slider("최소 원점수 (100점 만점 기준)", 0, 100, 80,
                        help="이 점수 미만이면 상위권이어도 추천하지 않습니다. 0이면 조건 없음.")
    include_leader = st.checkbox("팀장도 추천 대상에 포함", value=False)
    st.caption("상위 N번째와 동점인 사람은 함께 추천됩니다.")

    st.divider()
    st.header("📂 이전 평가 불러오기")
    uploaded = st.file_uploader("이 도구로 내려받은 엑셀 파일", type=["xlsx"])
    if uploaded is not None and st.button("불러오기"):
        try:
            leader, members = load_from_excel(uploaded)
            st.session_state.leader.update({k: str(v) for k, v in leader.items() if k in st.session_state.leader})
            st.session_state.members = members
            st.session_state.editor_ver += 1
            st.success("불러왔습니다.")
            st.rerun()
        except Exception as e:
            st.error(f"불러오지 못했습니다: {e}")

    st.divider()
    st.header("📋 평가 기준 (100점)")
    for name, mx, desc in CRITERIA:
        st.markdown(f"**{name} ({mx}점)** — {desc.split('—')[1].strip()}")

# ─────────────────────────────────────────────
# 본문
# ─────────────────────────────────────────────
st.title(f"{date.today().year}년 연말 인사 평가")
st.caption("팀장 1명 + 팀원 7명 · 팀장 점수는 팀원 7명의 중간값으로 자동 산정 · 8명 합계 100점으로 환산")

# ── 1) 팀장 정보 입력 (점수는 자동) ──
st.subheader("1. 팀장 정보")
c1, c2 = st.columns(2)
lead = st.session_state.leader
lead["이름"] = c1.text_input("이름", lead["이름"])
lead["직책"] = c2.text_input("직책", lead["직책"])
lead["주요 담당 사업"] = st.text_input("주요 담당 사업", lead["주요 담당 사업"])
lead["팀장 총평 / 코멘트"] = st.text_area("팀 운영 총평 (선택)", lead["팀장 총평 / 코멘트"], height=80)

# ── 2) 팀원 7명 입력 표 ──
st.subheader("2. 팀원 평가 입력")
st.caption("표의 셀을 클릭해 직접 수정하세요. 영역별 만점을 넘는 값은 입력할 수 없습니다.")

# 점수 컬럼별 입력 범위 설정
col_config = {
    c: st.column_config.NumberColumn(f"{c} ({MAX_SCORES[c]})", min_value=0, max_value=MAX_SCORES[c], step=0.5)
    for c in SCORE_COLS
}
col_config["주요 담당 사업"] = st.column_config.TextColumn("주요 담당 사업", width="medium")
col_config["팀장 총평 / 코멘트"] = st.column_config.TextColumn("팀장 총평 / 코멘트", width="large")

# st.session_state.members 는 '기준 데이터'로, 불러오기/코멘트 저장 때만 바뀐다.
# 표에서 고친 내용은 data_editor 가 자체적으로 기억하며, 그 결과가 edited 로 돌아온다.
edited = st.data_editor(
    st.session_state.members,
    column_config=col_config,
    num_rows="fixed",          # 팀원 수 7명 고정
    hide_index=True,
    width="stretch",
    key=f"editor_{st.session_state.editor_ver}",
)
members = edited[INPUT_COLS].reset_index(drop=True)  # 현재 화면의 최신 입력값

# 코멘트는 길게 쓰기 편하도록 별도 입력창도 제공
with st.expander("✍️ 팀장 총평 / 코멘트 길게 쓰기"):
    names = members["이름"].tolist()
    who = st.selectbox("팀원 선택", range(len(names)), format_func=lambda i: names[i])
    new_comment = st.text_area(
        f"{names[who]} 총평", members.at[who, "팀장 총평 / 코멘트"], height=160,
        key=f"cmt_{who}_{st.session_state.editor_ver}",
    )
    if st.button("코멘트 저장"):
        members.at[who, "팀장 총평 / 코멘트"] = new_comment
        st.session_state.members = members      # 표 수정분 + 새 코멘트를 기준 데이터로 확정
        st.session_state.editor_ver += 1        # 표를 새 기준 데이터로 다시 그림
        st.rerun()

# ── 3) 계산 및 결과 ──
st.subheader("3. 평가 결과")
_, warns = clean_scores(members)
for w in warns:
    st.warning(w)

result = compute_results(lead, members, top_n, min_raw, include_leader)

# 요약 지표
leader_score = result.loc[result["구분"] == "팀장", "최종 환산 점수"].iloc[0]
m1, m2, m3 = st.columns(3)
m1.metric("8명 합계", f"{result['최종 환산 점수'].sum():.2f}점")
m2.metric("팀장 점수 (팀원 중간값)", f"{leader_score:.2f}점")
m3.metric("승진 추천", f"{(result['승진 추천'] == STAR).sum()}명")


def highlight(row: pd.Series):
    """추천자는 노란색, 팀장은 연녹색 배경."""
    if row["승진 추천"] == STAR:
        return ["background-color: #FFF4CC; font-weight: 600"] * len(row)
    if row["구분"] == "팀장":
        return ["background-color: #EEF3F1"] * len(row)
    return [""] * len(row)


styled = (
    result.style.apply(highlight, axis=1)
    .format({"최종 환산 점수": "{:.2f}", "원점수 합계": "{:g}", **{c: "{:g}" for c in SCORE_COLS}}, na_rep="—")
)
st.dataframe(styled, hide_index=True, width="stretch")
st.caption("팀장 행의 영역별 점수는 '—'로 표시되며, 원점수는 팀원 7명 원점수의 중간값입니다.")

# ── 4) 엑셀 다운로드 ──
st.download_button(
    "📥 엑셀로 다운로드",
    data=to_excel_bytes(result, lead, members),
    file_name=f"{date.today().year}_연말평가_결과.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="primary",
)
