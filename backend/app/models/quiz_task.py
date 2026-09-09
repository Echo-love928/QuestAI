from typing import Literal

from pydantic import BaseModel, model_validator

from app.models.quiz import Quiz


QuizTaskState = Literal["pending", "processing", "completed", "failed"]


class QuizTaskStatus(BaseModel):
    task_id: str
    status: QuizTaskState
    quiz: Quiz | None = None
    error_code: int | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_terminal_payload(self) -> "QuizTaskStatus":
        if self.status == "completed" and self.quiz is None:
            raise ValueError("已完成任务必须包含题目")
        if self.status == "failed" and not self.error_message:
            raise ValueError("失败任务必须包含错误信息")
        return self
