from dataclasses import replace
from datetime import date, datetime

import pandas as pd
import streamlit as st

from task import Task
from schedule import CycleError, compute_schedule, days_over, project_finish
from adjust import propose_adjustment, validate_completed_dependencies
from evaluate import (
    evaluate_plan,
    make_gantt,
    make_problem_table,
    make_result_table,
    summary_text,
)

STATUS_OPTIONS = ("시작 전", "진행 중", "완료")


def rows_from_tasks(tasks: dict[str, Task]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "ID": tid,
            "작업 이름": task.name,
            "기간(일)": task.duration,
            "최소 기간(일)": task.min_duration,
            "선행 작업": ", ".join(task.preds),
            "예정 시작일": task.planned_start,
            "상태": task.status,
            "추가 지연(일)": task.delay,
        }
        for tid, task in tasks.items()
    ])


def required_text(value, field: str, row_index: int) -> str:
    if value is None or pd.isna(value) or not str(value).strip():
        raise ValueError(f"{row_index}행: '{field}'을(를) 입력해 주세요.")
    return str(value).strip()


def nonnegative_int(value, field: str, row_index: int) -> int:
    if value is None or pd.isna(value):
        raise ValueError(f"{row_index}행: '{field}'이(가) 비어 있습니다.")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{row_index}행: '{field}'은(는) 정수여야 합니다.") from exc
    if not number.is_integer() or number < 0:
        raise ValueError(f"{row_index}행: '{field}'은(는) 0 이상의 정수여야 합니다.")
    return int(number)


def parse_date(value, row_index: int, field="날짜") -> date:
    if value is None or pd.isna(value):
        raise ValueError(f"{row_index}행: {field}를 입력해 주세요.")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{row_index}행: {field}는 날짜 형식이어야 합니다.") from exc


def parse_tasks(edited_rows: pd.DataFrame) -> dict[str, Task]:
    tasks = {}
    for row_index, row in enumerate(edited_rows.to_dict("records"), start=1):
        if all(
            pd.isna(row.get(field)) or str(row.get(field)).strip() == ""
            for field in ("ID", "작업 이름", "기간(일)", "예정 시작일")
        ):
            continue
        tid = required_text(row.get("ID"), "ID", row_index)
        name = required_text(row.get("작업 이름"), "작업 이름", row_index)
        duration = nonnegative_int(row.get("기간(일)"), "기간(일)", row_index)
        minimum = nonnegative_int(row.get("최소 기간(일)"), "최소 기간(일)", row_index)
        delay = nonnegative_int(row.get("추가 지연(일)", 0), "추가 지연(일)", row_index)
        start = parse_date(row.get("예정 시작일"), row_index, "예정 시작일")
        status = required_text(row.get("상태"), "상태", row_index)
        if status not in STATUS_OPTIONS:
            raise ValueError(f"{row_index}행: 상태는 {', '.join(STATUS_OPTIONS)} 중 하나여야 합니다.")
        if tid in tasks:
            raise ValueError(f"작업 ID '{tid}'가 중복됐습니다.")
        raw_preds = row.get("선행 작업", "")
        if raw_preds is None or pd.isna(raw_preds):
            preds = []
        else:
            preds = [p.strip() for p in str(raw_preds).split(",") if p.strip()]
        if len(preds) != len(set(preds)):
            raise ValueError(f"{row_index}행: 선행 작업 ID가 중복됐습니다.")
        if tid in preds:
            raise ValueError(f"{row_index}행: 자기 자신을 선행 작업으로 지정할 수 없습니다.")
        if minimum > duration:
            raise ValueError(f"{row_index}행: 최소 기간이 원래 기간보다 깁니다.")
        tasks[tid] = Task(tid, name, duration, minimum, preds, start, status, delay)
    if not tasks:
        raise ValueError("작업을 한 개 이상 입력해 주세요.")
    for tid, task in tasks.items():
        for pred in task.preds:
            if pred not in tasks:
                raise ValueError(f"{tid} 작업의 선행 작업 '{pred}'이(가) 목록에 없습니다.")
    validate_completed_dependencies(tasks)
    return tasks


def display_finish(schedule: dict, deadline: date, *, show_auto_hint=False) -> None:
    finish = project_finish(schedule)
    over = days_over(finish, deadline)
    left, right = st.columns(2)
    left.metric("전체 완료일", finish.isoformat())
    right.metric("마감 대비", f"{over}일 초과" if over > 0 else f"{-over}일 여유")
    if over <= 0:
        st.success("마감일 이내에 완료할 수 있습니다.")
    else:
        msg = f"마감일을 {over}일 초과합니다."
        if show_auto_hint:
            msg += " 아래에서 자동 조정안을 계산하거나 직접 일정을 입력할 수 있습니다."
        st.warning(msg)


