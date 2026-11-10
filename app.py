from dataclasses import replace
from datetime import date, datetime

import pandas as pd
import streamlit as st

from task import Task
from schedule import CycleError, compute_schedule, days_over, project_finish
from evaluate import make_gantt, make_result_table


STATUS_OPTIONS = ["시작 전", "진행 중", "완료"]


def example_rows() -> pd.DataFrame:
    tasks = Task.get_task_example()
    return pd.DataFrame([
        {
            "ID": tid,
            "작업 이름": task.name,
            "기간(일)": task.duration,
            "최소 기간(일)": task.min_duration,
            "선행 작업": ", ".join(task.preds),
            "예정 시작일": task.planned_start,
            "상태": task.status,
        }
        for tid, task in tasks.items()
    ])


def required_text(value, field: str, row_index: int) -> str:
    if pd.isna(value) or not str(value).strip():
        raise ValueError(f"{row_index}행: '{field}'을(를) 입력해 주세요.")
    return str(value).strip()


def nonnegative_int(value, field: str, row_index: int) -> int:
    if pd.isna(value):
        raise ValueError(f"{row_index}행: '{field}'이(가) 비어 있습니다.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{row_index}행: '{field}'은(는) 정수여야 합니다.") from exc
    if not number.is_integer() or number < 0:
        raise ValueError(f"{row_index}행: '{field}'은(는) 0 이상의 정수여야 합니다.")
    return int(number)


def parse_date(value, row_index: int) -> date:
    if value is None or pd.isna(value):
        raise ValueError(f"{row_index}행: 예정 시작일을 입력해 주세요.")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise ValueError(f"{row_index}행: 예정 시작일은 날짜 형식이어야 합니다.") from exc


def parse_tasks(edited_rows: pd.DataFrame) -> dict[str, Task]:
    tasks = {}
    for row_index, row in enumerate(edited_rows.to_dict("records"), start=1):
        if all(pd.isna(row.get(field)) or str(row.get(field)).strip() == ""
               for field in ("ID", "작업 이름", "기간(일)", "예정 시작일")):
            continue

        tid = required_text(row.get("ID"), "ID", row_index)
        name = required_text(row.get("작업 이름"), "작업 이름", row_index)
        duration = nonnegative_int(row.get("기간(일)"), "기간(일)", row_index)
        minimum = nonnegative_int(row.get("최소 기간(일)"), "최소 기간(일)", row_index)
        start = parse_date(row.get("예정 시작일"), row_index)
        status = required_text(row.get("상태"), "상태", row_index)
        if status not in STATUS_OPTIONS:
            raise ValueError(f"{row_index}행: 상태는 {', '.join(STATUS_OPTIONS)} 중 하나여야 합니다.")
        if tid in tasks:
            raise ValueError(f"중복된 작업 ID가 있습니다: {tid}")

        raw_preds = row.get("선행 작업", "")
        preds = [] if pd.isna(raw_preds) else [p.strip() for p in str(raw_preds).split(",") if p.strip()]
        if len(preds) != len(set(preds)):
            raise ValueError(f"{row_index}행: 선행 작업 ID가 중복됐습니다.")
        tasks[tid] = Task(tid, name, duration, minimum, preds, start, status, 0)

    if not tasks:
        raise ValueError("작업을 한 개 이상 입력해 주세요.")

    for tid, task in tasks.items():
        for pred in task.preds:
            if pred not in tasks:
                raise ValueError(f"{tid} 작업의 선행 작업 '{pred}'이(가) 목록에 없습니다.")
    return tasks


def render_finish(schedule: dict, deadline: date) -> None:
    finish = project_finish(schedule)
    over = days_over(finish, deadline)
    left, right = st.columns(2)
    left.metric("전체 완료일", finish.isoformat())
    right.metric("마감 대비", f"{over}일 초과" if over > 0 else f"{-over}일 여유")
    if over <= 0:
        st.success("마감일 이내에 완료할 수 있습니다.")
    else:
        st.warning(f"마감일을 {over}일 초과합니다. 자동 조정 기능은 추후 연결할 예정입니다.")


def render_table(tasks: dict, schedule: dict, base_schedule=None) -> None:
    table = make_result_table(tasks, schedule, base_schedule=base_schedule)
    table = table.drop(columns=["기간(일)"], errors="ignore")
    ids = table["작업"].tolist()
    table.insert(4, "설정 기간(일)", [tasks[tid].duration for tid in ids])
    table.insert(5, "추가 지연(일)", [tasks[tid].delay for tid in ids])
    table.insert(6, "실제 소요(기간+지연)(일)", [tasks[tid].duration + tasks[tid].delay for tid in ids])
    st.dataframe(table, hide_index=True, width="stretch")


