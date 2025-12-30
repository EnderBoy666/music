import gradio as gr

def jump_to_search(keyword):
    # 拼接搜索URL
    search_url = f"https://www.baidu.com/s?wd={keyword}"
    # 返回前端执行的JS代码
    return f"window.open('{search_url}', '_blank');"

with gr.Blocks() as demo:
    gr.Markdown("# 动态搜索跳转")
    keyword = gr.Textbox(label="输入搜索关键词")
    btn = gr.Button("搜索并跳转")
    # 绑定点击事件，执行函数后运行返回的JS
    btn.click(
        fn=jump_to_search,
        inputs=keyword,
        outputs=None,
        js=lambda x: x  # 执行函数返回的JS代码
    )

if __name__ == "__main__":
    demo.launch()