def display_table(tasks: dict, schedule: dict, base_schedule=None, *, durations=None) -> None:
    table = make_result_table(tasks, schedule, base_schedule=base_schedule)
    table = table.drop(columns=["기간(일)"], errors="ignore")
    ids = table["작업"].tolist()
    applied_durations = durations or {}
    settings = [applied_durations.get(tid, tasks[tid].duration) for tid in ids]
    delays = [tasks[tid].delay for tid in ids]
    insert_at = min(4, len(table.columns))
    table.insert(insert_at, "설정 기간(일)", settings)
    table.insert(insert_at + 1, "추가 지연(일)", delays)
    table.insert(insert_at + 2, "실제 소요(기간+지연)(일)", [a + b for a, b in zip(settings, delays)])
    st.dataframe(table, hide_index=True, width="stretch")


def direct_rows_from_schedule(tasks: dict, schedule: dict) -> pd.DataFrame:
    return pd.DataFrame([
        {"작업 ID": tid, "작업 이름": task.name, "시작일": schedule[tid][0], "기간(일)": task.duration}
        for tid, task in tasks.items()
    ])


def parse_direct_rows(rows: pd.DataFrame, tasks: dict) -> tuple[dict, dict]:
    starts, durations = {}, {}
    for row_index, row in enumerate(rows.to_dict("records"), start=1):
        tid = required_text(row.get("작업 ID"), "작업 ID", row_index)
        if tid not in tasks or tid in starts:
            raise ValueError(f"{row_index}행: 알 수 없거나 중복된 작업 ID '{tid}'입니다.")
        starts[tid] = parse_date(row.get("시작일"), row_index, "시작일")
        durations[tid] = nonnegative_int(row.get("기간(일)"), "기간(일)", row_index)
    return starts, durations


def tasks_with_updated_delays(tasks: dict[str, Task], edited_delay: pd.DataFrame) -> dict[str, Task]:
    editable = {tid for tid, task in tasks.items() if task.status != "완료"}
    changes = {}
    for row_index, row in enumerate(edited_delay.to_dict("records"), start=1):
        tid = required_text(row.get("작업 ID"), "작업 ID", row_index)
        if tid not in tasks:
            raise ValueError(f"{row_index}행: 존재하지 않는 작업 ID '{tid}'입니다.")
        if tid not in editable:
            raise ValueError(f"완료 작업 '{tid}'의 기존 지연은 변경할 수 없습니다.")
        if tid in changes:
            raise ValueError(f"{row_index}행: 작업 ID '{tid}'가 중복됐습니다.")
        changes[tid] = nonnegative_int(row.get("추가 지연(일)"), "추가 지연(일)", row_index)
    missing = editable - changes.keys()
    if missing:
        raise ValueError(f"지연 입력이 누락된 작업이 있습니다: {', '.join(sorted(missing))}")
    return {
        tid: replace(task, delay=changes.get(tid, task.delay))
        for tid, task in tasks.items()
    }


def applied_tasks_for_schedule(tasks: dict, schedule: dict, durations: dict) -> dict:
    validate_completed_dependencies(tasks)
    applied = {}
    for tid, task in tasks.items():
        if task.status == "완료":
            applied[tid] = replace(task)
        else:
            applied[tid] = replace(
                task, duration=durations[tid], planned_start=schedule[tid][0]
            )
    if compute_schedule(applied) != schedule:
        raise ValueError("조정안 적용 후의 계산 일정이 제안과 달라 적용할 수 없습니다.")
    return applied


def clear_calculated_results() -> None:
    for key in (
        "base_tasks", "base_schedule", "delayed_tasks", "delayed_schedule",
        "auto_result", "auto_source", "direct_result", "direct_starts",
        "direct_durations", "direct_rows", "direct_version", "mode", "closed",
    ):
        st.session_state.pop(key, None)


def apply_plan(tasks: dict, schedule: dict, durations: dict) -> None:
    applied = applied_tasks_for_schedule(tasks, schedule, durations)
    st.session_state.base_tasks = applied
    st.session_state.base_schedule = compute_schedule(applied)
    st.session_state.task_rows = rows_from_tasks(applied)
    st.session_state.delayed_tasks = None
    st.session_state.delayed_schedule = None
    st.session_state.auto_result = None
    st.session_state.auto_source = None
    st.session_state.direct_result = None
    st.session_state.mode = "result"
    st.session_state.version += 1
    st.session_state.applied_notice = True
    st.rerun()


