import datetime
from dataclasses import dataclass
import streamlit as st

# Streamlit 재실행 시에도 초기화되지 않도록 session_state에 리스트 생성
if "task_ids" not in st.session_state:
    st.session_state.task_ids = []

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

    ids = st.session_state.task_ids    #전체 작업 ID 목록

    #객체 생성시 바로 실행
    def __post_init__(self):
        #Task 객체 생성 후 자동으로 입력 검증
        if not self.validate_task():
            raise ValueError("유효하지 않은 task입니다")
        #Task 객체 생성 후 자동으로 전체 작업 ID 목록에 추가
        if self.id not in Task.ids:
            Task.ids.append(self.id)

    #Task 객체 입력 검증
    def validate_task(self):
        #Id, name이 비어있으면 False
        if not self.id or not self.name:
            return False
        #id중복 시 덮어씌우는 형태, 아래의 주석은 현재로써는 무시
        #이미 있는 id이면 False
        #if self.id in Task.ids:
        #    return False
        #duration, min_duration, delay가 음수이면 False
        if self.duration < 0 or self.min_duration < 0 or self.delay < 0:
            return False
        #min_duration(최소 기간)이 duration(소요 기간)보다 크면 False
        if self.min_duration > self.duration:
            return False
        #status의 값이 "시작 전", "진행 중", "완료" 중 하나가 아니면 False
        if self.status not in ["시작 전", "진행 중", "완료"]:
            return False
        #preds(선행 작업 id들 목록)에 ids(전체 작업 id 목록)에 없으면 False
        if self.ids is not None:
            for pred in self.preds:
                if pred not in Task.ids:
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

        with container.form("input_form"):
            temp_task_id = st.text_input("작업 ID", placeholder="예: A").strip()
            temp_duration = st.number_input("소요 기간(일)", value=1)
            temp_planned_start = st.date_input("예정 시작일", value=datetime.date.today())
            temp_status = st.selectbox("작업 상태", ["시작 전", "진행 중", "완료"])
            temp_name = st.text_input("작업 이름", placeholder="예: 작업 A").strip()
            temp_min_duration = st.number_input("최소 기간(일)", value=1)
            temp_preds_str = list(st.text_input("선행 작업 ID (쉼표로 구분)", placeholder="예: A, B (없으면 비워둠)").split(","))
            temp_delay = st.number_input("지연 일수(일)", value=0)

            submitted = st.form_submit_button("작업 추가") 

            temp_preds = [p.strip() for p in temp_preds_str if p.strip()]  # 공백 제거 및 빈 문자열 제거

        if not submitted:
            return None

        # Task 객체 생성 및 반환
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
            if not new_task.validate_task():
                raise ValueError("유효하지 않은 task입니다")
            
            container.success(f"작업 '{new_task.id} ({new_task.name})'이(가) 추가되었습니다.")
            return new_task
        except ValueError as e:
            container.error(str(e))
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