# 우리 팀 일정 시나리오 테스트 — schedule.py 엔진이 아니라 README `## 일정` 계획이 마감 안에 들어오는지 본다
# README 일정을 바꾸면 이 파일도 같이 고친다. 엔진 단위 테스트는 test_schedule.py
from datetime import date
from types import SimpleNamespace as T
from schedule import compute_schedule, project_finish, shift_days, days_over

def d(month, day):
    return date(2026, month, day)


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
