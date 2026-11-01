# 테스트용 코드
from datetime import date
from types import SimpleNamespace as T
from schedule import CycleError, topo_sort, compute_schedule, project_finish, shift_days, days_over

# topo_sort — 순서는 하나로 정해지지 않으므로 "선행 작업이 앞에 오는가"만 본다 (README)
def check_order(tasks, order):
    assert sorted(order) == sorted(tasks), order
    for tid in tasks:
        for p in tasks[tid].preds:
            assert order.index(p) < order.index(tid), (order, p, tid)

tasks = {"A": T(preds=[]), "B": T(preds=["A"]), "C": T(preds=["A", "B"]), "D": T(preds=[])}
order = topo_sort(tasks)
check_order(tasks, order)
print(order)

# topo_sort — README 순환 예시: A의 선행에 C를 넣으면 A→B→C→A
cycle = {"A": T(preds=["C"]), "B": T(preds=["A"]), "C": T(preds=["B"]), "D": T(preds=[]), "E": T(preds=["D"])}
try:
    topo_sort(cycle)
    raise AssertionError("순환인데 CycleError가 나지 않음")
except CycleError as e:
    message = str(e)
assert all(tid in message for tid in ["A", "B", "C"]), message
print("순환 감지:", message)

# topo_sort — 자기 순환: A가 자기 자신을 선행으로 가짐. 관계없는 B는 메시지에 없어야 한다
try:
    topo_sort({"A": T(preds=["A"]), "B": T(preds=[])})
    raise AssertionError("자기 순환인데 CycleError가 나지 않음")
except CycleError as e:
    message = str(e)
assert "A" in message and "B" not in message, message
print("자기 순환 감지:", message)

print("topo_sort 테스트 통과")


# compute_schedule — README 예시 데이터와 기대 결과
def d(month, day):
    return date(2026, month, day)

def make_tasks():
    # 경우마다 delay를 바꾸므로 매번 새로 만든다
    return {
        "A": T(preds=[],    duration=4, planned_start=d(11, 2),  delay=0),
        "B": T(preds=["A"], duration=5, planned_start=d(11, 6),  delay=0),
        "C": T(preds=["B"], duration=3, planned_start=d(11, 11), delay=0),
        "D": T(preds=[],    duration=7, planned_start=d(11, 2),  delay=0),
        "E": T(preds=["D"], duration=2, planned_start=d(11, 11), delay=0),
    }

readme_tasks = make_tasks()
check_order(readme_tasks, topo_sort(readme_tasks))

# 기본
base = compute_schedule(make_tasks())
assert base == {
    "A": (d(11, 2), d(11, 6)),
    "B": (d(11, 6), d(11, 11)),
    "C": (d(11, 11), d(11, 14)),
    "D": (d(11, 2), d(11, 9)),
    "E": (d(11, 11), d(11, 13)),
}, base
assert project_finish(base) == d(11, 14), project_finish(base)
print("기본:", project_finish(base))

# A 지연 1일 → A·B·C 하루씩 밀림
t = make_tasks(); t["A"].delay = 1
a_late = compute_schedule(t)
assert project_finish(a_late) == d(11, 15), a_late
print("A 지연 1일:", project_finish(a_late))

# D 지연 1일 → D만 밀리고 E는 예정 시작(11/11) 그대로
t = make_tasks(); t["D"].delay = 1
d_late = compute_schedule(t)
assert d_late["D"][1] == d(11, 10) and d_late["E"][0] == d(11, 11) and project_finish(d_late) == d(11, 14), d_late
print("D 지연 1일:", project_finish(d_late))

# durations: 전부 최소 기간
shortest = compute_schedule(make_tasks(), durations={"A": 3, "B": 3, "C": 2, "D": 5, "E": 1})
assert project_finish(shortest) == d(11, 13), shortest
print("전부 최소 기간:", project_finish(shortest))

