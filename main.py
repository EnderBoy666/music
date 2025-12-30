import requests
import json
import gradio as gr
import sqlite3
from datetime import datetime

index_api = 'http://103.40.13.68:49964/search?keywords='
wy_url = 'https://music.163.com/#/song?id='  # 网易云音乐基础链接
download_api = "https://api.byfuns.top/1/?id="

# 数据库初始化
def init_db():
    """初始化数据库，创建存储歌曲ID的表和已播放歌曲表"""
    conn = sqlite3.connect('song_database.db')
    cursor = conn.cursor()
    # 创建歌曲表，包含ID、歌曲ID、歌曲名、歌手和添加时间
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS saved_songs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        song_id TEXT NOT NULL UNIQUE,
        song_name TEXT NOT NULL,
        artist TEXT NOT NULL,
        added_time TIMESTAMP NOT NULL
    )
    ''')
    
    # 创建已播放歌曲表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS played_songs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        song_id TEXT NOT NULL UNIQUE,
        song_name TEXT NOT NULL,
        artist TEXT NOT NULL,
        added_time TIMESTAMP NOT NULL,
        played_time TIMESTAMP NOT NULL 
    )
    ''')
    conn.commit()
    conn.close()

# 检查歌曲是否已存在（在未播放表中）
def is_song_exist(song_id):
    """检查歌曲是否已在数据库中"""
    conn = sqlite3.connect('song_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM saved_songs WHERE song_id = ?", (song_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

# 保存歌曲信息到数据库
def save_song_to_db(selected_song):
    """将选中的歌曲信息保存到数据库"""
    if not selected_song:
        return "请先选择歌曲"
    
    try:
        # 解析选中的歌曲信息
        parts = selected_song.split(',')
        if len(parts) < 2:
            return "歌曲信息格式错误"
        
        song_id = parts[0]
        song_info = parts[1].split('--by--')
        song_name = song_info[0].strip()
        artist = song_info[1].strip() if len(song_info) > 1 else "未知歌手"
        
        # 检查是否已存在
        if is_song_exist(song_id):
            return f"⚠️ 歌曲已存在：{song_name} - {artist}"
        
        # 插入数据库
        conn = sqlite3.connect('song_database.db')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO saved_songs (song_id, song_name, artist, added_time) VALUES (?, ?, ?, ?)",
            (song_id, song_name, artist, datetime.now())
        )
        conn.commit()
        conn.close()
        return f"成功保存歌曲：{song_name} - {artist} (ID: {song_id})"
    except sqlite3.IntegrityError:
        return f"⚠️ 歌曲已存在：{song_name} - {artist}"
    except Exception as e:
        return f"保存失败：{str(e)}"

def search_song(song_name):
    if not song_name:
        return []
    try:
        response = requests.get(index_api + song_name)
        data = json.loads(response.text)
        songs = data['result']['songs']
        song_list = []
        for song in songs:
            song_row = [
                song['id'],
                song['name'],
                ', '.join([artist['name'] for artist in song['artists']])
            ]
            song_list.append(song_row)
        return song_list
    except Exception as e:
        print(f"搜索出错: {e}")
        return []

def format_song_list(raw_song_list):
    if not raw_song_list:
        return []
    formatted = []
    for song in raw_song_list:
        formatted_str = f"{song[0]},{song[1]} --by-- {song[2]}"
        formatted.append(formatted_str)
    return formatted

def on_search_click(song_name):
    raw_list = search_song(song_name)
    formatted_list = format_song_list(raw_list)
    return gr.update(choices=formatted_list, value=None)

def on_song_select(selected_song):
    if not selected_song:
        return "请先选择歌曲"
    song_id = selected_song.split(',')[0]
    return f"你选择的歌曲ID是：{song_id}，歌曲为{selected_song.split(',')[1]}"

