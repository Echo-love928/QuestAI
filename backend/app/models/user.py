from datetime import datetime

from pydantic import BaseModel, Field


class User(BaseModel):
    id: int
    nickname: str
    avatar_url: str | None = None
    total_xp: int = 0
    token_version: int = Field(default=0, exclude=True)


class LoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=256)


class LoginResult(BaseModel):
    token: str
    user: User


class UserProfile(User):
    quiz_count: int = 0
    correct_count: int = 0
    average_accuracy: int = 0


class UserProfileUpdate(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=32)
    avatar_url: str | None = Field(default=None, max_length=2048)


class QuizHistoryItem(BaseModel):
    quiz_id: str
    title: str
    accuracy: int | None = None
    question_count: int
    correct_count: int | None = None
    xp_earned: int
    status: str
    created_at: datetime


class QuizHistoryPage(BaseModel):
    items: list[QuizHistoryItem]
    total: int
    page: int
    page_size: int


class QuizHistoryDetail(BaseModel):
    quiz: dict
    answer_records: list[dict]
    report: dict | None = None
