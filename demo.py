import openai
import json
import time
import random
from typing import Dict
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
import json
from openai import OpenAI
from rich import print 
from NetworkSearch import XhsWorkSearch
import sys
import os
import threading
import itertools
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.live import Live
from rich.text import Text
from rich.table import Table
from tavily import TavilyClient

console = Console()
xhs_search_api = XhsWorkSearch()

client = OpenAI(api_key='XXX', base_url="https://xxxxx") ###自己设置LLM的请求key和方式

os.environ['TAVILY_API_KEY']='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'    # travily搜索引擎api key
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


# ======== 定义 Tool Schema ========
tools = [
    {
        "type": "function",  # 必须有这个字段
        "function": {
            "name": "xhs_search",
            "description": "在小红书上搜索相关内容，主要是检索和租赁领域 以及3c商品相关的请求",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索的小红书关键词或短语"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",  # 必须有这个字段
        "function": {
            "name": "web_search",
            "description": "在网络平台进行搜索，主要是新闻相关的信息检索",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "网页新闻搜索的关键词或短语"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的天气信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "温度单位"
                    }
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "进行基本的数学计算",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["add", "subtract", "multiply", "divide"],
                        "description": "操作类型"
                    },
                    "a": {
                        "type": "number",
                        "description": "第一个数字"
                    },
                    "b": {
                        "type": "number",
                        "description": "第二个数字"
                    }
                },
                "required": ["operation", "a", "b"]
            }
        }
    }
]

# ======== 模拟的小红书知识库检索工具 =========
def xhs_search(query: str) -> Dict:
    result = xhs_search_api.get_search_data_by_batch([query],3,200)
    result = [r["title"] + ' ' + r["content"] for r in result]
    return {
        "query": query,
        "results": result
    }

# ======== web检索工具 =========
def web_search(query:str)->Dict:
    result = tavily_client.search(query, max_results=3)
    return {
        "query": query,
        "results": result
    }

# 实现工具函数
def get_weather(city: str, unit: str = "celsius") -> dict:
    """模拟获取天气"""
    weather_data = {
        "beijing": {"temp": 25, "condition": "晴天"},
        "shanghai": {"temp": 28, "condition": "多云"},
        "guangzhou": {"temp": 32, "condition": "热"}
    }
    
    city_lower = city.lower()
    if city_lower in weather_data:
        data = weather_data[city_lower]
        temp = data["temp"]
        
        if unit == "fahrenheit":
            temp = temp * 9/5 + 32
        
        return {
            "city": city,
            "temperature": temp,
            "unit": unit,
            "condition": data["condition"]
        }
    else:
        return {"error": f"找不到城市 {city} 的天气信息"}

def calculate(operation: str, a: float, b: float) -> dict:
    """执行计算操作"""
    operations = {
        "add": lambda x, y: x + y,
        "subtract": lambda x, y: x - y,
        "multiply": lambda x, y: x * y,
        "divide": lambda x, y: x / y if y != 0 else "错误：除数不能为零"
    }
    
    if operation not in operations:
        return {"error": f"未知的操作: {operation}"}
    
    result = operations[operation](a, b)
    return {
        "operation": operation,
        "a": a,
        "b": b,
        "result": result
    }


# 绿色 ANSI 样式 流式输出
GREEN_BOLD = "\033[1;32m"
RESET = "\033[0m"
def typewriter_output(text: str, delay: float = 0.03):
    sys.stdout.write(GREEN_BOLD)  # 开始绿色加粗
    sys.stdout.flush()
    for char in text:
        sys.stdout.write(char)  # 不换行
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write(RESET + "\n")  # 重置颜色并换行
    sys.stdout.flush()


# ======= 动画工具函数 =======
def spinner_animation(message: str, stop_event: threading.Event):
    spinner = itertools.cycle(['|', '/', '-', '\\'])
    while not stop_event.is_set():
        sys.stdout.write(f"\r{message} {next(spinner)}")
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write("\r" + " " * (len(message) + 2) + "\r")  # 清除动画行


