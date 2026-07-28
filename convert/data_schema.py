# data_schema.py
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict

@dataclass
class StepImage:
    relative_path: str
    absolute_path: str

    def to_dict(self):
        return asdict(self)

@dataclass
class Step:
    step_index: int
    content_text: str = ""
    action_json: Optional[Dict[Any, Any]] = None  # 存放解析后的JSON对象
    code_block: Optional[str] = None          # 存放非JSON的代码
    image: Optional[StepImage] = None

    def to_dict(self):
        data = {k: v for k, v in asdict(self).items() if v}
        if self.image:
            data['image'] = self.image.to_dict()
        return data

@dataclass
class TaskData:
    id: str
    base_path: str
    question: str
    gold_answer: str = ""
    question_image: str = "p0.png"
    steps: List[Step] = None
    model_final_answer: str = ""
    parse_success: bool = True
    error_msg: str = ""

    def to_dict(self):
        data = asdict(self)
        if self.steps:
            data['steps'] = [s.to_dict() for s in self.steps]
        return data