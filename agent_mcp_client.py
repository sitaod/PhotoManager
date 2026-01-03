"""Demo agent that calls the MCP search endpoint with JWT auth."""
import os
from typing import List, Optional

from dotenv import load_dotenv
import requests
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# Load environment variables from .env file
load_dotenv()


DEFAULT_MCP_URL = "http://localhost:5000/api/mcp"


class ImageSearchInput(BaseModel):
    location: Optional[str] = Field(None, description="拍摄地点关键词")
    tags: Optional[List[str]] = Field(default=None, description="标签列表，例如 ['风景', '杭州']")
    year: Optional[str] = Field(None, description="年份，例如 2024")


@tool("image_search", args_schema=ImageSearchInput)
def image_search_tool(location: Optional[str] = None, tags: Optional[List[str]] = None, year: Optional[str] = None):
    """调用后端 MCP 接口按地点、标签、年份搜索当前用户图片。"""
    token = os.getenv("MCP_AUTH_TOKEN")
    if not token:
        return "缺少环境变量 MCP_AUTH_TOKEN"

    url = os.getenv("MCP_SEARCH_URL", DEFAULT_MCP_URL)
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
            "clientInfo": {"name": "LangChainAgent", "version": "1.0.0"}
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
        # Extract content from result
        result = data.get("result", {})
        content = result.get("content", [])
        if content and isinstance(content, list):
            return content[0].get("text", "")
        return str(result)
    except ValueError:
        return response.text


def build_agent():
    llm = ChatOpenAI(
        model=os.getenv("QWEN_MODEL", "qwen-flash"),
        api_key=os.getenv("API_KEY"),
        base_url=os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        temperature=0.1,
    )
    tools = [image_search_tool]

    # 0) Prefer LangGraph (modern standard)
    try:
        from langgraph.prebuilt import create_react_agent
        return create_react_agent(llm, tools)
    except ImportError as e:
        print(f"Attempt 0 (LangGraph) failed: {e}")
        pass

    # 1) Prefer OpenAI function-calling style agent (works with qwen OpenAI-compatible API)
    try:
        from langchain.agents import AgentExecutor
        try:
            from langchain.agents import create_openai_tools_agent
        except ImportError:
            from langchain.agents.openai import create_openai_tools_agent  # type: ignore
        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "你是一个图片搜索助手，根据用户需求调用可用工具来检索图片。"),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        agent = create_openai_tools_agent(llm=llm, tools=tools, prompt=prompt)
        return AgentExecutor(agent=agent, tools=tools, verbose=True)
    except ImportError as e:
        print(f"Attempt 1 (OpenAI Tools Agent) failed: {e}")
        pass
    except Exception as e:
        print(f"Attempt 1 (OpenAI Tools Agent) unexpected error: {e}")
        pass

    # 2) React agent fallback (multiple import paths for compatibility)
    try:
        try:
            from langchain.agents import create_react_agent
        except ImportError:
            from langchain.agents.react.agent import create_react_agent  # type: ignore

        try:
            from langchain.agents import AgentExecutor
        except ImportError:
            from langchain.agents.agent import AgentExecutor  # type: ignore

        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "你是一个图片搜索助手，根据用户需求调用可用工具来检索图片。"),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)
        return AgentExecutor(agent=agent, tools=tools, verbose=True)
    except ImportError as e:
        print(f"Attempt 2 (React Agent) failed: {e}")
        pass
    except Exception as e:
        print(f"Attempt 2 (React Agent) unexpected error: {e}")
        pass

    # 3) Legacy initialize_agent fallback
    try:
        from langchain.agents import AgentType, initialize_agent

        return initialize_agent(
            tools=tools,
            llm=llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True,
        )
    except ImportError as e:
        print(f"Attempt 3 (Legacy initialize_agent) failed: {e}")
        pass
    except Exception as e:
        print(f"Attempt 3 (Legacy initialize_agent) unexpected error: {e}")
        pass

    # 4) Last-resort minimal wrapper: directly call the tool using structured args (no LLM routing)
    class DirectToolAgent:
        def invoke(self, inputs):
            data = inputs if isinstance(inputs, dict) else {"input": str(inputs)}
            # naive parse: not attempting NL understanding; just signal unsupported
            return "当前环境缺少 langchain agent 组件，请升级 langchain/langchain-openai 或使用 legacy initialize_agent。"

        def run(self, query):
            return self.invoke({"input": query})

    return DirectToolAgent()


def main():
    agent = build_agent()
    prompt = "帮我找和雀魂麻将相关的照片"
    
    # Check if it's a LangGraph agent (CompiledGraph)
    is_langgraph = hasattr(agent, "stream") and not hasattr(agent, "agent") # AgentExecutor has .agent
    
    if is_langgraph:
        print("Using LangGraph agent...")
        inputs = {"messages": [("user", prompt)]}
        # stream() yields steps, invoke() returns final state
        result = agent.invoke(inputs)
        # Extract last message content
        messages = result.get("messages", [])
        if messages:
            print("Agent 输出:", messages[-1].content)
        else:
            print("Agent 输出: (无响应)")
    else:
        print("Using LangChain AgentExecutor...")
        try:
            result = agent.invoke({"input": prompt})
            # AgentExecutor returns a dict with "output" usually
            if isinstance(result, dict) and "output" in result:
                print("Agent 输出:", result["output"])
            else:
                print("Agent 输出:", result)
        except AttributeError:
            # Legacy agents return a run() method
            result = agent.run(prompt)
            print("Agent 输出:", result)



if __name__ == "__main__":
    main()
