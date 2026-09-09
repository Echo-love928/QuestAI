class ModelGenerationError(RuntimeError):
    """模型无法生成可用业务结果。"""


class ConfigurationError(RuntimeError):
    """运行所需配置缺失。"""


class ResearchError(RuntimeError):
    """联网研究阶段无法产出可用证据。"""


class ResearchUnavailable(ResearchError):
    """联网研究服务暂时不可用。"""


class SearchUnavailable(ResearchUnavailable):
    """搜索服务暂时不可用。"""


class ExtractUnavailable(ResearchUnavailable):
    """网页提取服务暂时不可用。"""


class EvidenceInsufficient(ResearchError):
    """取得的资料不足以支持出题。"""


class TopicAmbiguous(ResearchError):
    """资料无法消解主题歧义。"""


class ResearchBudgetExceeded(ResearchError):
    """联网研究达到本次安全预算。"""
