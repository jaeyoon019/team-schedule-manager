from datetime import dat

from schedule import compute_schedule, days_over, project_finish


def make_min_durations(tasks) -> dict[str, int]:
    return {
        tid: task.duration if task.status == "완료" else task.min_duration
        for tid, task in tasks.items()
    }


def _adjusted_schedule(tasks, durations, fixed_schedule):
    earliest = min(task.planned_start for task in tasks.values())
    starts = {}
    for tid, task in tasks.items():
        if task.status == "완료":
            starts[tid] = fixed_schedule[tid][0]
        elif task.preds:
            starts[tid] = earliest

    schedule = compute_schedule(tasks, durations=durations, starts=starts)

    for tid, task in tasks.items():
        if task.status == "완료" and schedule[tid] != fixed_schedule[tid]:
            raise ValueError(f"완료 작업 {tid}의 일정이 변경되어 조정할 수 없습니다.")
    return schedule


def restore_durations(tasks, deadline: date, durations: dict[str, int]) -> dict[str, int]:
    restored = durations.copy()
    fixed_schedule = compute_schedule(tasks)
    while True:
        increased = False
        for tid, task in tasks.items():
            if task.status == "완료" or restored[tid] >= task.duration:
                continue
            restored[tid] += 1
            candidate = _adjusted_schedule(tasks, restored, fixed_schedule)
            if days_over(project_finish(candidate), deadline) > 0:
                restored[tid] -= 1
            else:
                increased = True
        if not increased:
            return restored


def propose_adjustment(tasks, deadline: date) -> dict:
    original_schedule = compute_schedule(tasks)
    original_finish = project_finish(original_schedule)
    original_over = days_over(original_finish, deadline)

    if original_over <= 0:
        return {
            "possible": True,
            "durations": {tid: task.duration for tid, task in tasks.items()},
            "schedule": original_schedule,
            "finish": original_finish,
            "over": original_over,
        }

    minimum_durations = make_min_durations(tasks)
    minimum_schedule = _adjusted_schedule(tasks, minimum_durations, original_schedule)
    minimum_finish = project_finish(minimum_schedule)
    minimum_over = days_over(minimum_finish, deadline)
    if minimum_over > 0:
        return {
            "possible": False,
            "durations": minimum_durations,
            "schedule": minimum_schedule,
            "finish": minimum_finish,
            "over": minimum_over,
        }

    durations = restore_durations(tasks, deadline, minimum_durations)
    schedule = _adjusted_schedule(tasks, durations, original_schedule)
    finish = project_finish(schedule)
    return {
        "possible": True,
        "durations": durations,
        "schedule": schedule,
        "finish": finish,
        "over": days_over(finish, deadline),
    }
