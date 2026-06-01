"""
Streamlit 入口 —— 多 Agent 需求分析系统的 Web 界面

特性：
  - 两段式人在回路：先出需求分析 → 人工审阅/编辑/确认 → 再跑后续生成 PRD
  - 实时进度：每个 Agent 阶段完成即展示（互质疑高亮）
  - PRD 下载（Word）

运行方式：streamlit run main.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

from config import MAX_REVISION_ROUNDS, TAVILY_API_KEY, RAG_DIR, DEEPSEEK_API_KEY
from core.crew_runner import analyze_requirement, generate_prd
from utils.validators import validate_requirement

st.set_page_config(page_title="多 Agent 需求分析系统", page_icon="🤖", layout="wide")

# ==================== 阶段 → Agent 展示元数据 ====================
AGENT_META = {
    "协调拆解": ("🧭", "协调员"),
    "需求分析": ("📋", "需求分析师"),
    "行业研究": ("🔍", "行业研究员"),
    "技术评估": ("🛠️", "技术评估员"),
    "互质疑": ("⚠️", "互质疑 · 退回修订"),
    "需求修订": ("✏️", "需求分析师 · 修订"),
    "重新评估": ("🔁", "技术评估员 · 复审"),
    "文档汇总": ("📄", "文档专员"),
}

EXAMPLES = [
    "做一个校园二手交易小程序",
    "搭一个企业内部的 IT 工单与排障系统",
    "做一个面向中小团队的项目管理工具",
]

# ==================== 会话状态初始化 ====================
_defaults = {
    "phase": "input",          # input → review → done
    "requirement": "",
    "analysis_result": None,   # {"plan":..., "analysis":...}
    "final_result": None,
    "stages": [],              # generate_prd 阶段的 (stage, content) 列表
}
for k, v in _defaults.items():
    st.session_state.setdefault(k, v)


def _reset():
    for k, v in _defaults.items():
        st.session_state[k] = v


def render_bubble(stage: str, content: str):
    """把一个阶段产出渲染成 Agent 气泡。"""
    emoji, name = AGENT_META.get(stage, ("🤖", stage))
    with st.chat_message(name, avatar=emoji):
        st.markdown(f"**{name}**")
        if stage == "互质疑":
            st.warning(content)
        else:
            st.markdown(content)


# ==================== 侧边栏 ====================
with st.sidebar:
    st.header("⚙️ 设置")
    max_rounds = st.slider("互质疑最大修订轮数", 0, 2, MAX_REVISION_ROUNDS,
                           help="技术评估员判定需修订时，退回需求分析师重做的最大轮数")
    st.divider()
    st.subheader("环境状态")
    st.caption(("✅" if DEEPSEEK_API_KEY else "❌") + " DeepSeek LLM")
    st.caption(("✅ 真实联网搜索" if TAVILY_API_KEY else "🟡 搜索降级为 LLM 模拟"))
    st.caption(("✅ RAG 历史经验联动" if RAG_DIR else "🟡 RAG 未配置（评估走通用经验）"))
    st.divider()
    st.subheader("✨ 三大亮点")
    st.markdown(
        "- **Agent 互质疑**：评估员可退回分析师改\n"
        "- **人在回路**：需求分析人工确认\n"
        "- **跨系统联动**：评估员调自建 RAG 查历史经验"
    )
    st.divider()
    if st.button("🔄 重新开始", use_container_width=True):
        _reset()
        st.rerun()

# ==================== 主区 ====================
st.title("🤖 多 Agent 需求分析系统")
st.caption("一句模糊需求 → 5 个 AI Agent 协作 → 专业需求规格说明书（PRD）")

phase = st.session_state.phase

# ---------- 阶段 input：输入需求 ----------
if phase == "input":
    st.markdown("### ① 输入你的需求")
    req = st.text_area("用一句话描述你想做的产品：", value=st.session_state.requirement,
                       placeholder="例如：做一个校园二手交易小程序", height=100)
    st.caption("示例（点击填入）：")
    cols = st.columns(len(EXAMPLES))
    for i, ex in enumerate(EXAMPLES):
        if cols[i].button(ex, use_container_width=True):
            st.session_state.requirement = ex
            st.rerun()

    # 输入验证
    req_stripped = req.strip()
    is_valid, validation_error = validate_requirement(req_stripped) if req_stripped else (False, "需求文本不能为空")

    if req_stripped and not is_valid:
        st.error(f"❌ {validation_error}")

    if st.button("① 分析需求", type="primary", disabled=not req_stripped or not is_valid):
        with st.spinner("协调员拆解任务 + 需求分析师分析中…"):
            result = analyze_requirement(req_stripped)
        st.session_state.requirement = req_stripped
        st.session_state.analysis_result = result
        st.session_state.phase = "review"
        st.rerun()

# ---------- 阶段 review：人在回路确认 ----------
elif phase == "review":
    st.markdown(f"**需求：** {st.session_state.requirement}")
    ar = st.session_state.analysis_result
    render_bubble("协调拆解", ar["plan"])

    st.info("👤 **人在回路**：请审阅需求分析，可直接编辑补充，确认后再进入耗时的研究与评估阶段。")
    edited = st.text_area("需求分析（可编辑）", value=ar["analysis"], height=420)

    c1, c2 = st.columns([1, 1])
    if c1.button("② 确认并生成 PRD", type="primary", use_container_width=True):
        stages = []
        with st.status("多 Agent 协作生成中…（研究 → 评估 → 互质疑 → 文档，约 2-4 分钟）",
                       expanded=True) as status:
            def on_stage(stage, content):
                stages.append((stage, content))
                emoji, name = AGENT_META.get(stage, ("🤖", stage))
                status.write(f"{emoji} **{name}** 完成")

            result = generate_prd(st.session_state.requirement, edited,
                                  on_stage=on_stage, max_rounds=max_rounds)
            status.update(label="✅ 生成完成！", state="complete")
        st.session_state.stages = stages
        st.session_state.final_result = result
        st.session_state.phase = "done"
        st.rerun()

    if c2.button("↩ 重新输入需求", use_container_width=True):
        st.session_state.phase = "input"
        st.rerun()

# ---------- 阶段 done：展示结果 + 下载 ----------
elif phase == "done":
    res = st.session_state.final_result
    rounds = res["revision_rounds"]
    if rounds > 0:
        st.success(f"✅ 完成！其中技术评估员触发了 {rounds} 轮「互质疑」，需求经修订后通过。")
    else:
        st.success("✅ 完成！技术评估一次通过，无需修订。")

    st.markdown("### 🗂️ 协作过程")
    render_bubble("协调拆解", st.session_state.analysis_result["plan"])
    render_bubble("需求分析", st.session_state.analysis_result["analysis"])
    for stage, content in st.session_state.stages:
        render_bubble(stage, content)

    st.divider()
    st.markdown("### 📄 最终需求规格说明书（PRD）")
    with open(res["docx_path"], "rb") as f:
        st.download_button("⬇️ 下载 Word 版 PRD", data=f.read(),
                           file_name=os.path.basename(res["docx_path"]),
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                           type="primary")
    st.markdown(res["prd_markdown"])

    if st.button("🔄 再做一个"):
        _reset()
        st.rerun()
