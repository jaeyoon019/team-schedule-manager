import datetime
from dataclasses import dataclass

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
        if self.min_duration > self.duration:
            return False
        if self.duration < 0 or self.min_duration < 0:
            return False
        if self.status not in ["시작 전", "진행 중", "완료"]:
            return False
        return True


    #입력 받는 함수
    @staticmethod
    def input_task(st_container=None):
        """추후에 입력 폼 작성"""
        pass
    
            
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