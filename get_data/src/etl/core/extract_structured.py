# -*- coding: utf-8 -*-
"""
结构化字段抽取 - 简化版
调用 LLM 抽取结构化数据，保存到 JSON 文件
"""

import json
import sys
import os
import re
import logging
from datetime import datetime
from tqdm import tqdm

try:
    from openai import OpenAI

    HAS_OPENAI = True
except ImportError:
    OpenAI = None  # type: ignore
    HAS_OPENAI = False

# 添加项目根目录和 src 目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, src_dir)
from config import (
    get_llm_config,
    CRAWLER_OUTPUT_DIR,
    ETL_OUTPUT_DIR,
)
from utils.logger import setup_logger
from crawler.crawl_detail import _canonical_detail_url


def _extract_llm_provider() -> str:
    """结构化抽取使用的 LLM 提供商键（config.LLM_PROVIDERS）。默认 deepseek官方 API。"""
    return os.environ.get("EXTRACT_LLM_PROVIDER", "deepseek").strip().lower()


# 初始化日志
logger = setup_logger('extract_structured', log_to_file=True)

SUPPORTED_MODELS = {
    'deepseek-chat': ('deepseek', 'deepseek-chat', 'DeepSeek V3'),
    'deepseek-reasoner': ('deepseek', 'deepseek-reasoner', 'DeepSeek R1'),
}

# DeepSeek 模型定价（元/1M tokens）
MODEL_PRICING = {
    'deepseek-chat': {'input_cache_hit': 0.2, 'input_cache_miss': 2.0, 'output': 3.0},
    'deepseek-reasoner': {'input_cache_hit': 0.2, 'input_cache_miss': 2.0, 'output': 3.0},
}

# DeepSeek 定价（元/1M tokens）
# 参考：https://platform.deepseek.com/pricing
# 保守估计：按缓存未命中计算（实际会有部分缓存命中）
DEEPSEEK_PRICING = {
    'input_cache_miss': 2.0,   # 输入（缓存未命中）
    'input_cache_hit': 0.2,    # 输入（缓存命中）
    'output': 3.0,             # 输出
}


class TokenCounter:
    """Token 计数器 - 支持多模型"""
    def __init__(self, model_name="deepseek-chat", estimate_cost: bool = True):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.cost = 0.0
        self.call_count = 0
        self.model_name = model_name
        self.pricing = MODEL_PRICING.get(model_name, DEEPSEEK_PRICING)
        self.estimate_cost = estimate_cost

    def add(self, usage):
        """添加一次调用的 token 使用"""
        self.prompt_tokens += usage.prompt_tokens
        self.completion_tokens += usage.completion_tokens
        self.total_tokens += usage.total_tokens
        self.call_count += 1

    def get_summary(self):
        """获取统计摘要"""
        if not self.estimate_cost:
            return {
                "model": self.model_name,
                "calls": self.call_count,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
                "cost_estimate_cny": "本地模型（未计价）",
            }
        # 根据模型定价计算费用
        if 'qwen' in self.model_name.lower():
            # 通义千问定价模式
            price_input = self.pricing.get('input', 0)
            price_output = self.pricing.get('output', 0)
            cost = (self.prompt_tokens * price_input + 
                   self.completion_tokens * price_output) / 1_000_000
            cost_str = f"{round(cost, 4)} 元"
        else:
            # DeepSeek 定价模式（缓存命中/未命中）
            price_hit = self.pricing.get('input_cache_hit', 0)
            price_miss = self.pricing.get('input_cache_miss', 0)
            price_output = self.pricing.get('output', 0)
            cost_min = (self.prompt_tokens * price_hit + 
                       self.completion_tokens * price_output) / 1_000_000
            cost_max = (self.prompt_tokens * price_miss + 
                       self.completion_tokens * price_output) / 1_000_000
            cost = (cost_min + cost_max) / 2
            cost_str = f"{round(cost, 4)} 元 (范围：{round(cost_min, 4)}-{round(cost_max, 4)})"
        
        return {
            'model': self.model_name,
            'calls': self.call_count,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'total_tokens': self.total_tokens,
            'cost_estimate_cny': cost_str,
        }


# 全局 token 计数器（默认模型会在 extract_batch 中设置）
token_counter = None


