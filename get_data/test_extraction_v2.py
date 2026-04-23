import os
import sys
import json

# Add project root to path
project_root = os.path.abspath(os.path.join(os.getcwd()))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from src.etl.core.extract_structured import call_llm, _canonical_detail_url

def test_single_url(target_url):
    detail_json = "data/output/crawler/tenders_detail.json"
    if not os.path.exists(detail_json):
        print(f"Error: {detail_json} not found")
        return

    with open(detail_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    target_canon = _canonical_detail_url(target_url)
    item = None
    for d in data:
        if _canonical_detail_url(d.get('url')) == target_canon:
            item = d
            break
    
    if not item:
        print(f"Error: URL {target_url} not found in {detail_json}")
        return

    print(f"Found item: {item.get('title')}")
    
    input_data = {
        "project_name": item.get("title") or "",
        "publish_date": item.get("publish_date") or "",
        "content": item.get("content") or "",
        "attachment_urls": json.dumps([a.get('download_url') for a in item.get('attachments', []) if isinstance(a, dict)], ensure_ascii=False)
    }

    print("Calling LLM with REFINED PROMPT...")
    result, usage = call_llm(input_data)
    
    if result:
        print("\n=== Extraction Result ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Check specific fields
        bc = result.get('buyer_contacts', [])
        ac = result.get('agency_contacts', [])
        pc = result.get('project_contacts', [])
        
        print("\n--- Contact Verification ---")
        print(f"Buyer Contacts: {bc}")
        print(f"Agency Contacts: {ac}")
        print(f"Project Contacts: {pc}")
    else:
        print("\nExtraction failed.")

if __name__ == "__main__":
    url = "http://www.ccgp.gov.cn/cggg/dfgg/cjgg/202604/t20260414_26399445.htm"
    test_single_url(url)
