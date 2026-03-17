from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import streamlit as st

from calc import (
    annual_to_monthly_rate,
    months_to_reach_target,
    months_to_years_months,
    nominal_to_real_return_pct,
    required_annual_return_pct_no_saving,
    required_monthly_saving,
    simulate_months_until_target,
    simulate_yearly_table,
)


st.set_page_config(page_title="투자 시나리오 비교", layout="wide", initial_sidebar_state="expanded")
st.markdown(
    """
<style>
  /* Streamlit 상단 배너(Deploy/옵션 등) 숨김 */
  [data-testid="stHeader"] {
    display: none;
  }
  [data-testid="stToolbar"] {
    display: none;
  }
  /* 우하단/기타 배지류(환경에 따라 존재) */
  .viewerBadge_container {
    display: none;
  }

  /* 상단/좌우 여백 최소화 */
  [data-testid="stAppViewContainer"] .block-container {
    padding-top: 0.75rem;
    padding-bottom: 1rem;
  }

  /* 모바일에서는 사이드바 토글(헤더)을 다시 노출 */
  @media (max-width: 768px) {
    [data-testid="stHeader"] {
      display: block;
    }
    [data-testid="stToolbar"] {
      display: block;
    }
    /* 헤더가 컨텐츠 위에 겹치지 않도록 상단 여백 추가 */
    [data-testid="stAppViewContainer"] .block-container {
      padding-top: 4.25rem;
    }
  }
</style>
""",
    unsafe_allow_html=True,
)

NOTES_DIR = Path(__file__).with_name("notes")
NOTES_DIR.mkdir(exist_ok=True)


