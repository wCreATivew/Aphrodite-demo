"""Aphrodite Streamlit Home + TaskRun Replay"""

import datetime
from urllib.parse import quote

import streamlit as st

from agentlib.task_run import load_task_run_steps, load_task_runs


def get_current_time_str() -> str:
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")


def build_search_url(query: str, engine: str) -> str:
    q = quote(query)
    if engine == "Google":
        return f"https://www.google.com/search?q={q}"
    if engine == "Bing":
        return f"https://www.bing.com/search?q={q}"
    if engine == "百度":
        return f"https://www.baidu.com/s?wd={q}"
    return f"https://www.google.com/search?q={q}"


def render_header():
    st.title("Aphrodite 控制台")
    st.markdown(f"**当前时间：** {get_current_time_str()}")


def render_search_section():
    st.subheader("🔍 搜索")
    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input("输入搜索关键词", "", key="search_query")
    with col2:
        engine = st.selectbox("搜索引擎", ["Google", "Bing", "百度"], key="search_engine")
    if st.button("立即搜索"):
        if query.strip():
            url = build_search_url(query, engine)
            st.markdown(f"✅ [点击这里查看结果]({url})", unsafe_allow_html=True)
        else:
            st.warning("请输入搜索关键词！")


def render_quick_links():
    st.subheader("📌 常用快捷链接")
    links = [
        ("GitHub", "https://github.com"),
        ("ArXiv", "https://arxiv.org"),
        ("Notion", "https://www.notion.so"),
        ("知乎", "https://www.zhihu.com"),
    ]
    cols = st.columns(2)
    for i, (name, url) in enumerate(links):
        with cols[i % 2]:
            st.markdown(f"[{name}]({url})")


def render_task_replay_section():
    st.subheader("🎬 TaskRun 回放 / 审计")
    runs = load_task_runs()
    if not runs:
        st.info("暂无 TaskRun 记录。请先运行 selfdrive/agent 任务。")
        return

    options = [f"{r.run_id} | {r.status} | {r.goal[:48]}" for r in runs]
    idx = st.selectbox("选择一次运行", list(range(len(options))), format_func=lambda i: options[i])
    run = runs[int(idx)]

    c1, c2, c3 = st.columns(3)
    c1.metric("状态", run.status)
    c2.metric("步骤数(快照)", len(run.steps))
    c3.metric("创建时间", datetime.datetime.fromtimestamp(run.created_at).strftime("%m-%d %H:%M:%S") if run.created_at else "-")

    with st.expander("Plan 快照", expanded=False):
        st.json(run.plan)

    steps = load_task_run_steps(run.run_id)
    if not steps and run.steps:
        steps = run.steps

    st.markdown(f"**Step 记录：{len(steps)} 条**")
    for i, step in enumerate(steps):
        title = f"{i+1}. {step.step_id} | {step.status} | {step.duration_ms}ms"
        with st.expander(title, expanded=False):
            st.write(f"开始: {datetime.datetime.fromtimestamp(step.ts_start)}")
            st.write(f"结束: {datetime.datetime.fromtimestamp(step.ts_end)}")
            st.write("输入")
            st.json(step.input_payload)
            st.write("工具调用")
            st.json(step.tool_calls)
            st.write("输出")
            st.json(step.output)
            if step.error:
                st.error(step.error)


def main():
    render_header()
    tab1, tab2 = st.tabs(["主页", "TaskRun 回放"])
    with tab1:
        render_search_section()
        st.markdown("---")
        render_quick_links()
    with tab2:
        render_task_replay_section()


if __name__ == "__main__":
    main()
