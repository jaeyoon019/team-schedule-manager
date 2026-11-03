# 팀플 일정 관리기 — 직접 입력 평가·결과 출력 (파트 4)
# 날짜는 datetime.date, 기간은 int(일). 완료일 = 시작일 + 기간 + 지연 = "다음 작업이 시작할 수 있는 날"
# tasks는 {작업 ID: Task} 딕셔너리 (Task 클래스는 task.py)
# 쓰는 Task 필드: name, duration, min_duration, preds, planned_start, status, delay
# 사용자가 직접 넣은 일정은 두 딕셔너리로 받는다
#   user_starts:    {ID: 시작일(date)}
#   user_durations: {ID: 기간(int)}   (지연 delay는 따로 더해지므로 기간에 포함하지 않는다)
# 사용자 입력은 몰래 고치지 않는다. 규칙을 어기면 적용하지 않고 문제가 있는 작업만 알려 준다
from datetime import timedelta

import pandas as pd
import plotly.express as px

from schedule import compute_schedule, project_finish, shift_days


def fmt(d):
    """날짜를 '11/6' 모양의 짧은 글자로 바꾼다 (메시지용)"""
    return f"{d.month}/{d.day}"


def make_problem(tid, kind, message):
    """문제 하나를 딕셔너리로 만든다. kind는 '입력 누락' / '최소 기간' / '선행 관계' / '완료 작업 변경' / '마감 준수'"""
    return {"작업": tid, "종류": kind, "내용": message}


def check_missing(tasks, user_starts, user_durations):
    """사용자 입력에 빠진 작업이 있는지 검사한다. 빠진 값을 몰래 채우지 않고 그대로 알려 준다"""
    problems = []
    for tid in tasks:
        if tid not in user_starts or tid not in user_durations:
            problems.append(make_problem(tid, "입력 누락", f"{tid} 작업의 시작일 또는 기간이 입력되지 않았습니다"))
    return problems


def check_min_duration(tasks, user_durations):
    """평가 1: 입력한 기간이 최소 기간보다 짧으면 안 된다"""
    problems = []
    for tid in tasks:
        task = tasks[tid]
        if user_durations[tid] < task.min_duration:
            problems.append(make_problem(
                tid, "최소 기간",
                f"{tid} 작업의 기간 {user_durations[tid]}일이 최소 기간 {task.min_duration}일보다 짧습니다"))
    return problems


def check_precedence(tasks, user_starts, user_durations):
    """평가 2: 작업은 선행 작업이 끝난 뒤에 시작해야 한다
    compute_schedule은 max()로 시작일을 뒤로 밀어 버려서 위반이 가려진다.
    그래서 여기서는 사용자가 입력한 값 그대로 직접 비교한다
    """
    problems = []
    for tid in tasks:
        for p in tasks[tid].preds:
            # 선행 작업 p의 완료일 = 입력한 시작일 + 입력한 기간 + 지연
            p_finish = user_starts[p] + timedelta(days=user_durations[p] + tasks[p].delay)
            if user_starts[tid] < p_finish:
                problems.append(make_problem(
                    tid, "선행 관계",
                    f"{tid} 작업을 {fmt(user_starts[tid])}에 시작하는데, 선행 작업 {p}는 {fmt(p_finish)}에 끝납니다"))
    return problems


def check_done_unchanged(tasks, user_starts, user_durations):
    """평가 3: 이미 완료한 작업은 시작일과 기간을 바꾸면 안 된다"""
    problems = []
    for tid in tasks:
        task = tasks[tid]
        if task.status != "완료":
            continue
        if user_starts[tid] != task.planned_start or user_durations[tid] != task.duration:
            problems.append(make_problem(
                tid, "완료 작업 변경",
                f"{tid} 작업은 이미 완료했는데 시작일 또는 기간이 바뀌었습니다 "
                f"(원래 {fmt(task.planned_start)} 시작, {task.duration}일)"))
    return problems


def deadline_margin(finish, deadline):
    """평가 4: 마감 판정에 쓰는 여유 일수를 계산한다
    마감 판정 = 완료일 <= 마감일 + 1일 (완료일은 '다음 작업이 시작할 수 있는 날'이라 마감일 당일까지 작업 가능)
    돌려주는 값: 0 이상이면 여유 일수, 음수면 초과 일수(절댓값)
    예: 마감 11/20이면 완료일 11/21은 0(통과), 11/22는 -1(1일 초과)
    adjust.py와 같은 식을 쓴다
    """
    return (deadline + timedelta(days=1) - finish).days


