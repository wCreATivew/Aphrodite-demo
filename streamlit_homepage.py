"""
一个简单的 Streamlit 浏览器主页示例。

特点：

* 显示当前日期和时间。
* 提供搜索框，可选择搜索引擎（Google、Bing、百度）。
* 快捷链接列表，可快速访问常用网站。
* 简易待办事项列表，利用 session_state 在会话内存储任务。

后续你可以通过修改此文件中的函数和数据结构来自定义页面内容。
"""

import datetime
from urllib.parse import quote

import streamlit as st


def get_current_time_str() -> str:
    """返回当前时间的字符串表示。"""
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")


def build_search_url(query: str, engine: str) -> str:
    """根据搜索引擎构建查询 URL。"""
    q = quote(query)
    if engine == "Google":
        return f"https://www.google.com/search?q={q}"
    elif engine == "Bing":
        return f"https://www.bing.com/search?q={q}"
    elif engine == "百度":
        return f"https://www.baidu.com/s?wd={q}"
    else:
        # 默认使用 Google
        return f"https://www.google.com/search?q={q}"


def render_header():
    """渲染顶部区域：显示日期和时间。"""
    st.title("我的浏览器主页")
    st.markdown(
        f"**当前时间：** {get_current_time_str()}",
        help="每次刷新页面时更新当前时间。",
    )


def render_search_section():
    """渲染搜索区域：输入框、引擎选择和搜索按钮。"""
    st.subheader("🔍 搜索")
    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input("输入搜索关键词", "", key="search_query")
    with col2:
        engine = st.selectbox("搜索引擎", ["Google", "Bing", "百度"], key="search_engine")
    if st.button("立即搜索"):
        if query.strip():
            url = build_search_url(query, engine)
            st.markdown(
                f"✅ 已为你生成搜索链接： [点击这里查看结果]({url})",
                unsafe_allow_html=True,
            )
        else:
            st.warning("请输入搜索关键词！")


def render_quick_links():
    """渲染快捷链接部分。"""
    st.subheader("📌 常用快捷链接")
    # 你可以在此列表中添加或修改链接
    links = [
        ("Google 学术", "https://scholar.google.com"),
        ("GitHub", "https://github.com"),
        ("ArXiv", "https://arxiv.org"),
        ("Notion", "https://www.notion.so"),
        ("网易云音乐", "https://music.163.com"),
        ("知乎", "https://www.zhihu.com"),
        ("邮箱", "https://mail.google.com"),
    ]
    cols = st.columns(3)
    for i, (name, url) in enumerate(links):
        with cols[i % 3]:
            st.markdown(f"[{name}]({url})")


def render_todo_list():
    """渲染待办事项管理器。"""
    st.subheader("📝 待办事项")
    # 使用 session_state 来持久化列表
    if "todo_list" not in st.session_state:
        st.session_state.todo_list = []

    # 添加任务
    new_task = st.text_input("添加新任务", "", key="new_task")
    if st.button("添加到列表"):
        task = new_task.strip()
        if task:
            st.session_state.todo_list.append({"task": task, "done": False})
            # 清空输入框
            st.session_state.new_task = ""
        else:
            st.warning("任务内容不能为空！")

    # 显示和更新任务
    for idx, item in enumerate(st.session_state.todo_list):
        cols = st.columns([0.1, 0.8, 0.1])
        # 复选框决定任务是否完成
        done = cols[0].checkbox("", value=item["done"], key=f"done_{idx}")
        # 文本显示
        if done:
            cols[1].markdown(f"~~{item['task']}~~")
        else:
            cols[1].markdown(item["task"])
        # 删除按钮
        if cols[2].button("❌", key=f"delete_{idx}"):
            st.session_state.todo_list.pop(idx)
            st.experimental_rerun()
        # 更新状态
        st.session_state.todo_list[idx]["done"] = done


def main():
    """主函数：按顺序渲染各个模块。"""
    render_header()
    # 使用横向分隔线分隔各个部分
    st.markdown("---")
    render_search_section()
    st.markdown("---")
    render_quick_links()
    st.markdown("---")
    render_todo_list()


if __name__ == "__main__":
    main()
