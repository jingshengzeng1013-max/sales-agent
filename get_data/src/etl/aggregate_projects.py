import json
import os
import re
from collections import defaultdict
from datetime import datetime

def normalize_project_name(name):
    """
    标准化项目名称，去除'招标公告'、'中标公告'、'更正公告'等后缀
    """
    if not name:
        return ""
    # 去除常见的公告类型后缀
    suffixes = [
        r'公开招标公告$', r'招标公告$', r'中标公告$', r'中标（成交）结果公告$', 
        r'成交结果公告$', r'更正公告$', r'竞争性谈判公告$', r'竞争性磋商公告$',
        r'询价公告$', r'单一来源采购公示$', r'终止公告$', r'废标公告$'
    ]
    normalized = name
    for suffix in suffixes:
        normalized = re.sub(suffix, '', normalized)
    
    # 去除括号内的内容（通常是项目编号或包号）
    normalized = re.sub(r'（.*?）', '', normalized)
    normalized = re.sub(r'\(.*?\)', '', normalized)
    
    return normalized.strip()

def aggregate_projects(structured_file, detail_file, output_file):
    if not os.path.exists(structured_file):
        print(f"Error: {structured_file} not found.")
        return

    # 加载详情数据以获取日期
    url_to_date = {}
    if os.path.exists(detail_file):
        with open(detail_file, 'r', encoding='utf-8') as f:
            details = json.load(f)
            for d in details:
                if d.get('url') and d.get('publish_date'):
                    url_to_date[d['url']] = d['publish_date']

    with open(structured_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 按标准化项目名称和采购人分组
    project_groups = defaultdict(list)
    
    for item in data:
        proj_name = item.get('project_name', '')
        buyer = item.get('buyer_name_std', '')
        
        # 补充日期信息
        url = item.get('source_url')
        if url in url_to_date:
            item['publish_date'] = url_to_date[url]
        
        norm_name = normalize_project_name(proj_name)
        # 组合键：标准化名称 + 采购人 (防止重名项目)
        group_key = f"{norm_name}@{buyer}"
        project_groups[group_key].append(item)

    aggregated_projects = []

    for key, items in project_groups.items():
        # 提取基础信息（取第一条作为模板）
        base_item = items[0]
        norm_name, buyer = key.split('@')
        
        project_module = {
            "project_id": base_item.get('tender_id'), # 使用其中一个ID作为参考
            "project_name_std": norm_name,
            "buyer_name": buyer,
            "province": base_item.get('province'),
            "city": base_item.get('city'),
            "total_budget": 0,
            "status": "进行中", # 默认状态
            "events": [],
            "winning_info": None,
            "latest_update": "",
            "publish_date": base_item.get('publish_date'), # 第一个公告的日期
            "latest_publish_date": base_item.get('publish_date'), # 用于排序
            # 保留第一个文件的抽取结果
            "content_summary": base_item.get('content_summary'),
            "technical_requirements_summary": base_item.get('technical_requirements_summary'),
            "application_scenario": base_item.get('application_scenario'),
            "opportunity_score": base_item.get('opportunity_score'),
            "opportunity_reason": base_item.get('opportunity_reason'),
            "contact_person": base_item.get('contact_person'),
            "contact_phone": base_item.get('contact_phone'),
            "product_keywords": base_item.get('product_keywords', [])
        }

        # 处理所有关联公告
        for item in items:
            source_url = item.get('source_url', '')
            winning_amount = item.get('winning_amount')
            item_date = item.get('publish_date', '')
            
            # 更新项目最新日期
            if item_date and (not project_module["latest_publish_date"] or item_date > project_module["latest_publish_date"]):
                project_module["latest_publish_date"] = item_date

            # 简单判断公告类型
            event_type = "未知"
            is_winning = False
            
            # 只要有 winning_amount 就算中标 (根据用户最新规则)
            if winning_amount and winning_amount > 0:
                event_type = "中标"
                is_winning = True
                project_module["status"] = "已中标"
                project_module["winning_info"] = {
                    "bidder": item.get('winning_bidder'),
                    "amount": winning_amount,
                    "url": source_url
                }
            elif "gkzb" in source_url or "招标公告" in item.get('project_name', ''):
                event_type = "招标"
            elif "zbgg" in source_url or "中标" in item.get('project_name', ''):
                event_type = "中标"
                is_winning = True
                project_module["status"] = "已中标"
                project_module["winning_info"] = {
                    "bidder": item.get('winning_bidder'),
                    "amount": item.get('winning_amount'),
                    "url": source_url
                }
            elif "gzgg" in source_url or "更正" in item.get('project_name', ''):
                event_type = "更正"
            
            event = {
                "type": event_type,
                "title": item.get('project_name'),
                "url": source_url,
                "budget": item.get('budget_amount'),
                "winning_amount": item.get('winning_amount'),
                "date": item_date
            }
            project_module["events"].append(event)
            
            # 更新预算逻辑：除了中标外的公告，只要有金额，都视为预算金额
            if not is_winning and item.get('budget_amount'):
                project_module["total_budget"] = item.get('budget_amount')

        aggregated_projects.append(project_module)

    # 写入结果
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(aggregated_projects, f, ensure_ascii=False, indent=2)
    
    print(f"Aggregated {len(aggregated_projects)} projects into {output_file}")

if __name__ == "__main__":
    input_path = r"D:\sales_agent\get_data\data\output\etl\tenders_structured.json"
    detail_path = r"D:\sales_agent\get_data\data\output\crawler\tenders_detail.json"
    output_path = r"D:\sales_agent\get_data\data\output\etl\projects_aggregated.json"
    aggregate_projects(input_path, detail_path, output_path)
