class ModelGenerationError(RuntimeError):
    """模型无法生成可用业务结果。"""


class ConfigurationError(RuntimeError):
    """运行所需配置缺失。"""

