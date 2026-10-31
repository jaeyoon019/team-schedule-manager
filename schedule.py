from datetime import timedelta

class CycleError(Exception):
    pass

def topo_sort(tasks):
    indegree = {tid: len(tasks[tid].preds) for tid in tasks}
    succs = {tid: [] for tid in tasks}

    for tid in tasks:
        for p in tasks[tid].preds:
            succs[p].append(tid)

    ready = [tid for tid in indegree if indegree[tid] == 0]
    order = []

    while(ready != []):
        cur = ready.pop(0)
        order.append(cur)
        for tid in succs[cur]:
            indegree[tid] -= 1
            if indegree[tid] == 0:
                ready.append(tid)

    if len(tasks) != len(order):
        problems = [tid for tid in tasks if tid not in order]
        raise CycleError(f"순환이 있거나 그 뒤에 있는 작업: {", ".join(problems)}")
    return order

def compute_schedule(tasks, durations = None, starts = None):
    if durations is None:
        durations = {}
    if starts is None:
        starts = {}

    order = topo_sort(tasks)
    result = {}

    for tid in order:
        task = tasks[tid]

        start = starts[tid] if tid in starts else task.planned_start
        for p in task.preds:
            start = max(start, result[p][1])

        dur = durations[tid] if tid in durations else task.duration
        finish = start + timedelta(days=dur + task.delay)

        result[tid] = (start, finish)

    return result

def project_finish(schedule):
    late_date = list(schedule.values())[0][1]
    for _, finish in schedule.values():
        late_date = max(late_date, finish)
    return late_date

def shift_days(before, after):
    result = {}
    for tid in before:
        if tid in after:
            result[tid] = (after[tid][1] - before[tid][1]).days
    return result