def close_plan() -> None:
    st.session_state.closed = True
    st.rerun()


def show_auto_result(tasks: dict, from_schedule: dict, deadline: date) -> None:
    result = st.session_state.get("auto_result")
    if result is None:
        return
    st.subheader("5. 자동 조정안")
    if not result["possible"]:
        st.error(f"최소 기간으로 줄여도 마감을 {result['over']}일 초과하여 조정할 수 없습니다.")
        st.caption("아래 일정은 적용 가능한 조정안이 아닌 최소 기간 기준 참고 결과입니다.")
    else:
        st.success("자동 조정안이 생성되었습니다. 아래에서 결과를 확인하고 적용 여부를 선택하세요.")
    display_finish(result["schedule"], deadline)
    display_table(tasks, result["schedule"], from_schedule, durations=result["durations"])
    st.plotly_chart(
        make_gantt(tasks, from_schedule, result["schedule"], base_label="지연 반영 일정", new_label="자동 조정안"),
        width="stretch",
    )
    left, middle, right = st.columns(3)
    if left.button("제안 적용", disabled=not result["possible"], type="primary", key="apply_auto"):
        try:
            applied_tasks_for_schedule(tasks, result["schedule"], result["durations"])
        except (ValueError, TypeError, KeyError, OverflowError, CycleError) as exc:
            st.error(f"조정안을 적용할 수 없습니다: {exc}")
        else:
            apply_plan(tasks, result["schedule"], result["durations"])
    if middle.button("직접 입력", key="auto_to_direct"):
        st.session_state.mode = "direct"
        st.session_state.direct_rows = direct_rows_from_schedule(tasks, from_schedule)
        st.session_state.direct_version = st.session_state.get("direct_version", 0) + 1
        st.session_state.direct_result = None
        st.rerun()
    if right.button("종료", key="close_auto"):
        close_plan()


def show_direct_editor(tasks: dict, source_schedule: dict, deadline: date) -> None:
    st.subheader("6. 직접 일정 입력 및 평가")
    if "direct_rows" not in st.session_state:
        st.session_state.direct_rows = direct_rows_from_schedule(tasks, source_schedule)
    if "direct_version" not in st.session_state:
        st.session_state.direct_version = 0
    st.caption("시작일과 기간을 직접 수정하세요. 기존 delay는 자동으로 더해지며 완료된 작업은 변경할 수 없습니다.")
    with st.form("direct_plan_form"):
        edited = st.data_editor(
            st.session_state.direct_rows,
            key=f"direct_table_{st.session_state.direct_version}",
            hide_index=True,
            width="stretch",
            disabled=["작업 ID", "작업 이름"],
            column_config={
                "시작일": st.column_config.DateColumn("시작일", format="YYYY-MM-DD", required=True),
                "기간(일)": st.column_config.NumberColumn("기간(일)", min_value=0, step=1, required=True),
            },
        )
        evaluated = st.form_submit_button("직접 입력 일정 평가", type="primary")
    if evaluated:
        try:
            user_starts, user_durations = parse_direct_rows(edited, tasks)
            result = evaluate_plan(tasks, user_starts, user_durations, deadline)
            if result["schedule"] is not None:
                moved = [tid for tid in user_starts
                         if result["schedule"][tid][0] != user_starts[tid]]
                if moved:
                    result = dict(result)
                    result["ok"] = False
                    result["problems"] = list(result["problems"]) + [
                        {"작업": tid, "종류": "시작일 불일치",
                         "내용": "입력한 시작일이 계산 결과에서 유지되지 않습니다. 예정 시작일 및 선행 관계를 확인해 주세요."}
                        for tid in moved
                    ]
        except (ValueError, TypeError, KeyError, OverflowError, CycleError) as exc:
            st.error(f"직접 입력 일정을 평가할 수 없습니다: {exc}")
            st.session_state.direct_result = None
        else:
            st.session_state.direct_rows = edited.copy()
            st.session_state.direct_starts = user_starts
            st.session_state.direct_durations = user_durations
            st.session_state.direct_result = result
            st.info(summary_text(result))
    result = st.session_state.get("direct_result")
    if result is not None:
        if result["ok"]:
            st.success("직접 입력한 일정이 모든 검사를 통과했습니다.")
        else:
            st.warning("직접 입력한 일정에서 다음 문제를 발견했습니다.")
        problems = make_problem_table(result)
        if not problems.empty:
            st.dataframe(problems, hide_index=True, width="stretch")
        if result["schedule"] is not None:
            display_finish(result["schedule"], deadline)
            display_table(tasks, result["schedule"], source_schedule, durations=st.session_state.direct_durations)
            st.plotly_chart(
                make_gantt(tasks, source_schedule, result["schedule"], base_label="지연 반영 일정", new_label="직접 입력"),
                width="stretch",
            )
    a, b, c, d = st.columns(4)
    if a.button("직접 입력안 적용", disabled=not (result and result["ok"]), type="primary"):
        try:
            applied_tasks_for_schedule(tasks, result["schedule"], st.session_state.direct_durations)
        except (ValueError, TypeError, KeyError, OverflowError, CycleError) as exc:
            st.error(f"직접 입력안을 적용할 수 없습니다: {exc}")
        else:
            apply_plan(tasks, result["schedule"], st.session_state.direct_durations)
    if b.button("다시 입력"):
        st.session_state.direct_result = None
        st.session_state.direct_version += 1
        st.rerun()
    auto = st.session_state.get("auto_result")
    if c.button("제안 적용", disabled=not (auto and auto["possible"]), key="direct_apply_auto"):
        try:
            applied_tasks_for_schedule(tasks, auto["schedule"], auto["durations"])
        except (ValueError, TypeError, KeyError, OverflowError, CycleError) as exc:
            st.error(f"조정안을 적용할 수 없습니다: {exc}")
        else:
            apply_plan(tasks, auto["schedule"], auto["durations"])
    if d.button("종료", key="direct_close"):
        close_plan()