# 结构化 JSON 输出目录：data/output/etl（与 config.ETL_OUTPUT_DIR 一致）
OUTPUT_DIR = str(ETL_OUTPUT_DIR)

# 读取 prompt markdown 文档
PROMPT_MD_PATH = os.path.join(os.path.dirname(__file__), "prompt_extract.md")
if os.path.exists(PROMPT_MD_PATH):
    with open(PROMPT_MD_PATH, 'r', encoding='utf-8') as f:
        LLM_PROMPT_MD = f.read()
else:
    LLM_PROMPT_MD = ""


def format_progress_item(text, max_len=18):
    """压缩当前处理项，避免把 tqdm 进度条挤乱。"""
    text = (text or "").replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def update_progress_status(progress, skipped, success, llm_success, project_name, status):
    """保持固定进度条，仅更新右侧状态信息。"""
    current_item = format_progress_item(project_name)
    progress.set_postfix_str(
        f"状态={status} 跳过={skipped} 成功={success} LLM={llm_success} 当前={current_item}",
        refresh=True,
    )


def _effective_llm_model(model_name: str | None) -> str:
    """未指定时使用抽取所用提供商 config 中的 model。"""
    cfg = get_llm_config(_extract_llm_provider())
    return (model_name or cfg.get("model") or "").strip() or "deepseek-chat"


def call_llm(input_data, model_name: str | None = None):
    """调用 LLM 进行结构化抽取

    Args:
        input_data: 输入数据字典
        model_name: 模型 id（OpenAI 兼容）；为 None 时使用抽取提供商（默认 deepseek）的 model

    Returns:
        tuple: (llm_result, token_usage) 或 (None, None)
    """
    if not HAS_OPENAI:
        logger.error("openai 库未安装")
        return None, None

    try:
        config = get_llm_config(_extract_llm_provider())
    except ValueError as e:
        logger.error(f"获取配置失败：{e}")
        return None, None

    model = _effective_llm_model(model_name)
    api_key = config.get("api_key") or "empty"
    base_url = (config.get("base_url") or "").rstrip("/")
    timeout = config.get("timeout", 120)

    logger.info(f"LLM: base_url={base_url} model={model}")

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    # 构建输入数据字符串
    # 增加限制内容长度，确保能覆盖到结尾的联系方式。
    # 注意：如果内容过长，优先保留开头（项目信息）和结尾（联系方式）。
    full_content = input_data.get('content', '')
    if len(full_content) > 15000:
        content_text = full_content[:10000] + "\n... (内容过长，省略中间部分) ...\n" + full_content[-5000:]
    else:
        content_text = full_content
        
    input_text = f"""项目名称：{input_data.get('project_name', '')}
发布日期：{input_data.get('publish_date', '')}
附件链接：{input_data.get('attachment_urls', '[]')}
公告内容：
{content_text}"""

    # 使用 markdown prompt 文档作为 system prompt
    system_prompt = LLM_PROMPT_MD + "\n\n## 当前任务\n请根据以下输入数据，按照上述要求抽取结构化字段。\n\n## 输入数据\n" + input_text

    logger.debug(f"Prompt length: {len(system_prompt)} chars")

    # DeepSeek Chat 官方接口 max_tokens 有效范围为 [1, 8192]；本地等提供商可加大。
    prov = _extract_llm_provider()
    if prov == "deepseek":
        max_tokens = min(
            8192,
            max(1, int(os.environ.get("EXTRACT_MAX_TOKENS", "8192"))),
        )
    else:
        max_tokens = max(1, int(os.environ.get("EXTRACT_MAX_TOKENS", "40960")))

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "请严格按照输出要求返回 JSON，不要有任何额外文字。"}
            ],
            max_tokens=max_tokens,
            temperature=0.1
        )

        content_text = response.choices[0].message.content
        usage = response.usage

        logger.debug(f"API response: prompt_tokens={usage.prompt_tokens}, completion_tokens={usage.completion_tokens}")

        # 记录 token 使用
        global token_counter
        if token_counter is not None:
            token_counter.add(usage)

        # 移除 <think> 标签
        content_text = re.sub(r'<think>.*?</think>', '', content_text, flags=re.DOTALL)
        content_text = re.sub(r'<think>.*?</think>', '', content_text, flags=re.DOTALL)
        if content_text.strip().startswith('<think>') or content_text.strip().startswith(''):
            content_text = re.sub(r'^.*?{', '{', content_text, flags=re.DOTALL)

        # 提取 JSON
        start_idx = content_text.find('{')
        end_idx = content_text.rfind('}') + 1
        if start_idx != -1 and end_idx > start_idx:
            json_str = content_text[start_idx:end_idx]
            logger.info(f"LLM 抽取成功：tokens={usage.total_tokens}")
            return json.loads(json_str), usage
        logger.warning("未找到有效 JSON")
        return None, usage

    except Exception as e:
        logger.error(f"LLM 调用失败：{e}")
        return None, None


