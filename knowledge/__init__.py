"""Knowledge Layer。

AI-Lab 的外部知识系统层，负责接入、管理、检索所有外部知识。
遵循 RFC-004 定义的 Knowledge Layer 架构。

五种知识类型：
- Document Knowledge：文档知识（PDF/Markdown/HTML/CSV）
- Entity Knowledge：实体知识（人/公司/概念/产品）
- Relation Knowledge：关系知识（实体间语义关系）
- Experiential Knowledge：经验知识（Best Practice/方法论）
- Decision Knowledge：决策知识（历史决策记录）

使用方式：
    from knowledge import KnowledgeManager
    from knowledge.models.document import DocumentKnowledge

    km = KnowledgeManager()
    result = await km.search(query="行业分析报告")
"""

__version__ = "0.1.0"