def sanitize_filename(stem: str) -> str:
    s = stem.strip()
    s = re.sub(r"[\\/:\*\?\"<>\|\n\r\t]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:80] if s else "untitled"

def queue_note_append(entry: str) -> None:
    """
    Streamlit 위젯(key='note_body') 생성 이후에는 st.session_state.note_body를 직접 수정할 수 없어서,
    append 요청을 큐에 넣고 rerun 시점(위젯 생성 전)에서 반영합니다.
    """
    if "pending_note_appends" not in st.session_state or st.session_state.pending_note_appends is None:
        st.session_state.pending_note_appends = []
    st.session_state.pending_note_appends.append(entry)
    st.session_state.note_open = True
    st.rerun()


def build_note_entry_real(
    *,
    title: str,
    seed_eok: float,
    monthly_saving_eok: float | None,
    annual_return_pct: float | None,
    inflation_pct: float,
    return_basis: str,
    horizon_years: int | None,
    horizon_months: int | None,
    result_lines: list[str],
) -> str:
    # 기록은 "구매력(실질/현재가치)" 기준으로 통일
    lines: list[str] = []
    lines.append(f"[{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}] {title}")
    lines.append(f"- 입력(구매력 기준): 시드 {seed_eok:,.4f}억")
    if monthly_saving_eok is not None:
        lines.append(f"- 입력(구매력 기준): 월저축 {monthly_saving_eok:,.4f}억/월 (≈ {monthly_saving_eok*10_000:,.0f}만원/월)")

    if annual_return_pct is not None:
        if return_basis == "nominal":
            real_r = nominal_to_real_return_pct(nominal_return_pct=annual_return_pct, inflation_pct=inflation_pct)
            lines.append(f"- 입력(구매력 기준): 실질 수익률 {real_r:,.3f}% (명목 {annual_return_pct:,.3f}%, 물가 {inflation_pct:,.3f}%)")
        else:
            lines.append(f"- 입력(구매력 기준): 실질 수익률 {annual_return_pct:,.3f}% (물가 {inflation_pct:,.3f}%)")
    else:
        lines.append(f"- 입력: 물가(환산용) {inflation_pct:,.3f}%")

    if horizon_years is not None:
        lines.append(f"- 기간: {horizon_years}년")
    if horizon_months is not None:
        y, m = months_to_years_months(horizon_months)
        lines.append(f"- 기간: {horizon_months}개월 (≈ {y}년 {m}개월)")

    lines.append("- 결과(구매력 기준):")
    lines.extend([f"  - {x}" for x in result_lines])
    return "\n".join(lines)


if "note_open" not in st.session_state:
    st.session_state.note_open = False

if "note_body" not in st.session_state or st.session_state.note_body is None:
    st.session_state.note_body = ""

if "pending_note_appends" in st.session_state and st.session_state.pending_note_appends:
    body = st.session_state.note_body.rstrip()
    for entry in st.session_state.pending_note_appends:
        if body:
            body += "\n\n"
        body += entry.strip() + "\n"
    st.session_state.note_body = body + ("\n" if not body.endswith("\n") else "")
    st.session_state.pending_note_appends = []


if st.session_state.note_open:
    left, right = st.columns([1.55, 1.0], gap="large")
else:
    left = st.container()
    right = None

with st.sidebar:
    st.header("기능 선택")
    mode = st.radio(
        "기능 선택",
        options=[
            "미래 자산(1~N년)",
            "목표자산 → 필요한 월저축",
            "목표자산 → 걸리는 기간",
            "목표자산 → 수익률(월저축 없음)",
        ],
        index=0,
        label_visibility="collapsed",
    )

    st.divider()
    st.header("입력")
    seed_eok = st.number_input("시드 (억)", min_value=0.0, value=1.0, step=0.1)
    annual_return_pct = st.number_input(
        "평균 수익률 (%)",
        value=7.0,
        step=0.1,
        disabled=mode == "목표자산 → 수익률(월저축 없음)",
        help="‘목표자산 → 수익률(월저축 없음)’에서는 역산 결과가 수익률입니다.",
    )
    inflation_pct = st.number_input("인플레이션 (%)", value=2.0, step=0.1)
    return_basis_label = st.radio(
        "수익률 입력 기준",
        options=["실질 수익률(인플레이션 제외)", "명목 수익률(인플레이션 포함)"],
        index=0,  # 기본: 실질
    )

    st.divider()
    monthly_saving_eok = st.number_input(
        "월저축 (억/월)",
        min_value=0.0,
        value=0.05,
        step=0.01,
        disabled=mode in ["목표자산 → 필요한 월저축", "목표자산 → 수익률(월저축 없음)"],
        help="‘목표자산 → 필요한 월저축’/‘목표자산 → 수익률’에서는 입력하지 않습니다(역산 결과가 월저축/수익률).",
    )
    st.caption(f"연저축 환산: 약 **{monthly_saving_eok*12:,.4f}억/년** (≈ **{monthly_saving_eok*12*10_000:,.0f}만원/년**)")

    years = st.slider(
        "기간 (년)",
        min_value=1,
        max_value=50,
        value=10,
        disabled=mode != "미래 자산(1~N년)",
    )

return_basis = "nominal" if return_basis_label.startswith("명목") else "real"
infl = inflation_pct / 100.0

with left:
    cap_col, btn_col = st.columns([0.85, 0.15])
    with cap_col:
        st.caption(
            "가정: 월저축은 매달 1회 납입, 수익률/인플레이션은 매년 동일. "
            "‘실질 수익률’ 선택 시, 명목 총자산은 실질자산에 물가상승을 곱해 환산."
        )
    with btn_col:
        if st.button(
            "메모장 닫기" if st.session_state.note_open else "메모장 열기",
            use_container_width=True,
        ):
            st.session_state.note_open = not st.session_state.note_open
            st.rerun()

if right is not None:
    with right:
        st.subheader("메모장")
        existing = sorted([p.stem for p in NOTES_DIR.glob("*.txt")])
        selected = st.selectbox("불러오기", options=["(새 메모)"] + existing)

        if "note_title" not in st.session_state:
            st.session_state.note_title = ""
        if "note_body" not in st.session_state:
            st.session_state.note_body = ""

        col_a, col_b, col_c = st.columns([1, 1, 1])
        with col_a:
            if st.button("불러오기", disabled=selected == "(새 메모)", use_container_width=True):
                p = NOTES_DIR / f"{selected}.txt"
                text = p.read_text(encoding="utf-8") if p.exists() else ""
                lines = text.splitlines()
                st.session_state.note_title = (lines[0] if lines else selected).strip()
                st.session_state.note_body = "\n".join(lines[1:]).lstrip("\n")
        with col_b:
            if st.button("새 메모", use_container_width=True):
                st.session_state.note_title = ""
                st.session_state.note_body = ""
        with col_c:
            if st.button("저장", use_container_width=True):
                title_now = st.session_state.note_title.strip()
                body_now = st.session_state.note_body
                stem = sanitize_filename(title_now)
                path = NOTES_DIR / f"{stem}.txt"
                path.write_text(f"{title_now}\n{body_now.rstrip()}\n", encoding="utf-8")
                st.success(f"저장됨: {path.name}")

        title_now = st.session_state.note_title.strip()
        body_now = st.session_state.note_body
        stem = sanitize_filename(title_now)
        filename = f"{stem}.txt"
        download_text = f"{title_now}\n{body_now.rstrip()}\n"
        st.download_button(
            "다운로드(.txt)",
            data=download_text.encode("utf-8"),
            file_name=filename,
            mime="text/plain; charset=utf-8",
            use_container_width=True,
        )

        title = st.text_input("제목(첫 줄)", key="note_title", placeholder="예) 10년 목표 시나리오")
        st.markdown(f"**{title.strip() or '(제목 없음)'}**")
        st.text_area("내용(둘째 줄부터)", key="note_body", height=520, placeholder="여기에 내용을 적으세요.")

with left:
    if mode == "미래 자산(1~N년)":
        df = simulate_yearly_table(
            seed_eok=seed_eok,
            monthly_saving_eok=monthly_saving_eok,
            annual_return_pct=annual_return_pct,
            inflation_pct=inflation_pct,
            years=years,
            return_basis=return_basis,
        )

        st.subheader("결과")
        st.dataframe(
            df.style.format(
                {
                    "누적 납입(억)": "{:,.2f}",
                    "명목 총자산(억)": "{:,.2f}",
                    "실질 총자산(억, 현재가치)": "{:,.2f}",
                }
            ),
            width="stretch",
        )

        last = df.iloc[-1]
        st.markdown(
            f"""
**{int(last["년"])}년 후**
- 명목 총자산: **{last["명목 총자산(억)"]:,.2f}억**
- 실질 총자산(현재가치): **{last["실질 총자산(억, 현재가치)"]:,.2f}억**
"""
        )

        year_to_note = st.selectbox("메모로 옮길 연차", options=list(range(1, int(years) + 1)), index=int(years) - 1)
        if st.button("선택 연차 결과를 메모장에 옮겨적기"):
            row = df[df["년"] == int(year_to_note)].iloc[0]
            entry = build_note_entry_real(
                title="미래 자산(연차 선택)",
                seed_eok=seed_eok,
                monthly_saving_eok=monthly_saving_eok,
                annual_return_pct=annual_return_pct,
                inflation_pct=inflation_pct,
                return_basis=return_basis,
                horizon_years=int(year_to_note),
                horizon_months=None,
                result_lines=[
                    f"{int(year_to_note)}년 후 실질 총자산(현재가치) {float(row['실질 총자산(억, 현재가치)']):,.4f}억",
                    f"{int(year_to_note)}년 후 누적 납입 {float(row['누적 납입(억)']):,.4f}억",
                ],
            )
            queue_note_append(entry)
            st.success("메모장에 추가했습니다.")

    elif mode == "목표자산 → 필요한 월저축":
        st.subheader("목표자산에 도달하기 위한 월저축(역산)")
        target_kind = st.radio("목표자산 기준", options=["명목 총자산(억)", "실질 총자산(억, 현재가치)"], index=0)
        target_eok = st.number_input("목표자산 (억)", min_value=0.0, value=10.0, step=0.1)
        horizon_years = st.slider("목표 기간 (년)", min_value=1, max_value=80, value=10)

        months = int(horizon_years) * 12

        if return_basis == "nominal":
            monthly_r = annual_to_monthly_rate(annual_return_pct)
            if target_kind.startswith("명목"):
                nominal_target = float(target_eok)
            else:
                nominal_target = float(target_eok) * ((1.0 + infl) ** horizon_years) if infl > -1.0 else float("nan")
            need_monthly = required_monthly_saving(seed_eok, monthly_r, nominal_target, months)
        else:
            monthly_real_r = annual_to_monthly_rate(annual_return_pct)
            if target_kind.startswith("실질"):
                real_target = float(target_eok)
            else:
                real_target = float(target_eok) / ((1.0 + infl) ** horizon_years) if infl > -1.0 else float("nan")
            need_monthly = required_monthly_saving(seed_eok, monthly_real_r, real_target, months)

        need_yearly = need_monthly * 12.0

        st.markdown(
            f"""
- 필요한 월저축: **{need_monthly:,.4f}억/월** (≈ **{need_monthly*10_000:,.0f}만원/월**)
- 필요한 연저축: **{need_yearly:,.4f}억/년** (≈ **{need_yearly*10_000:,.0f}만원/년**)
"""
        )
        st.caption("주의: 목표가 너무 작거나(이미 달성), 수익률/기간 조합에 따라 음수가 나올 수 있습니다(추가 저축 불필요/과도한 목표 설정 등).")

        # 메모 기록은 구매력(실질) 기준으로 통일
        if st.button("결과를 메모장에 옮겨적기"):
            real_target = float(target_eok)
            if target_kind.startswith("명목"):
                real_target = float(target_eok) / ((1.0 + infl) ** horizon_years) if infl > -1.0 else float("nan")

            if return_basis == "nominal":
                real_return_pct = nominal_to_real_return_pct(nominal_return_pct=annual_return_pct, inflation_pct=inflation_pct)
            else:
                real_return_pct = float(annual_return_pct)

            real_monthly_r = annual_to_monthly_rate(real_return_pct)
            need_monthly_real = required_monthly_saving(seed_eok, real_monthly_r, real_target, months)

            entry = build_note_entry_real(
                title="목표자산 → 필요한 월저축",
                seed_eok=seed_eok,
                monthly_saving_eok=need_monthly_real,
                annual_return_pct=annual_return_pct,
                inflation_pct=inflation_pct,
                return_basis=return_basis,
                horizon_years=int(horizon_years),
                horizon_months=None,
                result_lines=[
                    f"목표 실질 총자산(현재가치) {real_target:,.4f}억",
                    f"필요 월저축(구매력 기준) {need_monthly_real:,.4f}억/월 (≈ {need_monthly_real*10_000:,.0f}만원/월)",
                ],
            )
            queue_note_append(entry)
            st.success("메모장에 추가했습니다.")

    elif mode == "목표자산 → 걸리는 기간":
        st.subheader("목표자산에 도달하는 데 걸리는 기간(역산)")
        target_kind2 = st.radio(
            "목표자산 기준 ",
            options=["명목 총자산(억)", "실질 총자산(억, 현재가치)"],
            index=0,
            key="target_kind2",
        )
        target_eok2 = st.number_input("목표자산 (억) ", min_value=0.0, value=10.0, step=0.1, key="target_eok2")

        if return_basis == "nominal" and target_kind2.startswith("명목"):
            months_needed = months_to_reach_target(
                seed=seed_eok,
                monthly_saving=monthly_saving_eok,
                monthly_r=annual_to_monthly_rate(annual_return_pct),
                target=float(target_eok2),
            )
        elif return_basis == "real" and target_kind2.startswith("실질"):
            months_needed = months_to_reach_target(
                seed=seed_eok,
                monthly_saving=monthly_saving_eok,
                monthly_r=annual_to_monthly_rate(annual_return_pct),
                target=float(target_eok2),
            )
        else:
            months_needed = simulate_months_until_target(
                seed_eok=seed_eok,
                monthly_saving_eok=monthly_saving_eok,
                annual_return_pct=annual_return_pct,
                inflation_pct=inflation_pct,
                return_basis=return_basis,
                target_kind=target_kind2,
                target_eok=float(target_eok2),
            )

        if months_needed is None:
            st.markdown("- 도달 기간: **계산 불가/매우 김** (월저축이 0이거나 목표가 너무 큼)")
        else:
            y, mo = months_to_years_months(months_needed)
            st.markdown(f"- 도달 기간: **{months_needed}개월** (≈ **{y}년 {mo}개월**)")

        if st.button("결과를 메모장에 옮겨적기"):
            result_lines: list[str] = []
            horizon_m = None if months_needed is None else int(months_needed)

            if months_needed is None:
                result_lines.append("도달 기간 계산 불가")
                real_goal = None
            else:
                result_lines.append(f"도달 기간 {int(months_needed)}개월 (≈ {y}년 {mo}개월)")
                if target_kind2.startswith("실질"):
                    real_goal = float(target_eok2)
                else:
                    real_goal = float(target_eok2) / ((1.0 + infl) ** (float(months_needed) / 12.0)) if infl > -1.0 else float("nan")
                result_lines.append(f"목표 실질 총자산(현재가치, 달성시점 환산) {real_goal:,.4f}억")

            entry = build_note_entry_real(
                title="목표자산 → 걸리는 기간",
                seed_eok=seed_eok,
                monthly_saving_eok=monthly_saving_eok,
                annual_return_pct=annual_return_pct,
                inflation_pct=inflation_pct,
                return_basis=return_basis,
                horizon_years=None,
                horizon_months=horizon_m,
                result_lines=result_lines,
            )
            queue_note_append(entry)
            st.success("메모장에 추가했습니다.")

    else:
        st.subheader("목표자산에 도달하기 위한 수익률(월저축 없음, 역산)")
        st.caption("가정: 월저축=0, 시드만 복리로 굴린다고 가정합니다.")
        target_kind3 = st.radio(
            "목표자산 기준",
            options=["명목 총자산(억)", "실질 총자산(억, 현재가치)"],
            index=0,
            key="target_kind3",
        )
        target_eok3 = st.number_input("목표자산 (억)", min_value=0.0, value=10.0, step=0.1, key="target_eok3")
        horizon_years3 = st.slider("목표 기간 (년)", min_value=1, max_value=80, value=10, key="horizon_years3")

        if return_basis == "nominal":
            if target_kind3.startswith("명목"):
                nominal_target = float(target_eok3)
            else:
                nominal_target = float(target_eok3) * ((1.0 + infl) ** horizon_years3) if infl > -1.0 else float("nan")
            need_return_pct = required_annual_return_pct_no_saving(seed=seed_eok, target=nominal_target, years=int(horizon_years3))
        else:
            if target_kind3.startswith("실질"):
                real_target = float(target_eok3)
            else:
                real_target = float(target_eok3) / ((1.0 + infl) ** horizon_years3) if infl > -1.0 else float("nan")
            need_return_pct = required_annual_return_pct_no_saving(seed=seed_eok, target=real_target, years=int(horizon_years3))

        if need_return_pct is None or (isinstance(need_return_pct, float) and (need_return_pct != need_return_pct)):
            st.markdown("- 필요한 수익률: **계산 불가** (시드/목표/기간 값을 확인하세요)")
        else:
            st.markdown(f"- 필요한 연평균 수익률: **{need_return_pct:,.3f}%**")

        if st.button("결과를 메모장에 옮겨적기"):
            # 메모 기록은 구매력(실질) 기준의 필요 수익률로 통일
            real_target = float(target_eok3)
            if target_kind3.startswith("명목"):
                real_target = float(target_eok3) / ((1.0 + infl) ** horizon_years3) if infl > -1.0 else float("nan")

            need_real_return_pct = required_annual_return_pct_no_saving(seed=seed_eok, target=real_target, years=int(horizon_years3))
            if need_real_return_pct is None or (isinstance(need_real_return_pct, float) and (need_real_return_pct != need_real_return_pct)):
                result_lines = ["필요 실질 수익률 계산 불가"]
            else:
                result_lines = [
                    f"목표 실질 총자산(현재가치) {real_target:,.4f}억",
                    f"필요 실질 수익률 {need_real_return_pct:,.3f}%",
                ]

            entry = build_note_entry_real(
                title="목표자산 → 수익률(월저축 없음)",
                seed_eok=seed_eok,
                monthly_saving_eok=None,
                annual_return_pct=need_real_return_pct if need_real_return_pct is not None else None,
                inflation_pct=inflation_pct,
                return_basis="real",
                horizon_years=int(horizon_years3),
                horizon_months=None,
                result_lines=result_lines,
            )
            queue_note_append(entry)
            st.success("메모장에 추가했습니다.")