def _attachments_to_llm_field(attachments) -> str:
    """将爬虫 attachments 列表转为与 tenders.attachment_urls 相近的字符串。"""
    if not attachments:
        return "[]"
    urls = []
    for a in attachments:
        if isinstance(a, dict):
            u = a.get("download_url") or a.get("url")
            if u:
                urls.append(u)
        elif isinstance(a, str):
            urls.append(a)
    return json.dumps(urls, ensure_ascii=False)


def _load_rows_from_detail_json(json_path: str, limit: int | None):
    """从 tenders_detail.json 等爬虫产物加载行，不访问数据库。

    按 canonical detail_url 去重（与列表/详情爬虫一致），保留每条 URL 首次出现；
    limit 表示「最多加载多少条唯一 URL」；为 None 时加载全部唯一项。
    """
    path = os.path.abspath(json_path)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"详情 JSON 不存在：{path}")
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, list):
        raise ValueError(f"期望 JSON 数组，得到：{type(raw).__name__}")
    rows = []
    seen_canon: set[str] = set()
    skipped_dup = 0
    for item in raw:
        if limit is not None and len(rows) >= int(limit):
            break
        if not isinstance(item, dict):
            continue
        url = (item.get("url") or "").strip()
        if not url:
            continue
        canon = _canonical_detail_url(url) or url
        if canon in seen_canon:
            skipped_dup += 1
            continue
        seen_canon.add(canon)
        title = item.get("title") or ""
        pub = item.get("publish_date") or ""
        content = item.get("content") or ""
        att_str = _attachments_to_llm_field(item.get("attachments"))
        rows.append(
            {
                "source_url": canon,
                "project_name": title,
                "publish_date": pub,
                "content": content,
                "attachment_urls": att_str,
            }
        )
    if skipped_dup:
        logger.info(f"详情 JSON 按 URL 去重：跳过重复 {skipped_dup} 条，唯一 {len(rows)} 条")
    return rows


def _result_record_key(entry: dict) -> str:
    """与历史 tenders_structured.json 去重：source_url 用 canonical，与爬虫 URL 一致。"""
    u = (entry.get("source_url") or "").strip()
    if u:
        c = _canonical_detail_url(u) or u
        return f"url:{c}"
    return ""


def _dedupe_structured_results(results: list) -> tuple[list, int]:
    """已有输出列表按 _result_record_key 保留首次出现，去掉重复键。"""
    seen: set[str] = set()
    out: list = []
    dropped = 0
    for item in results:
        if not isinstance(item, dict):
            out.append(item)
            continue
        k = _result_record_key(item)
        if not k:
            out.append(item)
            continue
        if k in seen:
            dropped += 1
            continue
        seen.add(k)
        out.append(item)
    return out, dropped