# starts: B만 11/8 시작으로 입력
s = compute_schedule(make_tasks(), starts={"B": d(11, 8)})
assert s["B"] == (d(11, 8), d(11, 13)) and s["C"] == (d(11, 13), d(11, 16)), s
assert project_finish(s) == d(11, 16), s
print("B 11/8 시작:", project_finish(s))

# 합류: C는 A(11/4 완료)와 B(11/7 완료)를 둘 다 기다리므로, 늦게 끝나는 B에 맞춰 11/7 시작
# preds를 ["B", "A"] 순서로 둬서, 마지막 선행 작업만 보는 버그도 잡히게 한다
merge = {
    "A": T(preds=[],         duration=2, planned_start=d(11, 2), delay=0),
    "B": T(preds=[],         duration=5, planned_start=d(11, 2), delay=0),
    "C": T(preds=["B", "A"], duration=1, planned_start=d(11, 2), delay=0),
}
m = compute_schedule(merge)
assert m["C"] == (d(11, 7), d(11, 8)), m
print("합류:", m["C"])

print("compute_schedule 테스트 통과")


# project_finish — 가장 늦은 완료일이 맨 앞에 있을 때, 시작일은 늦지만 완료일은 이른 작업이 섞였을 때
assert project_finish({"C": (d(11, 11), d(11, 14)), "A": (d(11, 2), d(11, 6))}) == d(11, 14)
assert project_finish({"A": (d(11, 2), d(11, 14)), "X": (d(11, 12), d(11, 13))}) == d(11, 14)
assert project_finish({"A": (d(11, 2), d(11, 6))}) == d(11, 6)

# project_finish — 빈 일정은 ValueError
try:
    project_finish({})
    raise AssertionError("빈 일정인데 ValueError가 나지 않음")
except ValueError as e:
    print("빈 일정:", e)
print("project_finish 테스트 통과")


# shift_days — 작업별 완료일이 며칠 밀렸는지 (앞당겨지면 음수)
assert shift_days(base, a_late) == {"A": 1, "B": 1, "C": 1, "D": 0, "E": 0}, shift_days(base, a_late)
assert shift_days(base, d_late) == {"A": 0, "B": 0, "C": 0, "D": 1, "E": 0}, shift_days(base, d_late)
assert shift_days(base, shortest) == {"A": -1, "B": -2, "C": -1, "D": -2, "E": -1}, shift_days(base, shortest)
assert shift_days(base, base) == {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}, shift_days(base, base)
print("shift_days 테스트 통과")


# days_over — README 정한 기준 2: 마감 11/20이면 완료일 11/21까지 통과, 11/22부터 초과
assert days_over(d(11, 21), d(11, 20)) == 0    # 마감 당일까지 작업 → 통과
assert days_over(d(11, 22), d(11, 20)) == 1    # 1일 초과
assert days_over(d(11, 14), d(11, 20)) == -7   # 7일 여유
print("days_over 테스트 통과")


