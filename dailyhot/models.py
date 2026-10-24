"""数据模型：热榜条目"""

from dataclasses import dataclass


@dataclass
class HotItem:
    """
    一条热榜内容

    Attributes:
        rank: 榜内名次（1 起）
        title: 标题文本
        url: 可跳转链接（部分源无稳定链接时为空串）
        score: 热度值（各源格式不一，保留原样字符串，如 "1234 万热度"）
    """

    rank: int
    title: str
    url: str = ""
    score: str | None = None

    def to_dict(self) -> dict:
        return {"rank": self.rank, "title": self.title, "url": self.url, "score": self.score}
