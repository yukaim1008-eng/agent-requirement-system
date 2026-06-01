"""
RAG 查询工具 —— 技术评估员用，查询自建 IT 运维知识库的历史经验

联动方式：用 RAG 项目自己的 venv 拉起 backend.py 子进程，走 JSON 行协议通信
  请求: {"query": "...", "mode": "quick", "filter_json": "null"}
  响应: {"answer": "...", "citations": [...], "trace": {...}}

健壮性：用「后台读取线程 + 队列 + 真正的超时」读取响应。
  —— 关键：subprocess 的 readline() 是阻塞调用，若 backend 卡住（如重连 Qdrant 卡网络），
     readline 会永远阻塞、循环里的 timeout 根本检查不到，从而拖死整个 crew。
     这里改为读取线程把行喂进队列，主流程用 queue.get(timeout=...) 读，超时即杀进程走降级。
优化：后端进程常驻复用（一次加载模型，多次查询）。
进程隔离：RAG 的重模型不污染本项目依赖。
注意：RAG 日志走 stderr（这里丢弃），stdout 只有 READY 和 JSON 响应。
"""
import os
import json
import time
import queue
import atexit
import threading
import subprocess

from crewai.tools import tool

from config import RAG_DIR, RAG_PYTHON

_EOF = object()        # 进程结束（stdout 关闭）的哨兵
_backend = None        # {"proc": Popen, "q": Queue} 或 None


def _spawn_backend():
    """启动 RAG backend 子进程，并起一个后台线程把 stdout 逐行喂进队列。"""
    if not RAG_DIR or not RAG_PYTHON or not os.path.exists(RAG_PYTHON):
        return None
    if not os.path.exists(os.path.join(RAG_DIR, "backend.py")):
        return None

    proc = subprocess.Popen(
        [RAG_PYTHON, "backend.py"],
        cwd=RAG_DIR,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,   # RAG 日志走 stderr，丢弃
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    q: queue.Queue = queue.Queue()

    def _reader():
        try:
            for line in proc.stdout:
                q.put(line)
        except Exception:
            pass
        q.put(_EOF)

    threading.Thread(target=_reader, daemon=True).start()
    return {"proc": proc, "q": q}


def _read_line(b, timeout):
    """从队列读一行：返回 str / _EOF（进程结束） / None（超时）。"""
    try:
        return b["q"].get(timeout=max(0.1, timeout))
    except queue.Empty:
        return None


def _wait_ready(b, timeout: int = 180) -> bool:
    """等待 backend 打印 READY（模型加载完成）。超时/进程退出返回 False。"""
    start = time.time()
    while True:
        remaining = timeout - (time.time() - start)
        if remaining <= 0:
            return False
        item = _read_line(b, remaining)
        if item is None or item is _EOF:
            return False
        if item.strip() == "READY":
            return True


def _kill_backend():
    """杀掉常驻后端并重置（下次调用会重启）。"""
    global _backend
    if _backend is not None:
        try:
            _backend["proc"].terminate()
        except Exception:
            pass
    _backend = None


def _get_backend():
    """返回常驻后端；不存在/已退出则重启并等待 READY。失败返回 None。"""
    global _backend
    if _backend is not None and _backend["proc"].poll() is None:
        return _backend
    b = _spawn_backend()
    if b is None:
        return None
    if not _wait_ready(b):
        try:
            b["proc"].terminate()
        except Exception:
            pass
        return None
    _backend = b
    atexit.register(_kill_backend)
    return _backend


def _query_rag_backend(query: str, mode: str = "quick", timeout: int = 90):
    """向常驻后端发一个查询，返回格式化 answer；不可用/超时返回 None（绝不阻塞）。"""
    b = _get_backend()
    if b is None:
        return None
    try:
        req = json.dumps({"query": query, "mode": mode, "filter_json": "null"}, ensure_ascii=False)
        b["proc"].stdin.write(req + "\n")
        b["proc"].stdin.flush()
    except (BrokenPipeError, OSError):
        _kill_backend()
        return None

    start = time.time()
    while True:
        remaining = timeout - (time.time() - start)
        if remaining <= 0:
            _kill_backend()   # backend 卡住，杀掉走降级
            return None
        item = _read_line(b, remaining)
        if item is None or item is _EOF:
            _kill_backend()
            return None
        line = item.strip()
        if not line:
            continue
        try:
            resp = json.loads(line)
        except json.JSONDecodeError:
            continue  # 跳过意外的非 JSON 行
        answer = resp.get("answer", "")
        citations = resp.get("citations", [])
        if citations:
            srcs = "；".join(
                f"{c.get('source_file', '')} 第{c.get('chunk_index', '')}段"
                for c in citations[:3]
            )
            return f"{answer}\n\n（参考来源：{srcs}）"
        return answer


@tool("query_knowledge_base")
def query_history(query: str) -> str:
    """
    历史项目经验查询：查询自建 IT 运维知识库，获取与技术实现、运维、排障相关的历史经验参考。
    输入：一个技术问题或关键词（字符串）。返回：知识库中的相关经验；无相关内容时返回提示。
    适用于评估技术风险、参考过往实现方案时调用。
    （工具名必须为 ASCII —— OpenAI 兼容接口要求函数名只能含字母/数字/_/-）
    """
    result = _query_rag_backend(query)
    if result is None:
        return "（历史经验知识库当前不可用，本次评估基于通用工程经验进行。）"
    return result


def build_rag_tool():
    """返回配置好的 RAG 查询工具（供 agents 绑定）。"""
    return query_history