def yulan_song(selected_song):
    if not selected_song:
        return None  # 未选择歌曲时返回None
    song_id = selected_song.split(',')[0]
    download = f"{download_api}{song_id}"
    url = requests.get(download).text
    return url

# 获取当前播放队列（未播放歌曲）
def get_play_queue():
    """从数据库获取当前播放队列（已保存歌曲）"""
    try:
        conn = sqlite3.connect('song_database.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT song_name, artist, song_id, added_time 
            FROM saved_songs 
            ORDER BY added_time ASC
        """)
        data = cursor.fetchall()
        conn.close()
        
        formatted_data = []
        for row in data:
            song_name, artist, song_id, added_time = row
            formatted_time = datetime.strptime(added_time, "%Y-%m-%d %H:%M:%S.%f").strftime("%Y-%m-%d %H:%M")
            formatted_data.append([song_name, artist, song_id, formatted_time])
        
        return formatted_data
    except Exception as e:
        return [[f"获取队列失败: {str(e)}"]]

# 获取已播放歌曲列表
def get_played_songs():
    """从数据库获取已播放歌曲列表"""
    try:
        conn = sqlite3.connect('song_database.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT song_name, artist, song_id, played_time 
            FROM played_songs 
            ORDER BY played_time DESC
        """)
        data = cursor.fetchall()
        conn.close()
        
        formatted_data = []
        for row in data:
            song_name, artist, song_id, played_time = row
            formatted_time = datetime.strptime(played_time, "%Y-%m-%d %H:%M:%S.%f").strftime("%Y-%m-%d %H:%M")
            formatted_data.append([song_name, artist, song_id, formatted_time])
        
        return formatted_data
    except Exception as e:
        return [[f"获取已播放列表失败: {str(e)}"]]

# 初始化数据库
init_db()

with gr.Blocks(title="点歌台") as app:
    song_name = gr.Textbox(label="请输入歌曲名称")
    search_btn = gr.Button("查找歌曲")
    song_dropdown = gr.Dropdown(choices=[], label="选择你要点的歌", interactive=True)
    result_info = gr.Textbox(label="选择结果")

    search_btn.click(
        fn=on_search_click,
        inputs=song_name,
        outputs=song_dropdown
    )

    song_dropdown.change(
        fn=on_song_select,
        inputs=song_dropdown,
        outputs=result_info
    )

    yulan_btn = gr.Button("预览歌曲")
    yulan_out = gr.Audio()
    yulan_btn.click(
        fn=yulan_song,
        inputs=song_dropdown,
        outputs=yulan_out,
    )
    
    # 添加上传到数据库的按钮和结果显示
    save_btn = gr.Button("上传到数据库")
    save_result = gr.Textbox(label="保存结果")
    
    save_btn.click(
        fn=save_song_to_db,
        inputs=song_dropdown,
        outputs=save_result
    )
    
    # 播放队列显示
    gr.Markdown("### 当前播放队列（未播放）")
    queue_refresh_btn = gr.Button("刷新队列")
    play_queue = gr.Dataframe(
        headers=["歌曲名", "歌手", "歌曲ID", "添加时间"],
        type="array",
        label="已添加的歌曲列表"
    )
    
    queue_refresh_btn.click(
        fn=get_play_queue,
        inputs=[],
        outputs=play_queue
    )
    
    # 已播放歌曲列表
    gr.Markdown("### 已播放歌曲记录")
    played_refresh_btn = gr.Button("刷新已播放列表")
    played_songs = gr.Dataframe(
        headers=["歌曲名", "歌手", "歌曲ID", "播放时间"],
        type="array",
        label="已播放的歌曲列表"
    )
    
    played_refresh_btn.click(
        fn=get_played_songs,
        inputs=[],
        outputs=played_songs
    )
    
    # 页面加载时初始化数据
    app.load(
        fn=lambda: (get_play_queue(), get_played_songs()),
        inputs=[],
        outputs=[play_queue, played_songs]
    )

app.launch(server_port=8123)