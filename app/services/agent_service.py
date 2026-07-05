"""
Service for running the LangChain agent within the Flask application.
"""
import json
import os
from datetime import datetime
from typing import Any, List, Optional

from flask import current_app
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, field_validator

from app.services.image_search_service import search_images_for_user
from app.services.semantic_search_service import SemanticSearchError, semantic_search_images_for_user


def _agent_log(message: str) -> None:
    """Print agent progress immediately to the Flask terminal."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[Agent {timestamp}] {message}", flush=True)


def _preview(value: object, max_length: int = 200) -> str:
    text = str(value).replace("\n", " ").strip()
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}..."


def _tool_call_name(tool_call: object) -> str:
    if isinstance(tool_call, dict):
        return str(tool_call.get("name", "unknown"))
    return str(getattr(tool_call, "name", "unknown"))


def _is_empty_string(value: object) -> bool:
    if not isinstance(value, str):
        return False
    return value.strip().lower() in {"", "none", "null", "undefined"}


def _message_role(message: object) -> str:
    if isinstance(message, tuple) and message:
        return str(message[0])
    message_type = getattr(message, "type", None)
    if message_type:
        return str(message_type)
    return message.__class__.__name__


def _message_content(message: object) -> object:
    if isinstance(message, tuple) and len(message) > 1:
        return message[1]
    return getattr(message, "content", message)


def _log_messages(label: str, messages: object, max_length: int = 1000) -> None:
    _agent_log(f"{label}:")
    for index, message in enumerate(messages, start=1):
        role = _message_role(message)
        content = _preview(_message_content(message), max_length=max_length)
        _agent_log(f"  [{index}] {role}: {content}")
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            call_names = [_tool_call_name(call) for call in tool_calls]
            _agent_log(f"      tool_calls={call_names}")


class ImageSearchInput(BaseModel):
    location: Optional[str] = Field(
        None,
        description="拍摄地点关键词，例如 北京、杭州。没有地点条件时省略或传空字符串，不要传字符串 'None'。",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="标签数组，例如 ['风景', '旅行']。没有标签条件时传空数组 []；必须是数组，不要传字符串 'None'、'[]' 或逗号分隔字符串。",
    )
    year: Optional[str] = Field(
        None,
        description="四位年份字符串，例如 2024。没有年份条件时省略或传空字符串，不要传字符串 'None'。",
    )

    @field_validator("location", "year", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> Optional[str]:
        if _is_empty_string(value):
            return None
        if value is None:
            return None
        return str(value).strip()

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: Any) -> List[str]:
        if value is None or _is_empty_string(value):
            return []
        if isinstance(value, list):
            return [str(tag).strip() for tag in value if not _is_empty_string(tag)]
        if isinstance(value, str):
            text = value.strip()
            try:
                parsed = json.loads(text)
                if parsed is None:
                    return []
                if isinstance(parsed, list):
                    return [str(tag).strip() for tag in parsed if not _is_empty_string(tag)]
                if isinstance(parsed, str) and _is_empty_string(parsed):
                    return []
                return [str(parsed).strip()]
            except json.JSONDecodeError:
                pass
            cleaned = text.strip("[]")
            parts = [part.strip(" '\"") for part in cleaned.replace("，", ",").split(",")]
            return [part for part in parts if part and part.lower() not in {"none", "null", "undefined"}]
        return [str(value).strip()]


class SemanticImageSearchInput(BaseModel):
    query: str = Field(
        ...,
        description="用于语义搜图的自然语言描述，例如 '夜晚城市灯光'、'海边日落和人像'、'热闹的旅行照片'。",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="返回结果数量，默认 5。工具会先取 5 * top_k 个 Milvus HNSW 候选，再用 SigLIP image-text matching 重排。",
    )

    @field_validator("query", mode="before")
    @classmethod
    def normalize_query(cls, value: Any) -> str:
        return str(value or "").strip()

    @field_validator("top_k", mode="before")
    @classmethod
    def normalize_top_k(cls, value: Any) -> int:
        if value is None or _is_empty_string(value):
            return 5
        return int(value)


def run_agent_chat(prompt: str, user_id: int) -> str:
    """
    Run the agent with the given prompt and user id.
    """
    try:
        _agent_log(f"开始处理请求 user_id={user_id}, prompt=\"{_preview(prompt)}\"")

        api_key = current_app.config.get('QWEN_API_KEY') or os.environ.get('API_KEY')
        base_url = current_app.config.get('QWEN_BASE_URL')
        model_name = current_app.config.get('QWEN_MODEL', 'qwen-flash')
        _agent_log(f"初始化模型 model={model_name}, base_url={base_url}")

        llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=0.1,
        )

        @tool("image_search", args_schema=ImageSearchInput)
        def image_search_tool(location: Optional[str] = None, tags: Optional[List[str]] = None, year: Optional[str] = None):
            """
            按地点、标签、年份搜索当前用户图片。

            Args:
                location: 可选地点关键词，例如 北京、杭州；没有地点条件时省略或传空字符串。
                tags: 标签数组；没有标签条件时必须传 []，不要传字符串 "None" 或 "[]"。
                year: 可选四位年份字符串，例如 2024；没有年份条件时省略或传空字符串。
            """
            search_args = {
                "location": location or "",
                "tags": tags or [],
                "year": year or "",
            }
            _agent_log(f"调用工具 image_search args={search_args}")
            results = search_images_for_user(
                int(user_id),
                search_args,
            )
            _agent_log(f"工具 image_search 完成，命中 {len(results)} 张图片")
            return json.dumps(results, ensure_ascii=False)

        @tool("semantic_image_search", args_schema=SemanticImageSearchInput)
        def semantic_image_search_tool(query: str, top_k: int = 5):
            """
            基于图片视觉内容的语义搜图工具。

            使用 SigLIP Text Encoder 生成文本向量，在 Milvus HNSW 中检索 Top 5*top_k 候选图片，
            再用 SigLIP Image-Text Matching 重排，只返回 score 大于最高分 1/5 的相似结果及 score。

            Args:
                query: 自然语言语义描述，例如 "北京夜景"、"蓝天草地上的人"、"食物特写"。
                top_k: 最多返回数量，默认 5，范围 1-20；低相似度结果会被过滤。
            """
            _agent_log(f"调用工具 semantic_image_search query={query!r}, top_k={top_k}")
            try:
                results = semantic_search_images_for_user(int(user_id), query, top_k)
            except SemanticSearchError as exc:
                _agent_log(f"工具 semantic_image_search 配置错误: {exc}")
                return json.dumps({"error": str(exc)}, ensure_ascii=False)
            except Exception as exc:
                _agent_log(f"工具 semantic_image_search 执行失败: {exc}")
                return json.dumps({"error": f"语义搜索失败: {exc}"}, ensure_ascii=False)

            _agent_log(f"工具 semantic_image_search 完成，返回 {len(results)} 张图片")
            return json.dumps(results, ensure_ascii=False)

        tools = [image_search_tool, semantic_image_search_tool]
        _agent_log(f"已注册工具: {', '.join(t.name for t in tools)}")

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
            tool_calls = getattr(last_message, "tool_calls", None)
            if tool_calls:
                _agent_log(f"模型请求调用 {len(tool_calls)} 个工具")
                return "tools"
            _agent_log("模型未请求更多工具，准备结束")
            return END

        def call_model(state):
            messages = state['messages']
            _log_messages("发送给模型的消息", messages)
            _agent_log(f"调用模型，当前消息数={len(messages)}")
            response = llm.bind_tools(tools).invoke(messages)
            _log_messages("模型回复消息", [response])
            tool_calls = getattr(response, "tool_calls", None)
            if tool_calls:
                call_names = [_tool_call_name(call) for call in tool_calls]
                _agent_log(f"模型返回工具调用: {', '.join(call_names)}")
            else:
                content = getattr(response, "content", "")
                _agent_log(f"模型返回最终文本，长度={len(str(content))}")
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
        _log_messages("初始消息", inputs["messages"])
        _agent_log("开始执行 LangGraph")
        result = agent_executor.invoke(inputs)
        _agent_log("LangGraph 执行完成")
        messages = result.get("messages", [])
        _log_messages("最终消息", messages)
        if messages:
            final_content = messages[-1].content
            _agent_log(f"返回给前端，文本长度={len(str(final_content))}")
            return final_content
        _agent_log("返回给前端: 无响应")
        return "(无响应)"

    except Exception as e:
        _agent_log(f"执行出错: {e}")
        return f"Agent execution error: {str(e)}"