def evaluate_plan(tasks, user_starts, user_durations, deadline):
    """사용자가 직접 넣은 일정을 평가해 결과 딕셔너리를 돌려준다
    돌려주는 값:
      ok:       문제가 하나도 없으면 True
      problems: 문제 목록 (make_problem 모양)
      schedule: 계산한 {ID: (시작일, 완료일)}. 선행 관계 위반이 있거나 입력이 빠졌으면 None
      finish:   전체 완료일. schedule이 None이면 None
      margin:   deadline_margin 값 (0 이상 여유, 음수 초과). finish가 None이면 None
    순환 선행 관계가 있으면 compute_schedule에서 CycleError가 나므로 app.py가 잡는다
    """
    result = {"ok": False, "problems": [], "schedule": None, "finish": None, "margin": None}

    # 입력이 빠졌으면 나머지 검사를 할 수 없다
    missing = check_missing(tasks, user_starts, user_durations)
    if missing:
        result["problems"] = missing
        return result

    problems = []
    problems += check_min_duration(tasks, user_durations)
    problems += check_done_unchanged(tasks, user_starts, user_durations)
    precedence = check_precedence(tasks, user_starts, user_durations)
    problems += precedence

    # 선행 관계 위반이 없을 때만 완료일을 계산한다 (위반이 있으면 일정이 말이 안 된다)
    if not precedence:
        schedule = compute_schedule(tasks, durations=user_durations, starts=user_starts)
        finish = project_finish(schedule)
        margin = deadline_margin(finish, deadline)
        result["schedule"] = schedule
        result["finish"] = finish
        result["margin"] = margin
        if margin < 0:
            problems.append(make_problem(
                "전체", "마감 준수",
                f"전체 완료일 {fmt(finish)}이(가) 마감 {fmt(deadline)}을(를) {-margin}일 넘깁니다"))

    result["problems"] = problems
    result["ok"] = (problems == [])
    return result


def summary_text(result):
    """평가 결과를 한두 줄 글자로 만든다 (화면 맨 위에 보여 줄 용도)"""
    if result["finish"] is None:
        return "선행 관계 문제가 있어 완료일을 계산하지 못했습니다"
    text = f"전체 완료일: {fmt(result['finish'])}"
    margin = result["margin"]
    if margin >= 0:
        text += f", 마감까지 여유 {margin}일"
    else:
        text += f", 마감 {-margin}일 초과"
    return text


def make_problem_table(result):
    """문제 목록을 표(DataFrame)로 만든다. 문제가 없으면 빈 표"""
    return pd.DataFrame(result["problems"], columns=["작업", "종류", "내용"])


def make_result_table(tasks, schedule, base_schedule=None):
    """작업별 결과 표(DataFrame)를 만든다
    schedule:      보여 줄 일정 {ID: (시작일, 완료일)}
    base_schedule: 비교할 기존 일정. 주면 '완료일 변화(일)' 열이 추가된다 (shift_days 사용)
    """
    shifts = shift_days(base_schedule, schedule) if base_schedule is not None else {}
    rows = []
    for tid in tasks:               # 입력한 작업 순서대로 보여 준다
        start, finish = schedule[tid]
        row = {
            "작업": tid,
            "이름": tasks[tid].name,
            "시작일": fmt(start),
            "완료일": fmt(finish),
            "기간(일)": (finish - start).days,
        }
        if base_schedule is not None:
            row["완료일 변화(일)"] = shifts[tid]
        rows.append(row)
    return pd.DataFrame(rows)


def make_gantt(tasks, base_schedule, new_schedule=None):
    """Plotly 간트 차트를 만든다. new_schedule을 주면 기존/조정안을 나란히 비교한다
    완료일이 '다음 작업이 시작할 수 있는 날'이라 막대 끝을 완료일로 그대로 쓴다
    """
    rows = []
    labels = []
    for tid in tasks:
        label = f"{tid} {tasks[tid].name}"
        labels.append(label)
        start, finish = base_schedule[tid]
        rows.append({"작업": label, "시작": pd.to_datetime(start), "완료": pd.to_datetime(finish), "구분": "기존"})
        if new_schedule is not None:
            start, finish = new_schedule[tid]
            rows.append({"작업": label, "시작": pd.to_datetime(start), "완료": pd.to_datetime(finish), "구분": "조정안"})

    df = pd.DataFrame(rows)
    fig = px.timeline(df, x_start="시작", x_end="완료", y="작업", color="구분",
                      category_orders={"작업": labels})
    fig.update_yaxes(autorange="reversed")   # 위에서부터 입력 순서대로
    fig.update_layout(barmode="group")       # 기존/조정안이 겹치지 않고 나란히
    return fig
