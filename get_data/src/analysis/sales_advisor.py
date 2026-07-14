# -*- coding: utf-8 -*-
"""
销售建议引擎：利用 LLM 结合项目需求与客户画像生成销售切入点建议
支持 JSONL 缓存，避免重复调用 LLM
"""

import os
import sys
import json
import hashlib
import logging
from typing import Dict, Any, Optional, List
from openai import OpenAI
from pathlib import Path

# 添加项目根目录到路径
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))

from src.config import OUTPUT_DIR

logger = logging.getLogger("sales_advisor")


class SalesSuggestionCache:
    """销售建议缓存管理器"""

    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or (OUTPUT_DIR / "sales_suggestions")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "suggestions.jsonl"

    def _generate_key(self, project_data: Dict[str, Any], customer_name: Optional[str] = None) -> str:
        """生成缓存键（基于项目关键字段的哈希）"""
        key_parts = [
            project_data.get('project_name_std', ''),
            project_data.get('buyer_name', ''),
            str(project_data.get('total_budget', '')),
            str(customer_name or ''),
        ]
        key_str = '|'.join(key_parts)
        return hashlib.md5(key_str.encode('utf-8')).hexdigest()

    def get(self, project_data: Dict[str, Any], customer_name: Optional[str] = None) -> Optional[str]:
        """从缓存获取建议，如果存在返回 None 表示未命中"""
        cache_key = self._generate_key(project_data, customer_name)

        if not self.cache_file.exists():
            return None

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if record.get('cache_key') == cache_key:
                            logger.info(f"缓存命中，返回已保存的建议")
                            return record.get('suggestions')
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.warning(f"读取缓存失败: {e}")

        return None

    def save(self, project_data: Dict[str, Any], customer_name: Optional[str], suggestions: str):
        """保存建议到缓存"""
        cache_key = self._generate_key(project_data, customer_name)

        record = {
            'cache_key': cache_key,
            'project_name': project_data.get('project_name_std', ''),
            'buyer_name': project_data.get('buyer_name', ''),
            'customer_name': customer_name,
            'suggestions': suggestions,
        }

        try:
            with open(self.cache_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
            logger.info(f"建议已保存到缓存")
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")


class SalesAdvisor:
    def __init__(self, use_cache: bool = True):
        # 从统一配置中获取 LLM 设置
        from src.config import get_llm_config
        llm_config = get_llm_config()
        self.base_url = llm_config.get("base_url", "https://api.minimaxi.com/v1")
        self.api_key = llm_config.get("api_key", "")
        self.model = llm_config.get("model", "MiniMax-M3")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=60.0
        )

        # 缓存管理器
        self.use_cache = use_cache
        self.cache = SalesSuggestionCache()

    def generate_suggestions(self, project_data: Dict[str, Any], customer_profile: Optional[Dict[str, Any]] = None, customer_name: Optional[str] = None, use_cache: bool = None) -> str:
        """
        生成销售切入点建议

        Args:
            project_data: 项目数据
            customer_profile: 客户画像数据
            customer_name: 客户名称（用于缓存键）
            use_cache: 是否使用缓存，None 时使用实例默认值
        """
        # 决定是否使用缓存
        if use_cache is None:
            use_cache = self.use_cache

        # 尝试从缓存获取
        if use_cache and self.cache:
            cached = self.cache.get(project_data, customer_name)
            if cached:
                return cached

        # 1. 组装上下文
        project_context = f"""
项目名称：{project_data.get('project_name_std')}
采购单位：{project_data.get('buyer_name')}
预算金额：{project_data.get('total_budget', '未知')}
内容摘要：{project_data.get('content_summary', '无')}
技术要点：{project_data.get('technical_requirements_summary', '无')}
应用场景：{project_data.get('application_scenario', '无')}
产品关键词：{', '.join(project_data.get('product_keywords', []))}
"""
        
        customer_context = "暂无详细画像数据"
        if customer_profile:
            customer_context = f"""
历史招标次数：{customer_profile.get('value_profile', {}).get('tender_count', 0)}
平均机会评分：{customer_profile.get('value_profile', {}).get('avg_opportunity_score', 0)}
核心技术偏好：{', '.join(customer_profile.get('demand_profile', {}).get('tech_keywords', [])[:10])}
历史中标单位：{', '.join(customer_profile.get('competitive_landscape', {}).get('past_winners', []))}
联系人：{', '.join(customer_profile.get('contact_info', {}).get('persons', []))}
"""

        system_prompt = """你是一位资深的政府/企业大客户销售专家。
请根据提供的【项目需求】和【客户画像】，为销售人员提供专业的“销售切入点建议”。

**核心指令（必须严格遵守）：**
1. **语言限制**：必须全程使用**中文**进行思考和回答。严禁输出英文建议。
2. **内容限制**：直接输出建议正文。严禁输出任何“Thinking Process”、“思考过程”、"Thinking"、"Thought" 或类似的内心独白。
3. **格式规范**：使用 Markdown 格式，确保层级清晰。
4. **结构要求**：必须包含以下四个中文标题：
   - ### 1. 需求匹配度分析
   - ### 2. 竞争策略建议
   - ### 3. 关键切入点
   - ### 4. 风险提示

请用专业、干练、实战的口吻书写。"""

        user_prompt = f"""
### 项目需求：
{project_context}

### 客户画像：
{customer_context}

请给出你的销售建议（请直接输出中文建议内容，不要包含任何英文思考过程）：
"""

        try:
            logger.info(f"正在为项目 [{project_data.get('project_name_std')}] 生成 AI 销售建议...")
            
            # 使用流式请求来观察内容产生过程
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=10000, # 增加 token 限制，防止因思考过长导致正文被截断
                stream=True
            )
            
            full_content = ""
            reasoning_content = ""
            
            for chunk in response:
                if not chunk.choices:
                    continue
                
                delta = chunk.choices[0].delta
                
                # 累加正文内容
                if hasattr(delta, 'content') and delta.content:
                    full_content += delta.content
                
                # 累加推理内容
                # 注意：如果模型正在输出推理，我们记录它但不一定返回它，或者在返回时将其剔除
                if hasattr(delta, 'reasoning') and delta.reasoning:
                    reasoning_content += delta.reasoning
                elif hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                    reasoning_content += delta.reasoning_content

            # 最终决策返回什么
            if full_content:
                # 进一步检查：有些模型会在 content 开头包含 "Thinking Process" 等字样，需要剔除
                noise_markers = [
                    "Thinking Process:", "思考过程：", "思考过程:", 
                    "Thought:", "Thought", "Thinking:", "Thinking",
                    "<thought>", "</thought>"
                ]
                cleaned_content = full_content
                
                # 循环清洗，直到找不到标记
                changed = True
                while changed:
                    changed = False
                    for marker in noise_markers:
                        if marker in cleaned_content:
                            parts = cleaned_content.split(marker)
                            # 取最后一部分，通常是正文
                            cleaned_content = parts[-1].strip()
                            changed = True
                
                # 针对截图中的特殊情况：如果结尾包含指令列表（如 * Avoid fluff...），也需要剔除
                instruction_markers = ["* Avoid fluff", "* Use sales terminology", "* Ensure no markdown errors"]
                for i_marker in instruction_markers:
                    if i_marker in cleaned_content:
                        cleaned_content = cleaned_content.split(i_marker)[0].strip()

                # 保存到缓存
                if use_cache and self.cache:
                    self.cache.save(project_data, customer_name, cleaned_content)

                return cleaned_content
            elif reasoning_content:
                logger.info("正文为空，但捕获到流式推理内容，将其作为结果返回")
                # 同样对推理内容进行清洗
                noise_markers = [
                    "Thinking Process:", "思考过程：", "思考过程:", 
                    "Thought:", "Thought", "Thinking:", "Thinking",
                    "<thought>", "</thought>"
                ]
                cleaned_reasoning = reasoning_content
                
                changed = True
                while changed:
                    changed = False
                    for marker in noise_markers:
                        if marker in cleaned_reasoning:
                            parts = cleaned_reasoning.split(marker)
                            cleaned_reasoning = parts[-1].strip()
                            changed = True
                
                # 剔除指令列表
                instruction_markers = ["* Avoid fluff", "* Use sales terminology", "* Ensure no markdown errors"]
                for i_marker in instruction_markers:
                    if i_marker in cleaned_reasoning:
                        cleaned_reasoning = cleaned_reasoning.split(i_marker)[0].strip()

                # 保存到缓存
                if use_cache and self.cache:
                    self.cache.save(project_data, customer_name, cleaned_reasoning)

                return cleaned_reasoning
            else:
                logger.error("流式请求未捕获到任何内容")
                return "AI 建议生成失败：模型未输出任何内容"
                
        except Exception as e:
            logger.error(f"生成销售建议失败: {e}")
            return f"AI 建议生成失败：{str(e)}"

if __name__ == "__main__":
    # 配置日志以在控制台查看
    logging.basicConfig(level=logging.INFO)
    
    # 简单测试
    advisor = SalesAdvisor()
    test_project = {
        "project_name_std": "智慧校园三期",
        "buyer_name": "某省重点大学",
        "total_budget": 5000000,
        "content_summary": "采购智慧黑板、录播系统等",
        "product_keywords": ["智慧黑板", "录播主机"]
    }
    print("\n[TEST] 正在生成建议...")
    result = advisor.generate_suggestions(test_project)
    print("\n[AI 建议结果]:")
    print(result)
