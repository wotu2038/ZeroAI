"""
Prompt模板
"""
from typing import List, Dict, Any, Optional


def build_generation_prompt(
    user_query: str,
    retrieved_content: List[Dict[str, Any]],
    new_requirement: Optional[Dict[str, Any]],
    similar_requirements: List[Dict[str, Any]]
) -> str:
    """构建文档生成Prompt"""
    
    # 构建检索内容部分
    retrieved_section = ""
    if retrieved_content:
        retrieved_section = "## 相关参考内容（从知识库检索）\n\n"
        for idx, item in enumerate(retrieved_content[:10], 1):  # 最多使用前10条
            retrieved_section += f"### 参考内容 {idx}\n"
            retrieved_section += f"**类型**: {item.get('type', 'unknown')}\n"
            retrieved_section += f"**相关性**: {item.get('score', 0):.2f}\n"
            retrieved_section += f"**内容**:\n{item.get('content', '')}\n\n"
    
    # 构建相似需求部分
    similar_section = ""
    if similar_requirements:
        similar_section = "## 相似历史需求文档（供参考）\n\n"
        for req in similar_requirements[:5]:
            similar_section += f"- **{req.get('name', '')}** (版本: {req.get('version', 'N/A')})\n"
            similar_section += f"  {req.get('description', req.get('content', '')[:200])}\n\n"
    
    # 构建新需求部分
    new_req_section = ""
    if new_requirement:
        new_req_section = f"""
## 新需求信息
- **需求名称**: {new_requirement.get('name', '')}
- **需求描述**: {new_requirement.get('description', new_requirement.get('content', '')[:500])}
- **版本号**: {new_requirement.get('version', 'v1.0')}
"""
    else:
        new_req_section = f"""
## 用户需求描述
{user_query}
"""
    
    prompt = f"""你是一个专业的需求文档编写专家。请根据以下信息生成一份完整的需求规格说明书。

{new_req_section}

{retrieved_section}

{similar_section}

## 生成要求
1. **充分利用检索到的参考内容**：将检索到的相关内容整合到文档中，确保文档的准确性和完整性
2. **参考历史需求的文档结构和格式**：保持与历史需求文档一致的风格
3. **结合新需求的特点**：根据用户需求描述，生成符合实际需求的文档
4. **包含以下章节**：
   - 文档信息（版本号、编写日期等）
   - 项目概述（背景、定位、技术架构）
   - 系统架构
   - 功能需求详细说明（按模块组织）
   - 数据模型
   - 非功能性需求
5. **保持专业、清晰、完整的风格**
6. **使用 Markdown 格式**

请生成完整的需求文档。"""
    
    return prompt


def build_review_prompt(document: str) -> str:
    """构建文档评审Prompt"""
    prompt = f"""你是一个专业的需求文档评审专家。请对以下需求文档进行评审，从以下维度评分（0-100分），并给出改进建议。

## 评审维度
1. **完整性（Completeness）**：文档是否包含所有必要章节和信息
2. **准确性（Accuracy）**：需求描述是否准确，是否符合实际需求
3. **一致性（Consistency）**：文档格式、术语使用是否一致
4. **可读性（Readability）**：文档表达是否清晰，是否易于理解

## 待评审文档
{document}

## 输出要求
请以JSON格式输出评审结果，格式如下：
{{
  "overall_score": 85.0,
  "completeness_score": 90.0,
  "accuracy_score": 85.0,
  "consistency_score": 80.0,
  "readability_score": 85.0,
  "issues": [
    "问题1描述",
    "问题2描述"
  ],
  "suggestions": [
    "改进建议1",
    "改进建议2"
  ]
}}

只返回JSON，不要其他内容。"""
    
    return prompt


def build_optimization_prompt(
    document: str,
    review_report: Dict[str, Any]
) -> str:
    """构建文档优化Prompt"""
    issues = review_report.get("issues", [])
    suggestions = review_report.get("suggestions", [])
    scores = {
        "completeness": review_report.get("completeness_score", 0),
        "accuracy": review_report.get("accuracy_score", 0),
        "consistency": review_report.get("consistency_score", 0),
        "readability": review_report.get("readability_score", 0)
    }
    
    issues_text = "\n".join([f"- {issue}" for issue in issues]) if issues else "无"
    suggestions_text = "\n".join([f"- {suggestion}" for suggestion in suggestions]) if suggestions else "无"
    
    prompt = f"""你是一个专业的需求文档优化专家。请根据评审结果优化以下需求文档。

## 当前文档
{document}

## 评审结果
### 各维度评分
- 完整性: {scores['completeness']:.1f}/100
- 准确性: {scores['accuracy']:.1f}/100
- 一致性: {scores['consistency']:.1f}/100
- 可读性: {scores['readability']:.1f}/100

### 发现的问题
{issues_text}

### 改进建议
{suggestions_text}

## 优化要求
1. **针对性地解决评审中发现的问题**
2. **采纳改进建议，提升文档质量**
3. **保持文档的原有结构和核心内容**
4. **确保优化后的文档更加完整、准确、一致、易读**
5. **使用 Markdown 格式**

请输出优化后的完整文档。"""
    
    return prompt

