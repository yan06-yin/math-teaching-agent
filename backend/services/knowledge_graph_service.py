"""
跨学科知识图谱服务

构建学生知识点掌握度的知识图谱，支持：
- 跨学科薄弱点关联分析
- 知识点前置关系追踪
- 自适应学习路径推荐
- 精准推题

使用轻量级内存图结构（NetworkX 风格），无需额外数据库。
"""

import json
import logging
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)


# ===== 知识点前置关系定义 =====
# 跨学科知识关联图谱（静态定义）
KNOWLEDGE_PREREQUISITES = {
    # === 数学 ===
    "有理数运算": [],
    "一元一次方程": ["有理数运算"],
    "二元一次方程组": ["一元一次方程"],
    "一元二次方程": ["一元一次方程", "因式分解"],
    "因式分解": ["代数式与整式"],
    "函数基础": ["一元一次方程"],
    "一次函数": ["函数基础"],
    "二次函数": ["一元二次方程", "一次函数"],
    "反比例函数": ["函数基础"],
    "平面几何基础": [],
    "全等三角形": ["平面几何基础", "三角形"],
    "相似三角形": ["全等三角形"],
    "勾股定理": ["三角形", "平方运算"],
    "四边形": ["平面几何基础"],
    "圆": ["三角形", "四边形"],
    "概率基础": ["数据的收集与整理"],
    # === 语文 ===
    "字音字形": [],
    "词语理解": ["字音字形"],
    "语言运用-病句修改": ["词语理解"],
    "语言运用-修辞手法": ["词语理解"],
    "现代文阅读": ["词语理解"],
    "文言文阅读": ["字音字形", "词语理解"],
    "古诗词鉴赏": ["字音字形"],
    "作文-记叙文": ["现代文阅读", "语言运用-修辞手法"],
    "作文-议论文": ["现代文阅读", "作文-记叙文"],
    # === 英语 ===
    "英语-词汇": [],
    "英语-时态-一般现在时": ["英语-词汇"],
    "英语-时态-一般过去时": ["英语-时态-一般现在时"],
    "英语-时态-现在完成时": ["英语-时态-一般过去时"],
    "英语-时态-一般将来时": ["英语-时态-一般现在时"],
    "英语-语态-被动语态": ["英语-时态-一般过去时"],
    "英语-从句-定语从句": ["英语-时态-一般现在时"],
    "英语-写作": ["英语-时态-一般现在时", "英语-词汇"],
    # === 跨学科关联 ===
    "数学-逻辑推理": [],
    "语文-议论文论证": ["数学-逻辑推理"],  # 逻辑推理能力跨学科迁移
}

# 跨学科关联映射
CROSS_SUBJECT_LINKS = [
    ("数学逻辑推理", "全等三角形", "数学证明与逻辑推理"),
    ("数学逻辑推理", "语文-议论文论证", "逻辑推理能力可迁移至议论文写作"),
    ("一次函数", "数据分析", "函数思维有助于数据分析"),
    ("数据分析", "统计", "数据处理能力是统计分析的基础"),
]


class KnowledgeGraphNode:
    """知识图谱节点"""

    def __init__(self, name: str, subject: str = "math", level: str = "初中"):
        self.name = name
        self.subject = subject
        self.level = level
        self.error_count = 0
        self.total_attempts = 0
        self.mastery = 1.0  # 掌握度 0-1
        self.children = []
        self.parents = []

    @property
    def error_rate(self) -> float:
        if self.total_attempts == 0:
            return 0
        return self.error_count / self.total_attempts

    def update_mastery(self):
        """根据错误率更新掌握度"""
        if self.total_attempts == 0:
            self.mastery = 1.0
        else:
            # 掌握度 = 1 - (错误数 / 总尝试数) * 衰减因子
            raw = 1 - (self.error_count / max(self.total_attempts, 1)) * 1.2
            self.mastery = max(0, min(1, raw))

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "subject": self.subject,
            "level": self.level,
            "mastery": round(self.mastery, 2),
            "error_count": self.error_count,
            "total_attempts": self.total_attempts,
            "error_rate": round(self.error_rate, 2),
        }