def main() -> None:
    st.set_page_config(page_title="팀플 일정 관리기", layout="wide")
    st.title("팀플 일정 관리기")
    st.caption("작업 입력 → 일정 계산 → 지연 반영 → 자동 조정 / 직접 입력 → 적용 또는 종료")
    if "version" not in st.session_state:
        st.session_state.version = 0
    if "closed" not in st.session_state:
        st.session_state.closed = False

    if st.session_state.closed:
        st.success("일정 검토를 종료했습니다.")
        if st.button("다시 열기"):
            st.session_state.closed = False
            st.rerun()
        return

    if st.session_state.pop("applied_notice", False):
        st.success("선택한 일정을 적용했습니다. 아래에서 반영된 일정을 확인할 수 있습니다.")

    st.subheader("1. 작업 입력")
    with st.expander("작업 추가 / 예시 데이터 불러오기 / 입력 완료", expanded="task_rows" not in st.session_state):
        st.caption("팀원의 task.py 입력 폼을 사용합니다. 작업을 추가한 뒤 '작업 입력 완료'를 누르세요.")
        imported_tasks = Task.input_task()

    if imported_tasks is not None:
        st.session_state.task_rows = rows_from_tasks(imported_tasks)
        clear_calculated_results()
        st.session_state.version += 1
        st.success("작업 입력을 불러왔습니다. 아래에서 내용을 확인한 다음 기본 일정을 계산하세요.")

    if "task_rows" not in st.session_state:
        st.info("작업을 추가하거나 예시 데이터를 불러온 후 '작업 입력 완료'를 눌러 주세요.")
        return

    st.subheader("2. 작업 정보 확인 및 기본 일정 계산")
    with st.form("task_form"):
        deadline = st.date_input("프로젝트 마감일", value=st.session_state.get("deadline", date(2026, 11, 20)))
        edited = st.data_editor(
            st.session_state.task_rows,
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            key=f"task_editor_{st.session_state.version}",
            column_config={
                "ID": st.column_config.TextColumn("ID", required=True),
                "작업 이름": st.column_config.TextColumn("작업 이름", required=True),
                "기간(일)": st.column_config.NumberColumn("기간(일)", min_value=0, step=1, required=True),
                "최소 기간(일)": st.column_config.NumberColumn("최소 기간(일)", min_value=0, step=1, required=True),
                "선행 작업": st.column_config.TextColumn("선행 작업 (ID를 쉼표로 구분)"),
                "예정 시작일": st.column_config.DateColumn("예정 시작일", format="YYYY-MM-DD", required=True),
                "상태": st.column_config.SelectboxColumn("상태", options=STATUS_OPTIONS, required=True),
                "추가 지연(일)": st.column_config.NumberColumn("추가 지연(일)", min_value=0, step=1, required=True),
            },
        )
        submit_tasks = st.form_submit_button("기본 일정 계산", type="primary")
    if submit_tasks:
        try:
            tasks = parse_tasks(edited)
            base_schedule = compute_schedule(tasks)
        except (ValueError, TypeError, KeyError, OverflowError, CycleError) as exc:
            st.error(f"입력한 작업을 확인해 주세요: {exc}")
        else:
            clear_calculated_results()
            st.session_state.task_rows = edited.copy()
            st.session_state.base_tasks = tasks
            st.session_state.base_schedule = base_schedule
            st.session_state.deadline = deadline
            st.session_state.delayed_tasks = None
            st.session_state.delayed_schedule = None
            st.session_state.version += 1
            st.success("기본 일정을 계산했습니다.")
            st.rerun()

    if "base_schedule" not in st.session_state:
        st.info("'기본 일정 계산' 버튼을 눌러 시작하세요.")
        return

    tasks = st.session_state.base_tasks
    base_schedule = st.session_state.base_schedule
    saved_deadline = st.session_state.deadline
    st.subheader("3. 기본 일정 결과")
    display_finish(base_schedule, saved_deadline, show_auto_hint=True)
    display_table(tasks, base_schedule)

    st.subheader("4. 지연 입력 및 재계산")
    previous = st.session_state.get("delayed_tasks") or tasks
    editable_ids = [tid for tid, task in tasks.items() if task.status != "완료"]
    completed_ids = [tid for tid, task in tasks.items() if task.status == "완료"]
    if completed_ids:
        st.caption(
            "완료 작업은 이미 발생한 지연을 유지하며 수정할 수 없습니다: "
            + ", ".join(f"{tid}({tasks[tid].delay}일)" for tid in completed_ids)
        )
    submit_delay = False
    if editable_ids:
        delay_rows = pd.DataFrame([
            {"작업 ID": tid, "작업 이름": tasks[tid].name, "추가 지연(일)": previous[tid].delay}
            for tid in editable_ids
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
    else:
        st.info("모든 작업이 완료되어 지연을 수정할 수 없습니다.")

    if submit_delay:
        try:
            delayed_tasks = tasks_with_updated_delays(tasks, edited_delay)
            delayed_schedule = compute_schedule(delayed_tasks)
        except (ValueError, TypeError, KeyError, OverflowError, CycleError) as exc:
            st.error(f"지연 정보를 확인해 주세요: {exc}")
        else:
            st.session_state.delayed_tasks = delayed_tasks
            st.session_state.delayed_schedule = delayed_schedule
            st.session_state.auto_result = None
            st.session_state.direct_result = None
            st.session_state.direct_rows = None
            st.session_state.mode = "result"
            st.success("지연을 반영해 일정을 다시 계산했습니다.")
            st.rerun()

    source_tasks = st.session_state.get("delayed_tasks") or tasks
    source_schedule = st.session_state.get("delayed_schedule") or base_schedule
    if st.session_state.get("delayed_schedule") is not None:
        st.subheader("지연 반영 결과 및 비교")
        display_finish(source_schedule, saved_deadline, show_auto_hint=True)
        display_table(source_tasks, source_schedule, base_schedule)
        st.plotly_chart(
            make_gantt(source_tasks, base_schedule, source_schedule, base_label="기본 일정", new_label="지연 반영"),
            width="stretch",
        )
    else:
        st.subheader("기본 일정 간트 차트")
        st.plotly_chart(make_gantt(tasks, base_schedule), width="stretch")

    st.divider()
    c1, c2, c3 = st.columns(3)
    if c1.button("자동 조정안 생성", type="primary"):
        try:
            result = propose_adjustment(source_tasks, saved_deadline)
        except (ValueError, TypeError, KeyError, OverflowError, CycleError) as exc:
            st.error(f"자동 조정안을 생성할 수 없습니다: {exc}")
        else:
            st.session_state.auto_result = result
            st.session_state.mode = "auto"
            st.session_state.direct_result = None
            st.rerun()
    if c2.button("직접 입력"):
        st.session_state.mode = "direct"
        st.session_state.direct_rows = direct_rows_from_schedule(source_tasks, source_schedule)
        st.session_state.direct_version = st.session_state.get("direct_version", 0) + 1
        st.session_state.direct_result = None
        st.rerun()
    if c3.button("종료"):
        close_plan()

    if st.session_state.get("mode") == "auto":
        show_auto_result(source_tasks, source_schedule, saved_deadline)
    elif st.session_state.get("mode") == "direct":
        show_direct_editor(source_tasks, source_schedule, saved_deadline)


if __name__ == "__main__":
    main()