def main() -> None:
    st.set_page_config(page_title="팀플 일정 관리기", layout="wide")
    st.title("팀플 일정 관리기")
    st.caption("화면 뼈대: 작업 입력 → 기본 일정 계산 → 지연 반영 재계산")

    if "task_rows" not in st.session_state:
        st.session_state.task_rows = example_rows()
    if "version" not in st.session_state:
        st.session_state.version = 0

    st.subheader("1. 작업 정보 및 프로젝트 마감일")
    st.write("선행 작업은 ID를 쉼표로 구분해 입력하세요. 예: A, B")
    with st.form("task_form"):
        deadline = st.date_input("마감일", value=date(2026, 11, 20))
        edited = st.data_editor(
            st.session_state.task_rows,
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            column_config={
                "ID": st.column_config.TextColumn("ID", required=True),
                "작업 이름": st.column_config.TextColumn("작업 이름", required=True),
                "기간(일)": st.column_config.NumberColumn("기간(일)", min_value=0, step=1, required=True),
                "최소 기간(일)": st.column_config.NumberColumn("최소 기간(일)", min_value=0, step=1, required=True),
                "선행 작업": st.column_config.TextColumn("선행 작업"),
                "예정 시작일": st.column_config.DateColumn("예정 시작일", format="YYYY-MM-DD", required=True),
                "상태": st.column_config.SelectboxColumn("상태", options=STATUS_OPTIONS, required=True),
            },
        )
        submit_tasks = st.form_submit_button("기본 일정 계산", type="primary")

    if submit_tasks:
        try:
            tasks = parse_tasks(edited)
            base_schedule = compute_schedule(tasks)
        except (ValueError, TypeError, KeyError, CycleError) as exc:
            st.error(f"입력한 작업을 확인해 주세요: {exc}")
        else:
            st.session_state.task_rows = edited.copy()
            st.session_state.base_tasks = tasks
            st.session_state.base_schedule = base_schedule
            st.session_state.deadline = deadline
            st.session_state.delayed_tasks = None
            st.session_state.delayed_schedule = None
            st.session_state.version += 1
            st.success("기본 일정을 계산했습니다.")

    if "base_schedule" not in st.session_state:
        st.info("예시 작업 데이터가 채워져 있습니다. '기본 일정 계산' 버튼을 눌러 시작하세요.")
        return

    tasks = st.session_state.base_tasks
    base_schedule = st.session_state.base_schedule
    saved_deadline = st.session_state.deadline

    st.subheader("2. 기본 일정 결과")
    render_finish(base_schedule, saved_deadline)
    render_table(tasks, base_schedule)

    st.subheader("3. 지연 입력 및 재계산")
    st.write("각 작업에 추가로 발생한 지연 일수만 입력하세요. 원래 기간은 변경하지 않습니다.")
    previous = st.session_state.get("delayed_tasks") or tasks
    delay_rows = pd.DataFrame([
        {"작업 ID": tid, "작업 이름": task.name, "추가 지연(일)": previous[tid].delay}
        for tid, task in tasks.items()
    ])
    with st.form("delay_form"):
        edited_delay = st.data_editor(
            delay_rows,
            key=f"delay_editor_{st.session_state.version}",
            hide_index=True,
            width="stretch",
            disabled=["작업 ID", "작업 이름"],
            column_config={
                "추가 지연(일)": st.column_config.NumberColumn("추가 지연(일)", min_value=0, step=1, required=True)
            },
        )
        submit_delay = st.form_submit_button("지연 반영 재계산", type="primary")

    if submit_delay:
        try:
            delays = {
                row["작업 ID"]: nonnegative_int(row["추가 지연(일)"], "추가 지연(일)", i)
                for i, row in enumerate(edited_delay.to_dict("records"), start=1)
            }
            delayed_tasks = {tid: replace(task, delay=delays[tid]) for tid, task in tasks.items()}
            delayed_schedule = compute_schedule(delayed_tasks)
        except (ValueError, TypeError, KeyError, CycleError) as exc:
            st.error(f"지연 정보를 확인해 주세요: {exc}")
        else:
            st.session_state.delayed_tasks = delayed_tasks
            st.session_state.delayed_schedule = delayed_schedule
            st.success("지연을 반영해 일정을 다시 계산했습니다.")

    new_schedule = st.session_state.get("delayed_schedule")
    if new_schedule is not None:
        st.subheader("4. 지연 반영 결과 및 비교")
        new_tasks = st.session_state.delayed_tasks
        render_finish(new_schedule, saved_deadline)
        render_table(new_tasks, new_schedule, base_schedule)
        st.plotly_chart(make_gantt(new_tasks, base_schedule, new_schedule), width="stretch")
    else:
        st.subheader("4. 기본 일정 간트 차트")
        st.plotly_chart(make_gantt(tasks, base_schedule), width="stretch")

    st.divider()
    st.subheader("추후 통합할 기능")
    st.info("자동 조정안(adjust.py)과 직접 입력 일정 평가(evaluate.py)는 팀원들과 함수 규약을 확정한 뒤 연결합니다.")


if __name__ == "__main__":
    main()
