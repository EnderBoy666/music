import requests
import sqlite3
import gradio as gr
from typing import Optional, List, Tuple
from datetime import datetime

# 配置项（与点歌台保持一致）
DOWNLOAD_API = "https://api.byfuns.top/1/?id="
DB_PATH = "song_database.db"  # 与点歌台共享数据库文件


def get_saved_songs_from_db() -> Tuple[List[str], List[str]]:
    """从数据库读取所有已保存的歌曲，按上传时间升序排列（先上传先播放），返回下拉框选项和原始列表"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # 关键修改：ORDER BY added_time ASC （升序，先上传的排在前面）
        cursor.execute("""
            SELECT song_id, song_name, artist 
            FROM saved_songs 
            ORDER BY added_time ASC
        """)
        songs = cursor.fetchall()
        conn.close()

        # 格式化："歌曲ID,歌曲名 --by-- 歌手"
        formatted_songs = []
        raw_songs = []
        for song_id, name, artist in songs:
            formatted = f"{song_id},{name} --by-- {artist}"
            formatted_songs.append(formatted)
            raw_songs.append(formatted)
        return formatted_songs, raw_songs

    except sqlite3.Error as e:
        print(f"数据库读取失败: {e}")
        error_msg = ["数据库读取失败，请检查文件是否存在"]
        return error_msg, error_msg
    except Exception as e:
        print(f"未知错误: {e}")
        error_msg = ["加载歌曲列表失败"]
        return error_msg, error_msg


def get_song_play_url(selected_song: str) -> Optional[str]:
    """解析选中的歌曲，调用API获取播放链接"""
    if not selected_song or "数据库读取失败" in selected_song:
        return None

    try:
        # 提取歌曲ID
        song_id = selected_song.split(",")[0].strip()
        # 调用API获取音频链接
        response = requests.get(f"{DOWNLOAD_API}{song_id}", timeout=15)
        response.raise_for_status()  # 捕获HTTP请求错误
        play_url = response.text.strip()

        # 验证链接有效性（简单过滤空值/错误信息）
        if not play_url or "error" in play_url.lower():
            return None
        return play_url

    except requests.exceptions.Timeout:
        print("请求超时：API响应过慢")
        return None
    except requests.exceptions.RequestException as e:
        print(f"API请求失败: {e}")
        return None
    except IndexError:
        print("歌曲格式解析失败")
        return None


def play_song_by_index(song_list: List[str], index: int) -> Tuple[Optional[str], str, int]:
    """根据索引播放歌曲"""
    if not song_list or index < 0 or index >= len(song_list):
        return None, "⚠️ 无效的歌曲索引", index

    selected_song = song_list[index]
    try:
        play_url = get_song_play_url(selected_song)
        if play_url:
            return play_url, f"✅ 正在播放：{selected_song.split(',')[1]}", index
        else:
            return None, "❌ 获取播放链接失败（可能API不可用/歌曲ID无效）", index
    except Exception as e:
        return None, f"❌ 播放失败：{str(e)}", index


def play_selected_song(selected_song: str, song_list: List[str]) -> Tuple[Optional[str], str, int]:
    """播放选中的歌曲并更新索引"""
    if not selected_song or not song_list:
        return None, "⚠️ 请先从下拉框选择一首歌曲", -1

    try:
        index = song_list.index(selected_song)
        return play_song_by_index(song_list, index)
    except ValueError:
        return None, "⚠️ 所选歌曲不在列表中", -1


def move_to_played(song_id: str) -> bool:
    """将歌曲从saved_songs移动到played_songs"""
    if not song_id:
        return False
        
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 开启事务
        conn.execute('BEGIN TRANSACTION')
        
        # 查询歌曲信息
        cursor.execute("""
            SELECT song_id, song_name, artist, added_time 
            FROM saved_songs 
            WHERE song_id = ?
        """, (song_id,))
        song = cursor.fetchone()
        
        if not song:
            conn.rollback()
            return False
            
        # 插入到已播放表
        cursor.execute("""
            INSERT INTO played_songs 
            (song_id, song_name, artist, added_time, played_time) 
            VALUES (?, ?, ?, ?, ?)
        """, (song[0], song[1], song[2], song[3], datetime.now()))
        
        # 从原表删除
        cursor.execute("DELETE FROM saved_songs WHERE song_id = ?", (song_id,))
        
        # 提交事务
        conn.commit()
        return True
        
    except sqlite3.Error as e:
        print(f"移动歌曲失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def next_song(song_list: List[str], current_index: int) -> Tuple[Optional[str], str, int]:
    """播放下一首歌曲（按上传顺序往后）"""
    if not song_list:
        return None, "⚠️ 歌曲列表为空", -1

    # 如果当前有正在播放的歌曲，将其移到已播放表
    if current_index >= 0 and current_index < len(song_list):
        current_song = song_list[current_index]
        song_id = current_song.split(",")[0].strip()
        move_to_played(song_id)
    
    # 计算下一首索引，循环播放（先上传的先播，播完到下一个）
    next_index = (current_index + 1) % len(song_list) if song_list else -1
    return play_song_by_index(song_list, next_index)


def refresh_song_list() -> Tuple[gr.Dropdown, List[str], Optional[str], str, int]:
    """刷新歌曲列表并自动播放第一首（最先上传的）"""
    formatted_songs, raw_songs = get_saved_songs_from_db()
    
    # 如果有歌曲，自动播放第一首（最先上传的）
    if formatted_songs and "数据库读取失败" not in formatted_songs[0]:
        return (gr.update(choices=formatted_songs, value=formatted_songs[0]), 
                raw_songs, 
                *play_song_by_index(raw_songs, 0))
    else:
        return gr.update(choices=formatted_songs, value=None), raw_songs, None, "", -1


# 构建Gradio播放界面
with gr.Blocks(title="音乐播放端") as play_app:
    gr.Markdown("# 🎶 已保存歌曲播放端")
    gr.Markdown("### 从数据库加载已收藏的歌曲（先上传先播放）")

    # 状态变量：存储歌曲列表和当前播放索引
    song_list_state = gr.State([])
    current_index_state = gr.State(-1)

    # 第一行：歌曲选择 + 刷新按钮
    with gr.Row():
        song_dropdown = gr.Dropdown(
            choices=[],
            label="已保存的歌曲列表（按上传时间升序 | 先上传先播放）",
            interactive=True
        )
        refresh_btn = gr.Button("🔄 刷新列表", variant="secondary")

    # 第二行：控制按钮
    with gr.Row():
        play_btn = gr.Button("▶️ 播放选中歌曲", variant="primary")
        next_btn = gr.Button("⏭️ 下一首", variant="secondary")

    # 状态提示 + 音频播放器
    play_status = gr.Textbox(label="播放状态", placeholder="操作提示将显示在这里")
    audio_player = gr.Audio(
        label="歌曲播放区",
        interactive=True,  # 允许用户暂停/调整音量
        autoplay=True      # 启用自动播放
    )

    # 初始化加载歌曲列表并自动播放第一首（最先上传的）
    play_app.load(
        fn=refresh_song_list,
        inputs=[],
        outputs=[song_dropdown, song_list_state, audio_player, play_status, current_index_state]
    )

    # 绑定事件：刷新列表（刷新后自动播放第一首最先上传的）
    refresh_btn.click(
        fn=refresh_song_list,
        inputs=[],
        outputs=[song_dropdown, song_list_state, audio_player, play_status, current_index_state]
    )

    # 绑定事件：点击播放按钮
    play_btn.click(
        fn=play_selected_song,
        inputs=[song_dropdown, song_list_state],
        outputs=[audio_player, play_status, current_index_state]
    )

    # 绑定事件：点击下一首按钮（按上传顺序往后播）
    next_btn.click(
        fn=next_song,
        inputs=[song_list_state, current_index_state],
        outputs=[audio_player, play_status, current_index_state]
    )

    # 绑定事件：音频播放结束时自动播放下一首（连续播放）
    audio_player.stop(
        fn=next_song,
        inputs=[song_list_state, current_index_state],
        outputs=[audio_player, play_status, current_index_state]
    )

    # 绑定事件：下拉框选择变化时自动播放选中歌曲
    song_dropdown.change(
        fn=play_selected_song,
        inputs=[song_dropdown, song_list_state],
        outputs=[audio_player, play_status, current_index_state]
    )

# 启动播放端
if __name__ == "__main__":
    play_app.launch(
        server_port=8124,
        server_name="0.0.0.0",  # 允许局域网访问
        share=True  # 如需公网访问，取消注释
    )