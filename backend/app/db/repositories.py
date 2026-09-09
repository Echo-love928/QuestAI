import json
from decimal import Decimal
from typing import Any

import aiomysql

from app.db.database import Database
from app.models.quiz import Quiz
from app.models.quiz import QuizGenerateRequest
from app.models.quiz_task import QuizTaskStatus
from app.models.report import LearningReport, ReportGenerateRequest
from app.models.user import (
    QuizHistoryDetail,
    QuizHistoryItem,
    QuizHistoryPage,
    User,
    UserProfile,
    UserProfileUpdate,
)


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _user(row: dict) -> User:
    return User(
        id=row["id"],
        nickname=row["nickname"],
        avatar_url=row["avatar_url"],
        total_xp=row["total_xp"],
        token_version=row.get("token_version", 0),
    )


class MySQLRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def upsert_by_openid(self, openid: str) -> User:
        async with self.database.require_pool().acquire() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO users (openid, last_login_at)
                    VALUES (%s, CURRENT_TIMESTAMP(3))
                    ON DUPLICATE KEY UPDATE
                      id = LAST_INSERT_ID(id), last_login_at = CURRENT_TIMESTAMP(3)
                    """,
                    (openid,),
                )
                user_id = cursor.lastrowid
                await cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                row = await cursor.fetchone()
            await connection.commit()
        if row is None:
            raise RuntimeError("用户创建失败")
        return _user(row)

    async def get_by_id(self, user_id: int) -> User | None:
        row = await self.database.fetch_one(
            "SELECT * FROM users WHERE id = %s", (user_id,)
        )
        return _user(row) if row else None

    async def get_profile(self, user_id: int) -> UserProfile | None:
        row = await self.database.fetch_one(
            """
            SELECT u.id, u.nickname, u.avatar_url, u.total_xp, u.token_version,
                   COUNT(q.id) AS quiz_count,
                   COALESCE(SUM(q.correct_count), 0) AS correct_count,
                   COALESCE(ROUND(AVG(q.accuracy)), 0) AS average_accuracy
            FROM users u
            LEFT JOIN quiz_sessions q
              ON q.user_id = u.id AND q.status = 'completed'
            WHERE u.id = %s
            GROUP BY u.id
            """,
            (user_id,),
        )
        if row is None:
            return None
        return UserProfile(
            **_user(row).model_dump(),
            quiz_count=int(row["quiz_count"]),
            correct_count=int(row["correct_count"]),
            average_accuracy=int(row["average_accuracy"]),
        )

    async def update_profile(
        self, user_id: int, update: UserProfileUpdate
    ) -> UserProfile | None:
        changes = update.model_dump(exclude_none=True)
        if changes:
            assignments = ", ".join(f"{name} = %s" for name in changes)
            async with self.database.require_pool().acquire() as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute(
                        f"UPDATE users SET {assignments} WHERE id = %s",
                        (*changes.values(), user_id),
                    )
                await connection.commit()
        return await self.get_profile(user_id)

    async def save_quiz(self, user_id: int, quiz: Quiz) -> None:
        async with self.database.require_pool().acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO quiz_sessions
                      (quiz_id, user_id, title, summary, source_type, grounding_mode,
                       user_input, questions_json, sources_json, researched_at,
                       question_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE quiz_id = quiz_id
                    """,
                    (
                        quiz.quiz_id,
                        user_id,
                        quiz.title,
                        quiz.summary,
                        quiz.source_type,
                        quiz.grounding_mode,
                        quiz.user_input,
                        json.dumps(
                            [item.model_dump() for item in quiz.questions],
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            [item.model_dump(mode="json") for item in quiz.sources],
                            ensure_ascii=False,
                        ),
                        quiz.researched_at,
                        len(quiz.questions),
                    ),
                )
            await connection.commit()

    async def create_quiz_task(
        self,
        task_id: str,
        user_id: int | None,
        request: QuizGenerateRequest,
    ) -> QuizTaskStatus:
        async with self.database.require_pool().acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO quiz_generation_tasks
                      (task_id, user_id, status, request_json)
                    VALUES (%s, %s, 'pending', %s)
                    """,
                    (
                        task_id,
                        user_id,
                        json.dumps(request.model_dump(mode="json"), ensure_ascii=False),
                    ),
                )
            await connection.commit()
        return QuizTaskStatus(task_id=task_id, status="pending")

    async def get_quiz_task(
        self, task_id: str
    ) -> tuple[QuizTaskStatus, int | None] | None:
        row = await self.database.fetch_one(
            """
            SELECT task_id, user_id, status, result_json, error_code, error_message
            FROM quiz_generation_tasks WHERE task_id = %s
            """,
            (task_id,),
        )
        if row is None:
            return None
        quiz = Quiz.model_validate(_json_value(row["result_json"])) if row["result_json"] else None
        task = QuizTaskStatus(
            task_id=row["task_id"],
            status=row["status"],
            quiz=quiz,
            error_code=row["error_code"],
            error_message=row["error_message"],
        )
        return task, row["user_id"]

    async def mark_quiz_task_processing(self, task_id: str) -> None:
        await self._update_quiz_task(
            """
            UPDATE quiz_generation_tasks
            SET status = 'processing', started_at = CURRENT_TIMESTAMP(3)
            WHERE task_id = %s AND status = 'pending'
            """,
            (task_id,),
        )

    async def complete_quiz_task(self, task_id: str, quiz: Quiz) -> None:
        await self._update_quiz_task(
            """
            UPDATE quiz_generation_tasks
            SET status = 'completed', result_json = %s,
                completed_at = CURRENT_TIMESTAMP(3)
            WHERE task_id = %s
            """,
            (
                json.dumps(quiz.model_dump(mode="json"), ensure_ascii=False),
                task_id,
            ),
        )

    async def fail_quiz_task(
        self, task_id: str, error_code: int, error_message: str
    ) -> None:
        await self._update_quiz_task(
            """
            UPDATE quiz_generation_tasks
            SET status = 'failed', error_code = %s, error_message = %s,
                completed_at = CURRENT_TIMESTAMP(3)
            WHERE task_id = %s
            """,
            (error_code, error_message, task_id),
        )

    async def _update_quiz_task(self, sql: str, args: tuple[Any, ...]) -> None:
        async with self.database.require_pool().acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(sql, args)
            await connection.commit()

    async def save_report(
        self,
        user_id: int,
        request: ReportGenerateRequest,
        report: LearningReport,
    ) -> bool:
        pool = self.database.require_pool()
        async with pool.acquire() as connection:
            try:
                async with connection.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(
                        """
                        SELECT id, status FROM quiz_sessions
                        WHERE quiz_id = %s AND user_id = %s FOR UPDATE
                        """,
                        (request.quiz_id, user_id),
                    )
                    session = await cursor.fetchone()
                    if session is None or session["status"] == "completed":
                        await connection.rollback()
                        return False
                    session_id = session["id"]
                    questions = {item.id: item for item in request.questions}
                    for order, record in enumerate(request.answer_records, start=1):
                        result = next(
                            item
                            for item in report.answer_results
                            if item.question_id == record.question_id
                        )
                        await cursor.execute(
                            """
                            INSERT INTO answer_records
                              (quiz_session_id, question_id, question_order,
                               selected_answers_json, correct_answers_json,
                               is_correct, duration_ms)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                session_id,
                                record.question_id,
                                order,
                                json.dumps(record.selected_answers, ensure_ascii=False),
                                json.dumps(
                                    questions[record.question_id].answer,
                                    ensure_ascii=False,
                                ),
                                result.is_correct,
                                record.duration_ms,
                            ),
                        )
                    await cursor.execute(
                        """
                        INSERT INTO reports
                          (quiz_session_id, accuracy, mastered_points_json,
                           weak_points_json, three_line_summary_json,
                           advice_json, share_quote)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            session_id,
                            report.accuracy,
                            json.dumps(report.mastered_points, ensure_ascii=False),
                            json.dumps(report.weak_points, ensure_ascii=False),
                            json.dumps(report.three_line_summary, ensure_ascii=False),
                            json.dumps(report.advice, ensure_ascii=False),
                            report.share_quote,
                        ),
                    )
                    await cursor.execute(
                        """
                        UPDATE quiz_sessions
                        SET correct_count = %s, accuracy = %s, xp_earned = %s,
                            duration_ms = %s, status = 'completed',
                            completed_at = CURRENT_TIMESTAMP(3)
                        WHERE id = %s
                        """,
                        (
                            report.correct_count,
                            report.accuracy,
                            report.xp_earned,
                            sum(item.duration_ms for item in request.answer_records),
                            session_id,
                        ),
                    )
                    await cursor.execute(
                        "UPDATE users SET total_xp = total_xp + %s WHERE id = %s",
                        (report.xp_earned, user_id),
                    )
                await connection.commit()
                return True
            except Exception:
                await connection.rollback()
                raise

    async def list_quizzes(
        self, user_id: int, page: int, page_size: int
    ) -> QuizHistoryPage:
        offset = (page - 1) * page_size
        async with self.database.require_pool().acquire() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT COUNT(*) AS total FROM quiz_sessions WHERE user_id = %s",
                    (user_id,),
                )
                total_row = await cursor.fetchone()
                await cursor.execute(
                    """
                    SELECT quiz_id, title, accuracy, question_count, correct_count,
                           xp_earned, status, created_at
                    FROM quiz_sessions WHERE user_id = %s
                    ORDER BY created_at DESC LIMIT %s OFFSET %s
                    """,
                    (user_id, page_size, offset),
                )
                rows = await cursor.fetchall()
        items = []
        for row in rows:
            values = dict(row)
            if values["accuracy"] is not None:
                values["accuracy"] = int(values["accuracy"])
            items.append(QuizHistoryItem(**values))
        return QuizHistoryPage(
            items=items,
            total=int(total_row["total"] if total_row else 0),
            page=page,
            page_size=page_size,
        )

    async def get_quiz_detail(
        self, user_id: int, quiz_id: str
    ) -> QuizHistoryDetail | None:
        async with self.database.require_pool().acquire() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT * FROM quiz_sessions WHERE user_id = %s AND quiz_id = %s",
                    (user_id, quiz_id),
                )
                quiz = await cursor.fetchone()
                if quiz is None:
                    return None
                await cursor.execute(
                    """
                    SELECT question_id, question_order, selected_answers_json,
                           correct_answers_json, is_correct, duration_ms, answered_at
                    FROM answer_records WHERE quiz_session_id = %s
                    ORDER BY question_order
                    """,
                    (quiz["id"],),
                )
                answers = await cursor.fetchall()
                await cursor.execute(
                    "SELECT * FROM reports WHERE quiz_session_id = %s",
                    (quiz["id"],),
                )
                report = await cursor.fetchone()
        quiz["questions"] = _json_value(quiz.pop("questions_json"))
        quiz["sources"] = _json_value(quiz.pop("sources_json", None)) or []
        for answer in answers:
            answer["selected_answers"] = _json_value(
                answer.pop("selected_answers_json")
            )
            answer["correct_answers"] = _json_value(
                answer.pop("correct_answers_json")
            )
            answer["is_correct"] = bool(answer["is_correct"])
        if report:
            for source, target in (
                ("mastered_points_json", "mastered_points"),
                ("weak_points_json", "weak_points"),
                ("three_line_summary_json", "three_line_summary"),
                ("advice_json", "advice"),
            ):
                report[target] = _json_value(report.pop(source))
            if isinstance(report.get("accuracy"), Decimal):
                report["accuracy"] = int(report["accuracy"])
        return QuizHistoryDetail(quiz=quiz, answer_records=answers, report=report)
