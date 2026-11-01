# 팀플 일정 관리기 — 일정 계산 엔진 (파트 1)
# 날짜는 datetime.date, 기간은 int(일). 완료일 = 시작일 + 기간(+ 지연) = "다음 작업이 시작할 수 있는 날"
# tasks는 {작업 ID: Task} 딕셔너리 (Task 클래스는 task.py)
# 쓰는 Task 필드: preds(선행 작업 ID 목록), planned_start(예정 시작일), duration(기간), delay(지연 일수)
from datetime import timedelta

class CycleError(Exception):
    """선행 관계에 순환(예: A→B→C→A)이 있을 때 발생. app.py가 잡아서 화면에 보여 준다"""
    pass

def topo_sort(tasks):
    """선행 작업이 항상 앞에 오도록 작업 ID를 정렬한다(위상 정렬). 순환이 있으면 CycleError"""
    # 진입 차수: 작업마다 아직 안 끝난 선행 작업 수
    indegree = {tid: len(tasks[tid].preds) for tid in tasks}
    # 후속 작업 목록: preds(선행)를 뒤집어 "이 작업이 끝나면 풀리는 작업"을 만든다
    succs = {tid: [] for tid in tasks}

    for tid in tasks:
        for p in tasks[tid].preds:
            succs[p].append(tid)

    # 대기열: 선행 작업이 모두 끝나 지금 시작할 수 있는 작업. 처음엔 선행 작업이 없는 작업들
    ready = [tid for tid in indegree if indegree[tid] == 0]
    # 결과: 대기열에서 꺼낸 순서대로 쌓은 작업 ID (선행 작업이 항상 앞에 온다)
    order = []

    while(ready != []):
        cur = ready.pop(0)          # 먼저 준비된 작업부터 꺼낸다
        order.append(cur)
        for tid in succs[cur]:
            indegree[tid] -= 1      # cur가 끝났으니 후속 작업의 남은 선행 수를 하나 줄인다
            if indegree[tid] == 0:  # 선행이 모두 끝난 작업은 이제 시작할 수 있다
                ready.append(tid)

    # 순서에 못 들어간 작업이 있으면 순환이 있다는 뜻
    # (순환 안의 작업과, 그 순환에 막혀 뒤에 있는 작업이 함께 남는다)
    if len(tasks) != len(order):
        problems = [tid for tid in tasks if tid not in order]
        raise CycleError(f"순환이 있거나 그 뒤에 있는 작업: {", ".join(problems)}")
    return order

def compute_schedule(tasks, durations = None, starts = None):
    """작업별 (시작일, 완료일)을 계산해 {ID: (시작일, 완료일)}로 돌려준다
    durations: {ID: 기간} — 넘긴 작업만 duration 대신 사용 (adjust.py의 조정안 계산용)
    starts:    {ID: 날짜} — 넘긴 작업만 planned_start 대신 사용 (evaluate.py의 직접 입력 평가용)
    """
    # 기본값을 None으로 받고 여기서 새 딕셔너리를 만든다 (기본 인자로 {}를 쓰면 호출끼리 공유됨)
    if durations is None:
        durations = {}
    if starts is None:
        starts = {}

    # 선행 작업이 먼저 계산되도록 위상 정렬 순서대로 돈다 (계산 순서일 뿐, 작업 순서가 아니다)
    # 시작일은 자기 선행 작업만 기다리므로, 선행 관계가 없는 작업은 동시에 진행된다
    # (예: A→B, C→D이면 B는 A만, D는 C만 기다린다. 두 줄기는 서로 기다리지 않고 함께 진행된다)
    order = topo_sort(tasks)
    result = {}

    for tid in order:
        task = tasks[tid]

        # 시작일 = max(예정 시작일, 모든 선행 작업의 완료일)
        start = starts[tid] if tid in starts else task.planned_start
        for p in task.preds:
            start = max(start, result[p][1])

        # 완료일 = 시작일 + 기간 + 지연(delay: 원래보다 더 걸리는 일수)
        dur = durations[tid] if tid in durations else task.duration
        finish = start + timedelta(days=dur + task.delay)

        result[tid] = (start, finish)

    return result

def project_finish(schedule):
    """프로젝트 전체 완료일 = 작업 완료일 중 가장 늦은 날. schedule은 compute_schedule의 결과
    빈 일정이면 ValueError (완료일을 고를 작업이 없다)
    """
    if not schedule:
        raise ValueError("작업이 없어 전체 완료일을 계산할 수 없습니다")
    # 첫 작업의 완료일로 시작해 더 늦은 날이 나오면 바꾼다
    late_date = list(schedule.values())[0][1]
    for _, finish in schedule.values():
        late_date = max(late_date, finish)
    return late_date

def shift_days(before, after):
    """두 일정을 비교해 작업별 완료일이 며칠 밀렸는지 돌려준다 (앞당겨지면 음수)
    지연 영향 확인, 기존 일정과 조정안 비교에 쓴다
    before·after는 compute_schedule의 결과, [1]은 완료일
    """
    result = {}
    for tid in before:
        if tid in after:   # 양쪽 일정에 다 있는 작업만 비교
            result[tid] = (after[tid][1] - before[tid][1]).days
    return result
