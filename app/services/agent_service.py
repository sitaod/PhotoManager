"""
Service for running the LangChain agent within the Flask application.
"""
import os
import requests
from typing import List, Optional
from contextvars import ContextVar

from flask import current_app
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# Context variable to pass the token to the tool safely in a threaded environment
_mcp_token_ctx = ContextVar('mcp_token', default=None)

DEFAULT_MCP_URL = "http://localhost:5000/api/mcp"

class ImageSearchInput(BaseModel):
    location: Optional[str] = Field(None, description="拍摄地点关键词")
    tags: Optional[List[str]] = Field(default=None, description="标签列表，例如 ['风景', '杭州']")
    year: Optional[str] = Field(None, description="年份，例如 2024")

@tool("image_search", args_schema=ImageSearchInput)
def image_search_tool(location: Optional[str] = None, tags: Optional[List[str]] = None, year: Optional[str] = None):
    """调用后端 MCP 接口按地点、标签、年份搜索当前用户图片。"""
    token = _mcp_token_ctx.get()
    if not token:
        return "Error: MCP_AUTH_TOKEN not found in context."

    # Use the URL from config or default
    url = os.environ.get("MCP_SEARCH_URL", DEFAULT_MCP_URL)
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # 1. Initialize (Handshake)
    init_payload = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "FlaskAgentService", "version": "1.0.0"}
        },
        "id": 1
    }
    try:
        resp = requests.post(url, json=init_payload, headers=headers, timeout=5)
        if resp.status_code != 200:
            return f"MCP Initialize failed: {resp.status_code} {resp.text}"
    except Exception as e:
        return f"MCP Connection failed: {e}"

    # 2. Initialized Notification
    notify_payload = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {},
        "id": 2
    }
    requests.post(url, json=notify_payload, headers=headers, timeout=5)

    # 3. Call Tool
    call_payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "search_images",
            "arguments": {
                "location": location or "",
                "tags": tags or [],
                "year": year or ""
            }
        },
        "id": 3
    }

    try:
        response = requests.post(url, json=call_payload, headers=headers, timeout=15)
    except requests.RequestException as exc:
        return f"调用 MCP 接口失败: {exc}"

    if response.status_code != 200:
        return f"MCP 接口返回错误 {response.status_code}: {response.text}"

    try:
        data = response.json()
        if "error" in data:
            return f"MCP Error: {data['error']}"
        
        result = data.get("result", {})
        content = result.get("content", [])
        if content and isinstance(content, list):
            return content[0].get("text", "")
        return str(result)
    except ValueError:
        return response.text

def run_agent_chat(prompt: str, token: str) -> str:
    """
    Run the agent with the given prompt and user token.
    """
    # Set the token in the context variable
    token_token = _mcp_token_ctx.set(token)
    
    try:
        api_key = current_app.config.get('QWEN_API_KEY') or os.environ.get('API_KEY')
        base_url = current_app.config.get('QWEN_BASE_URL')
        model_name = current_app.config.get('QWEN_MODEL', 'qwen-flash')

        llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=0.1,
        )
        
        tools = [image_search_tool]

        # LangGraph Construction
        from langgraph.graph import StateGraph, END
        from langgraph.prebuilt import ToolNode
        from typing import TypedDict, Annotated, Sequence
        import operator
        from langchain_core.messages import BaseMessage

        class AgentState(TypedDict):
            messages: Annotated[Sequence[BaseMessage], operator.add]

        def should_continue(state):
            messages = state['messages']
            last_message = messages[-1]
            if last_message.tool_calls:
                return "tools"
            return END

        def call_model(state):
            messages = state['messages']
            response = llm.bind_tools(tools).invoke(messages)
            return {"messages": [response]}

        workflow = StateGraph(AgentState)
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", ToolNode(tools))

        workflow.set_entry_point("agent")
        workflow.add_conditional_edges("agent", should_continue)
        workflow.add_edge("tools", "agent")

        agent_executor = workflow.compile()

        # Run the agent
        system_prompt = "你是一个智能图片助手。当搜索到图片时，请务必使用 Markdown 图片语法 `![描述](url)` 展示图片，不要只给出链接。"
        inputs = {"messages": [("system", system_prompt), ("user", prompt)]}
        result = agent_executor.invoke(inputs)
        messages = result.get("messages", [])
        if messages:
            return messages[-1].content
        return "(无响应)"

    except Exception as e:
        return f"Agent execution error: {str(e)}"
    finally:
        # Reset the token context
        _mcp_token_ctx.reset(token_token)
