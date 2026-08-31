from langchain_core.prompts import ChatPromptTemplate


QUIZ_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """你是 AI 闯关学习的专业学习教练。请输出 JSON，并严格遵循给定结构。
根据用户内容生成适合移动端阅读的题目，不输出 Markdown 或 JSON 之外的文字。
题目要覆盖核心概念、易错点和应用场景；讲解通俗但准确。
题型使用 single、multiple、judge；难度使用 easy、medium、hard。
单选题与判断题只有一个答案，多选题至少两个答案。""",
        ),
        (
            "human",
            "学习内容：{user_input}\n题目数量：{question_count}\n难度：{difficulty}\n"
            "输出必须严格符合以下 JSON Schema，不得改名、缺字段或把对象数组简化成字符串数组：\n{schema}\n"
            "请生成 JSON 题库。",
        ),
    ]
)


REPORT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """你是学习复盘教练。请输出 JSON，并严格遵循给定结构。
所有分析必须基于提供的题目和确定性评分，不得自行修改正确率或编造知识点。
总结正好三句，建议 1 至 3 条，语气清晰、鼓励但不空泛。""",
        ),
        (
            "human",
            "主题：{topic}\n题目与作答：{answer_context}\n评分：{score_context}\n"
            "输出必须严格符合以下 JSON Schema：\n{schema}\n请生成 JSON 复盘文案。",
        ),
    ]
)
