import datetime
from dataclasses import dataclass
import streamlit as st

#작업 각각의 정보를 담는 데이터 클래스
@dataclass
class Task:
    #필드부분
    id:str                          #고유ID
    name:str                        #작업 이름
    duration:int                    #소요기간(일)
    min_duration:int                #최소기간(duraton보다 클 수 없음)
    preds:list[str]                 #선행 작업 ID목록
    planned_start:datetime.date     #예정 시작일
    status:str="시작 전"             #"시작 전"/"진행 중"/"완료"(이 세개의 값만 가질 수 있음)
    delay:int=0                     #원래보다 더 걸리는 일수(기본적으로 0)

    #객체 생성시 바로 실행
    def __post_init__(self):
        #Task 객체 생성 후 자동으로 입력 검증
        if not self.validate_task():
            raise ValueError("유효하지 않은 task입니다")

    #Task 객체 입력 검증
    def validate_task(self):
        #Id, name이 비어있으면 False
        if not self.id or not self.name:
            return False
        #같은 id로 다시 추가하면 덮어쓴다 (중복 검사는 Task가 아니라 입력 폼·app.py가 맡는다)
        #duration, min_duration, delay가 음수이면 False
        if self.duration < 0 or self.min_duration < 0 or self.delay < 0:
            return False
        #min_duration(최소 기간)이 duration(소요 기간)보다 크면 False
        if self.min_duration > self.duration:
            return False
        #status의 값이 "시작 전", "진행 중", "완료" 중 하나가 아니면 False
        if self.status not in ["시작 전", "진행 중", "완료"]:
            return False
        #preds(선행 작업)가 자기자신을 포함 하거나 없으면 False
        if self.id in self.preds:
            return False
        if not isinstance(self.preds, list):
            return False
        return True


    #입력 받는 함수
    @staticmethod
    def input_task(st_container=None):
        
        #Streamlit 입력 폼을 통해 정보를 입력 후 Task 객체를 반환
        #입력이 끝나면 검증, 검증에 실패하면 None을 반환
        
        container = st_container if st_container is not None else st
        #입력한 작업 목록은 세션(브라우저 탭)마다 따로 둔다. {작업ID: Task객체}
        tasks = st.session_state.setdefault("input_tasks", {})

        #작업 입력 폼
        with container.form("input_form"):
            temp_task_id = st.text_input("작업 ID", placeholder="예: A").strip()
            temp_duration = st.number_input("소요 기간(일)", value=1)
            temp_planned_start = st.date_input("예정 시작일", value=datetime.date.today())
            temp_status = st.selectbox("작업 상태", ["시작 전", "진행 중", "완료"])
            temp_name = st.text_input("작업 이름", placeholder="예: 작업 A").strip()
            temp_min_duration = st.number_input("최소 기간(일)", value=1)
            temp_preds_str = list(st.text_input("선행 작업 ID (쉼표로 구분)", placeholder="예: A, B (없으면 비워둠)").split(","))
            temp_delay = st.number_input("지연 일수(일)", value=0)

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                submitted = st.form_submit_button("작업 추가") 
            with col2:
                example = st.form_submit_button("예시 데이터 불러오기")
            with col3:
                reset = st.form_submit_button("작업 초기화")
            with col4:
                completed = st.form_submit_button("작업 입력 완료", type="primary", width="stretch")

            temp_preds = [p.strip() for p in temp_preds_str if p.strip()]  # 공백 제거 및 빈 문자열 제거

        #'작업 추가'버튼을 눌렀을 때 검증 후 Task 객체 생성 및 tasks에 추가
        if submitted:
            try:
                new_task = Task(
                    id=temp_task_id,
                    name=temp_name,
                    duration=int(temp_duration),
                    min_duration=int(temp_min_duration),
                    preds=temp_preds,
                    planned_start=temp_planned_start,
                    status=temp_status,
                    delay=int(temp_delay)
                )
                container.success(f"작업 '{new_task.id} ({new_task.name})'이(가) 추가되었습니다.")
                tasks.update({new_task.id: new_task})

            except ValueError as e:
                container.error(str(e))
                return None

        if example:
            example_tasks = Task.get_task_example()
            tasks.update(example_tasks)
            container.success("예시 데이터가 추가되었습니다.")
            return None

        if reset:
            tasks.clear()
            container.success("작업이 초기화 되었습니다.")
            return None

        #선행 작업으로 입력됐지만 아직 추가되지 않은 작업 ID (저장하지 않고 매번 계산)
        missing = sorted({pred for task in tasks.values() for pred in task.preds} - tasks.keys())

        #'작업 입력 완료' 버튼을 눌렀을 때 검증 후 전체 작업 딕셔너리 반환
        if completed:
            if not tasks:
                container.error("작업을 한 개 이상 추가해 주세요.")
                return None
            if missing:
                container.error(f"선행 작업으로 입력되었으나 아직 추가되지 않은 작업이 있습니다: {', '.join(missing)}")
                return None
            return tasks

        if tasks:
            container.info(f"현재 추가된 작업 ID: {', '.join(tasks.keys())}")
        if missing:
            container.warning(f"아직 추가되지 않은 선행 작업 ID: {', '.join(missing)}")
        return None
            
    #README에 적힌 예시데이터를 반환하는 매서드
    @staticmethod
    def get_task_example():
        #dict[str, Task] (str:작업ID, Task:작업 객체) 딕셔너리를 반환 값으로 가짐

        #README에 적힌 예시데이터
        tasks = {
            "A":Task(
                id="A", 
                name="작업 A", 
                duration=4, 
                min_duration=3, 
                preds=[], 
                planned_start=datetime.date(2026, 11, 2)
                ),

            "B":Task(
                id="B", 
                name="작업 B", 
                duration=5, 
                min_duration=3, 
                preds=["A"], 
                planned_start=datetime.date(2026, 11, 6)
                ),

            "C":Task(
                id="C", 
                name="작업 C", 
                duration=3, 
                min_duration=2, 
                preds=["B"], 
                planned_start=datetime.date(2026, 11, 11)
                ),

            "D":Task(
                id="D", 
                name="작업 D", 
                duration=7, 
                min_duration=5, 
                preds=[], 
                planned_start=datetime.date(2026, 11, 2)
                ),

            "E":Task(
                id="E", 
                name="작업 E", 
                duration=2, 
                min_duration=1, 
                preds=["D"], 
                planned_start=datetime.date(2026, 11, 11)
                )
            }
        return tasks