# 우리 팀 일정 (README `## 일정`) — 기간은 이 테스트에서 정한 값(schedule만 커밋 이력 10/31~11/1).
# 각 작업의 완료일이 마감일 + 1일이 되도록 맞췄다. 기대값은 손으로 계산했다
# ID 규칙: 구현 작업은 파일 이름(같은 파일의 다른 일은 파일_내용), 단계 작업은 README 단계명
# 단순화: 기획서·리허설·발표는 다른 작업과 선행 관계가 없어 뺐다. 같은 날짜의 요약서와 PPT·소스는 한 작업으로 합쳤다.
#         입력 폼은 통합 점검(integration)에 포함했다. mid_submission은 app을 기다리지 않는다
#         (README: 뼈대가 없으면 시연을 대체). 담당자 충돌은 검사하지 않는다 (README 가정)
def make_team():
    # 경우마다 delay를 바꾸므로 매번 새로 만든다
    return {
        "schedule":         T(preds=[],                                                   duration=2, planned_start=d(10, 31), delay=0),
        "task":             T(preds=[],                                                   duration=3, planned_start=d(11, 2),  delay=0),
        "contracts":        T(preds=[],                                                   duration=3, planned_start=d(11, 2),  delay=0),
        "app":              T(preds=["schedule", "task", "contracts"],                    duration=4, planned_start=d(11, 5),  delay=0),
        "evaluate":         T(preds=["schedule", "task"],                                 duration=5, planned_start=d(11, 5),  delay=0),
        "adjust":           T(preds=["schedule", "task"],                                 duration=5, planned_start=d(11, 5),  delay=0),
        "task_check":       T(preds=["task"],                                             duration=5, planned_start=d(11, 5),  delay=0),
        "mid_submission":   T(preds=["evaluate", "adjust", "task_check"],                 duration=2, planned_start=d(11, 10), delay=0),
        "integration":      T(preds=["app", "evaluate", "adjust", "task_check", "contracts"], duration=1, planned_start=d(11, 14), delay=0),
        "final_impl":       T(preds=["adjust", "app"],                                    duration=8, planned_start=d(11, 10), delay=0),
        "evaluate_gantt":   T(preds=["evaluate"],                                         duration=8, planned_start=d(11, 10), delay=0),
        "final_submission": T(preds=["final_impl", "evaluate_gantt", "integration"],      duration=2, planned_start=d(11, 18), delay=0),
    }

team_deadlines = {
    "schedule": d(11, 9), "task": d(11, 4), "contracts": d(11, 4), "app": d(11, 8),
    "evaluate": d(11, 9), "adjust": d(11, 9), "task_check": d(11, 9), "mid_submission": d(11, 11),
    "integration": d(11, 14), "final_impl": d(11, 17), "evaluate_gantt": d(11, 17), "final_submission": d(11, 19),
}

# ① 지금 일정: schedule만 8일 여유(-8)이고 나머지는 자기 마감에 딱 맞는다(0). 최종 제출(11/20)에는 하루 여유(예비일)
team = compute_schedule(make_team())
assert team == {
    "schedule":         (d(10, 31), d(11, 2)),
    "task":             (d(11, 2),  d(11, 5)),
    "contracts":        (d(11, 2),  d(11, 5)),
    "app":              (d(11, 5),  d(11, 9)),
    "evaluate":         (d(11, 5),  d(11, 10)),
    "adjust":           (d(11, 5),  d(11, 10)),
    "task_check":       (d(11, 5),  d(11, 10)),
    "mid_submission":   (d(11, 10), d(11, 12)),
    "integration":      (d(11, 14), d(11, 15)),
    "final_impl":       (d(11, 10), d(11, 18)),
    "evaluate_gantt":   (d(11, 10), d(11, 18)),
    "final_submission": (d(11, 18), d(11, 20)),
}, team
for tid, deadline in team_deadlines.items():
    expected = -8 if tid == "schedule" else 0
    assert days_over(team[tid][1], deadline) == expected, (tid, team[tid])
assert days_over(project_finish(team), d(11, 20)) == -1, project_finish(team)
print("우리 팀 일정: 모든 마감 통과 (schedule 8일 여유), 최종 제출 1일 여유")

# ② adjust 초안 2일 지연 → mid_submission·final_impl·final_submission이 2일씩 밀린다
#    중간 제출은 2일 초과, 최종 제출은 예비일을 써도 1일 초과
t = make_team(); t["adjust"].delay = 2
team_late = compute_schedule(t)
assert {tid: n for tid, n in shift_days(team, team_late).items() if n} == {
    "adjust": 2, "mid_submission": 2, "final_impl": 2, "final_submission": 2,
}, shift_days(team, team_late)
assert days_over(team_late["mid_submission"][1], d(11, 11)) == 2, team_late["mid_submission"]
assert days_over(project_finish(team_late), d(11, 20)) == 1, project_finish(team_late)
print("adjust 2일 지연: 중간 제출 2일 초과, 최종 제출 1일 초과")
