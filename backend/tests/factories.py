from app.models.quiz import Option, Question, Quiz


def make_questions() -> list[Question]:
    return [
        Question(
            id="q1",
            type="single",
            stem="RAG 的核心思路是什么？",
            options=[
                Option(key="A", text="只依赖模型记忆"),
                Option(key="B", text="先检索，再结合资料生成"),
                Option(key="C", text="复制搜索结果"),
                Option(key="D", text="增加模型参数"),
            ],
            answer=["B"],
            explanation="RAG 会先检索外部资料，再交给模型组织答案。",
            knowledge_point="RAG 基本定义",
            difficulty="easy",
        ),
        Question(
            id="q2",
            type="multiple",
            stem="哪些场景适合使用 RAG？",
            options=[
                Option(key="A", text="企业内部文档问答"),
                Option(key="B", text="无需事实的创意写作"),
                Option(key="C", text="需要最新资料的产品问答"),
                Option(key="D", text="固定规则的加法"),
            ],
            answer=["A", "C"],
            explanation="需要外部事实或私有资料时，RAG 更有价值。",
            knowledge_point="RAG 应用场景",
            difficulty="medium",
        ),
        Question(
            id="q3",
            type="judge",
            stem="接入 RAG 后，答案一定不会出错。",
            options=[
                Option(key="A", text="正确"),
                Option(key="B", text="错误"),
            ],
            answer=["B"],
            explanation="RAG 能降低错误概率，但检索和生成仍可能出错。",
            knowledge_point="RAG 能力边界",
            difficulty="medium",
        ),
    ]


def make_quiz() -> Quiz:
    return Quiz(
        quiz_id="quiz_test",
        title="RAG 入门闯关",
        summary="认识 RAG 的定义、场景和能力边界。",
        source_type="text",
        user_input="我想学习 RAG",
        questions=make_questions(),
    )