# ======== Agent ========
class ResearchAgent:
    def __init__(self, max_rounds=5):
        self.max_rounds = max_rounds
        self.history_results = []
        self.conversation_history = []

    def chat_and_maybe_call_tool(self, user_prompt: str) -> str:
        """发送prompt，让模型自主选择是否调用工具"""
        self.conversation_history.append({"role": "user", "content": user_prompt})

        with Progress(SpinnerColumn(),TextColumn("[cyan]    🤖 模型正在思考..."),TimeElapsedColumn(),console=console) as progress:
            progress.add_task("thinking", total=None, start=True)
            ##请求模型
            resp = client.chat.completions.create(
                model="DeepSeek-V3",
                messages=self.conversation_history,
                tools=tools,
                tool_choice="auto"
            )
        msg = resp.choices[0].message

        # 如果模型要求调用工具
        if msg.tool_calls:
            # 将 assistant（包含 tool_calls）加入到 conversation_history
            self.conversation_history.append({
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in msg.tool_calls
                ]
            })

            for tool_call in msg.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)    
                ##安全参数
                param_str = json.dumps(tool_args, ensure_ascii=False)
                with Progress(SpinnerColumn(),
                              TextColumn("[yellow]🔍 调用工具中 ..."),
                              TimeElapsedColumn(),console=console) as progress:
                    progress.add_task(f"[yellow]🔧 调用工具 {tool_name} 参数: {param_str}", total=None, start=True)

                    # === 根据工具名字调用 ===
                    if tool_name == "xhs_search":
                        search_res = xhs_search(tool_args["query"])
                        self.history_results.append({"query": tool_args["query"],"results":search_res})

                    elif tool_name == "get_weather":
                        tool_input = json.loads(tool_call.function.arguments)
                        search_res = get_weather(**tool_input)
                        # self.history_results.append({"query": tool_args["query"],"results":search_res})
                    elif tool_name == "web_search":
                        search_res = web_search(tool_args["query"])
                        self.history_results.append({"query": tool_args["query"],"results":search_res})
                    else:
                        search_res = {"error": "未知工具"}
                console.print(f"[bold magenta]📊 工具返回结果:[/bold magenta] {search_res}")

                # 返回工具结果给模型
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(search_res, ensure_ascii=False)
                })

            # 再让模型基于工具结果回复
            with Progress(
                SpinnerColumn(),
                TextColumn("[green]📄 模型正在整理结果..."),
                TimeElapsedColumn(),
                console=console
            ) as progress:
                progress.add_task("thinking", total=None, start=True)
                follow_resp = client.chat.completions.create(
                    model="DeepSeek-V3",
                    messages=self.conversation_history,
                    tools=tools,
                    tool_choice="auto"
                )

            reply = follow_resp.choices[0].message.content
            self.conversation_history.append({"role": "assistant", "content": reply})
            console.print("\n[bold green]💡 模型输出:[/bold green]")
            typewriter_output(reply)
            return reply
        else:
            # 没调用工具，直接返回
            reply = msg.content
            self.conversation_history.append({"role": "assistant", "content": reply})
            console.print("\n[bold green]💡 模型输出:[/bold green]")
            typewriter_output(reply)

            return reply

    def final_report(self):
        """生成最终调研报告"""
        console.rule("[bold magenta]📑 最终调研总结报告[/bold magenta]")

        # 用 rich table 展示结果
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("检索关键词", style="cyan")
        table.add_column("检索结果", style="green")

        # for item in self.history_results:
        #     query = item["query"]
        #     results_text = "\n".join(item["results"])
        #     table.add_row(query, results_text)
        # console.print(table)

        # AI 自动总结
        summary_prompt = f"请根据以下检索结果，总结关键结论：\n{self.history_results}"
        try:
            resp = client.chat.completions.create(
                model="DeepSeek-V3",
                messages=[{"role": "user", "content": summary_prompt}]
            )
            ai_summary = resp.choices[0].message.content
            console.print("\n[bold yellow]📌 AI 总结:[/bold yellow]")
            typewriter_output(ai_summary, delay=0.015)
        except Exception as e:
            console.print(f"[red]生成总结失败: {e}[/red]")


    def run(self, user_query: str):
        round_num = 0
        while round_num < self.max_rounds:
            round_num += 1
            console.rule(f"[bold cyan]=== 调研轮次 {round_num} ===")
            current_time = time.localtime()
            reply = self.chat_and_maybe_call_tool(
                f"当前时间是: {current_time},用户的调研主题是: {user_query}。请规划下一步的搜索或分析，并在需要时调用合适的工具。"
            )
            print(f"[模型回复]\n{reply}")
            print("##############")
            
            # 可以在这里加: 解析模型的指令，决定是否结束
            if "完成调研" in reply or "finish: true" in reply:
                print("\n[完成] 已满足调研需求")
                break
        self.final_report()

if __name__ == "__main__":
    agent = ResearchAgent(max_rounds=3)
    query_input = input("请输入第一次调研主题: ").strip()
    agent.run(query_input)