def extract_batch(
    limit=50,
    use_llm=True,
    model_name: str | None = None,
    output_suffix=None,
    input_json_path: str | None = None,
):
    """批量抽取结构化字段，每抽取一条立即保存，已存在的数据跳过

    Args:
        limit: 处理记录数；表示最多处理多少条**唯一详情 URL**（按 canonical 去重）
        use_llm: 是否使用 LLM
        model_name: 模型 id；None 时使用抽取提供商的 model（默认 DeepSeek deepseek-chat）
        output_suffix: 输出文件后缀，用于区分不同模型的测试结果
        input_json_path: 详情 JSON（如 tenders_detail.json）路径
    """
    global token_counter
    effective_model = _effective_llm_model(model_name)
    prov = _extract_llm_provider()
    estimate_cost = prov != "local"
    token_counter = TokenCounter(
        model_name=effective_model,
        estimate_cost=estimate_cost,
    )

    logger.info("=" * 60)
    logger.info(
        f"开始抽取任务：limit={limit}, use_llm={use_llm}, "
        f"provider={prov}, model={effective_model}, "
        f"input_json={input_json_path}"
    )

    if not input_json_path:
        logger.error("未指定输入 JSON 文件路径")
        return None

    rows = _load_rows_from_detail_json(input_json_path, limit)
    logger.info(f"从 JSON 获取 {len(rows)} 条记录")

    # 根据 output_suffix 生成不同的输出文件名
    suffix = output_suffix or ""
    if suffix:
        json_path = os.path.join(OUTPUT_DIR, f"tenders_structured_{suffix}.json")
    else:
        json_path = os.path.join(OUTPUT_DIR, "tenders_structured.json")

    # 如果文件已存在，先读取已有数据（空文件或损坏 JSON 时从头开始）
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                raw = f.read().strip()
            if not raw:
                results = []
                logger.warning(f"已有输出文件为空，将覆盖写入：{json_path}")
            else:
                results = json.loads(raw)
                if not isinstance(results, list):
                    raise ValueError(
                        f"期望 JSON 数组，得到 {type(results).__name__}"
                    )
        except (json.JSONDecodeError, ValueError, OSError) as e:
            logger.warning(f"读取已有输出失败（{e}），将从头写入：{json_path}")
            results = []
        results, merge_dropped = _dedupe_structured_results(results)
        if merge_dropped:
            logger.warning(
                f"已有 tenders_structured 中存在 {merge_dropped} 条重复键，已合并为保留首条"
            )
            try:
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                logger.info(f"已写回去重后的已有数据：{json_path}")
            except OSError as e:
                logger.warning(f"写回去重结果失败：{e}")
        existing_ids = {_result_record_key(item) for item in results if _result_record_key(item)}
        logger.info(f"加载已有数据，共 {len(results)} 条（去重后）")
    else:
        results = []
        existing_ids = set()
        logger.info("未找到已有数据文件，从头开始")

    success = 0
    llm_success = 0
    skipped = 0

    progress = tqdm(
        rows,
        total=len(rows),
        desc="抽取进度",
        unit="条",
        dynamic_ncols=True,
        leave=True,
    )

    for idx, row in enumerate(progress, 1):
        rec_key = _result_record_key({"source_url": row["source_url"]})
        project_name = (row.get("project_name") or "")[:40]
        data = {
            "source_url": row["source_url"],
            "project_name": row.get("project_name") or "",
        }
        input_data = {
            "project_name": row.get("project_name") or "",
            "publish_date": row.get("publish_date") or "",
            "content": row.get("content") or "",
            "attachment_urls": row.get("attachment_urls") or "[]",
        }

        if rec_key in existing_ids:
            skipped += 1
            logger.debug(f"跳过已存在记录：{rec_key}")
            progress.set_postfix_str(
                f"跳过={skipped} 成功={success} LLM={llm_success} Token={token_counter.total_tokens}",
                refresh=True
            )
            continue

        if use_llm:
            llm_result, token_usage = call_llm(
                input_data, model_name=effective_model
            )
            if llm_result:
                data.update(llm_result)
                data["llm_model"] = effective_model
                llm_success += 1
                success += 1
                if token_usage:
                    if not token_counter.estimate_cost:
                        logger.info(
                            f"LLM 抽取成功：input={token_usage.prompt_tokens}, "
                            f"output={token_usage.completion_tokens}"
                        )
                        print(
                            f"  [TOKEN] input={token_usage.prompt_tokens} "
                            f"output={token_usage.completion_tokens} "
                            f"total={token_usage.total_tokens}"
                        )
                    else:
                        price_hit = token_counter.pricing.get('input_cache_hit', 0)
                        price_miss = token_counter.pricing.get('input_cache_miss', 0)
                        price_output = token_counter.pricing.get('output', 0)

                        if 'qwen' in effective_model.lower():
                            price_input = token_counter.pricing.get('input', 0)
                            cost = (
                                token_usage.prompt_tokens * price_input
                                + token_usage.completion_tokens * price_output
                            ) / 1_000_000
                            cost_str = f"{round(cost, 4)} 元"
                        else:
                            cost_min = (
                                token_usage.prompt_tokens * price_hit
                                + token_usage.completion_tokens * price_output
                            ) / 1_000_000
                            cost_max = (
                                token_usage.prompt_tokens * price_miss
                                + token_usage.completion_tokens * price_output
                            ) / 1_000_000
                            cost_avg = (cost_min + cost_max) / 2
                            cost_str = f"{round(cost_avg, 4)} 元 ({round(cost_min, 4)}-{round(cost_max, 4)})"

                        logger.info(
                            f"LLM 抽取成功：input={token_usage.prompt_tokens}, "
                            f"output={token_usage.completion_tokens}, cost≈{cost_str}"
                        )
                        print(
                            f"  [TOKEN] input={token_usage.prompt_tokens} "
                            f"output={token_usage.completion_tokens} "
                            f"total={token_usage.total_tokens} cost={cost_str}"
                        )
            else:
                logger.warning(f"LLM 抽取失败：{row.get('source_url', '')}")
                print(f"  [TOKEN] call failed")
        else:
            success += 1

        results.append(data)
        existing_ids.add(rec_key)

        # 立即保存到 JSON 文件
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        progress.set_postfix_str(
            f"跳过={skipped} 成功={success} LLM={llm_success} Token={token_counter.total_tokens}",
            refresh=True
        )

    logger.info(f"抽取完成：success={success}, skipped={skipped}, llm_success={llm_success}")

    # 显示 token 统计
    summary = token_counter.get_summary()
    logger.info(f"Token 统计：{summary}")

    logger.info(f"JSON 文件已保存：{json_path}")
    logger.info(f"=" * 60)

    print("="*60)
    print(f"完成！成功处理 {success}/{len(rows)} 条，跳过 {skipped} 条")
    print(f"LLM 成功：{llm_success} 条")
    print("="*60)
    print("[TOKEN Statistics]")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print("="*60)
    _log_file = next(
        (
            getattr(h, "baseFilename", None)
            for h in logger.handlers
            if getattr(h, "baseFilename", None)
        ),
        None,
    )
    print(f"[日志] 已保存到：{_log_file or '（仅控制台）'}")
    print(f"[JSON] 已保存到：{json_path}")

    return json_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description='结构化字段抽取')
    parser.add_argument('--limit', type=int, default=None, help='处理记录数')
    parser.add_argument('--all', action='store_true', help='处理所有记录')
    parser.add_argument('--test-first', action='store_true', help='仅测试第一条')
    parser.add_argument('--no-llm', action='store_true', help='不使用 LLM')
    parser.add_argument(
        '--model',
        type=str,
        default=None,
        help='模型 id（默认使用抽取提供商的 model，DeepSeek 为 deepseek-chat）',
    )
    parser.add_argument(
        '--provider',
        type=str,
        default=None,
        help='抽取用 LLM 提供商键：deepseek、local（默认 deepseek；也可用环境变量 EXTRACT_LLM_PROVIDER）',
    )
    parser.add_argument('--output-suffix', type=str, default=None, help='输出文件后缀')
    parser.add_argument(
        '--from-json',
        nargs='?',
        const='',
        default=None,
        metavar='PATH',
        help='从爬虫详情 JSON 读取并抽取；省略 PATH 时用 crawler/tenders_detail.json',
    )

    args = parser.parse_args()

    if args.provider:
        os.environ["EXTRACT_LLM_PROVIDER"] = args.provider.strip().lower()

    if args.test_first:
        limit = 1
    elif args.all:
        limit = None
    else:
        limit = args.limit

    use_llm = not args.no_llm

    # 默认从爬虫详情 JSON 读取
    input_json_path = str(CRAWLER_OUTPUT_DIR / 'tenders_detail.json')
    
    if args.from_json is not None:
        if args.from_json != '':
            input_json_path = os.path.abspath(args.from_json)

    extract_batch(
        limit=limit,
        use_llm=use_llm,
        model_name=args.model,
        output_suffix=args.output_suffix,
        input_json_path=input_json_path,
    )


if __name__ == "__main__":
    main()
