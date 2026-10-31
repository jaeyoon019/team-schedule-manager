# 테스트용 코드
from datetime import date
from types import SimpleNamespace as T
from schedule import CycleError, topo_sort, compute_schedule, project_finish, shift_days

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

print("compute_schedule 테스트 통과")


# project_finish — 가장 늦은 완료일이 맨 앞에 있을 때, 시작일은 늦지만 완료일은 이른 작업이 섞였을 때
assert project_finish({"C": (d(11, 11), d(11, 14)), "A": (d(11, 2), d(11, 6))}) == d(11, 14)
assert project_finish({"A": (d(11, 2), d(11, 14)), "X": (d(11, 12), d(11, 13))}) == d(11, 14)
assert project_finish({"A": (d(11, 2), d(11, 6))}) == d(11, 6)
print("project_finish 테스트 통과")


# shift_days — 작업별 완료일이 며칠 밀렸는지 (앞당겨지면 음수)
assert shift_days(base, a_late) == {"A": 1, "B": 1, "C": 1, "D": 0, "E": 0}, shift_days(base, a_late)
assert shift_days(base, d_late) == {"A": 0, "B": 0, "C": 0, "D": 1, "E": 0}, shift_days(base, d_late)
assert shift_days(base, shortest) == {"A": -1, "B": -2, "C": -1, "D": -2, "E": -1}, shift_days(base, shortest)
assert shift_days(base, base) == {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}, shift_days(base, base)
print("shift_days 테스트 통과")