class KnowledgeGraph:
    """知识图谱"""

    def __init__(self):
        self.nodes: dict[str, KnowledgeGraphNode] = {}
        self._build_static_graph()

    def _build_static_graph(self):
        """根据前置关系构建静态图"""
        for name, prereqs in KNOWLEDGE_PREREQUISITES.items():
            if name not in self.nodes:
                subject = self._guess_subject(name)
                self.nodes[name] = KnowledgeGraphNode(name, subject)
            for prereq in prereqs:
                if prereq not in self.nodes:
                    subj = self._guess_subject(prereq)
                    self.nodes[prereq] = KnowledgeGraphNode(prereq, subj)
                self.nodes[name].parents.append(self.nodes[prereq])
                self.nodes[prereq].children.append(self.nodes[name])

    def _guess_subject(self, name: str) -> str:
        """根据知识点名称猜测学科"""
        if name.startswith("英语-"):
            return "english"
        if name.startswith("语文-") or any(kw in name for kw in ["作文", "阅读", "文言", "古诗", "修辞"]):
            return "chinese"
        if name.startswith("数学-"):
            return "math"
        return "math"

    def get_or_create_node(self, name: str, subject: str = "math",
                           level: str = "初中") -> KnowledgeGraphNode:
        """获取或创建节点"""
        if name not in self.nodes:
            self.nodes[name] = KnowledgeGraphNode(name, subject, level)
        return self.nodes[name]

    def record_error(self, knowledge_point: str, subject: str = "math",
                     level: str = "初中", count: int = 1):
        """记录一次错误"""
        node = self.get_or_create_node(knowledge_point, subject, level)
        node.error_count += count
        node.total_attempts += count
        node.update_mastery()
        # 级联更新前置知识点
        self._cascade_update(node)

    def record_correct(self, knowledge_point: str, subject: str = "math",
                       level: str = "初中"):
        """记录一次正确"""
        node = self.get_or_create_node(knowledge_point, subject, level)
        node.total_attempts += 1
        node.update_mastery()

    def _cascade_update(self, node: KnowledgeGraphNode, depth: int = 0):
        """级联更新：前置知识点掌握度影响后续知识点"""
        if depth > 3:
            return
        for child in node.children:
            # 父节点掌握度低 → 子节点掌握度也受影响
            if node.mastery < 0.6:
                child.mastery = min(child.mastery, node.mastery * 1.1)
            self._cascade_update(child, depth + 1)

    def get_weak_points(self, subject: Optional[str] = None,
                        threshold: float = 0.7, top_n: int = 5) -> list[dict]:
        """获取薄弱知识点"""
        weak = []
        for node in self.nodes.values():
            if subject and node.subject != subject:
                continue
            if node.mastery < threshold and node.total_attempts > 0:
                weak.append(node.to_dict())
        weak.sort(key=lambda x: x["mastery"])
        return weak[:top_n]

    def get_strong_points(self, subject: Optional[str] = None,
                          threshold: float = 0.9, top_n: int = 3) -> list[dict]:
        """获取优势知识点"""
        strong = []
        for node in self.nodes.values():
            if subject and node.subject != subject:
                continue
            if node.mastery >= threshold and node.total_attempts > 0:
                strong.append(node.to_dict())
        strong.sort(key=lambda x: -x["mastery"])
        return strong[:top_n]

    def get_learning_path(self, target_point: str) -> list[str]:
        """获取从基础到目标知识点的学习路径"""
        if target_point not in self.nodes:
            return [target_point]

        # BFS 从目标点反向查找前置路径
        visited = set()
        path = []
        queue = [(target_point, [target_point])]

        while queue:
            current, current_path = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            node = self.nodes[current]
            if not node.parents:
                # 到达根节点
                path = current_path
                break
            for parent in node.parents:
                new_path = [parent.name] + current_path
                queue.append((parent.name, new_path))

        return path if path else [target_point]

    def get_cross_subject_insights(self) -> list[dict]:
        """获取跨学科关联分析洞察"""
        insights = []
        for subj_a, subj_b, desc in CROSS_SUBJECT_LINKS:
            node_a = self.nodes.get(subj_a)
            node_b = self.nodes.get(subj_b)
            if node_a and node_b and node_a.mastery < 0.7:
                insights.append({
                    "from": subj_a,
                    "to": subj_b,
                    "description": desc,
                    "from_mastery": round(node_a.mastery, 2),
                    "to_mastery": round(node_b.mastery, 2),
                })
        return insights

    def to_dict(self) -> dict:
        """导出完整图谱"""
        return {
            "nodes": {name: node.to_dict() for name, node in self.nodes.items()},
            "weak_points": self.get_weak_points(),
            "cross_subject_insights": self.get_cross_subject_insights(),
        }


class KnowledgeGraphService:
    """知识图谱服务 - 管理学生知识图谱"""

    def __init__(self):
        # 学生ID → KnowledgeGraph 的映射
        self._graphs: dict[int, KnowledgeGraph] = {}

    def get_or_create_graph(self, student_id: int) -> KnowledgeGraph:
        """获取或创建学生知识图谱"""
        if student_id not in self._graphs:
            self._graphs[student_id] = KnowledgeGraph()
        return self._graphs[student_id]

    async def load_from_db(self, student_id: int, db_session):
        """从数据库加载学生错误记录到知识图谱"""
        from models import ErrorRecord
        from sqlalchemy import select

        graph = self.get_or_create_graph(student_id)

        result = await db_session.execute(
            select(ErrorRecord).filter(ErrorRecord.student_id == student_id)
        )
        for record in result.scalars().all():
            # 根据知识点名称推测学科
            subject = "math"
            if record.knowledge_point:
                kp_lower = record.knowledge_point.lower()
                if any(kw in kp_lower for kw in ["作文", "阅读", "文言", "古诗", "修辞", "病句", "成语"]):
                    subject = "chinese"
                elif any(kw in kp_lower for kw in ["时态", "语态", "从句", "英语-"]):
                    subject = "english"

            graph.record_error(
                knowledge_point=record.knowledge_point,
                subject=subject,
                count=record.error_count or 1,
            )

        return graph

    def get_weak_points(self, student_id: int, subject: Optional[str] = None,
                        top_n: int = 5) -> list[dict]:
        """获取学生薄弱知识点"""
        graph = self._graphs.get(student_id)
        if not graph:
            return []
        return graph.get_weak_points(subject=subject, top_n=top_n)

    def get_strong_points(self, student_id: int, subject: Optional[str] = None,
                          top_n: int = 3) -> list[dict]:
        """获取学生优势知识点"""
        graph = self._graphs.get(student_id)
        if not graph:
            return []
        return graph.get_strong_points(subject=subject, top_n=top_n)

    def get_cross_subject_insights(self, student_id: int) -> list[dict]:
        """获取跨学科分析洞察"""
        graph = self._graphs.get(student_id)
        if not graph:
            return []
        return graph.get_cross_subject_insights()

    def get_learning_path(self, student_id: int, target_point: str) -> list[str]:
        """获取学习路径"""
        graph = self._graphs.get(student_id)
        if not graph:
            return [target_point]
        return graph.get_learning_path(target_point)


# 全局单例
knowledge_graph_service = KnowledgeGraphService()