import requests
import json
import gradio as gr
index_api=r'http://103.40.13.68:49964/search?keywords='

def search_song(song_name):
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
    #print(song_list)
    return song_list

def choose_song(song_list):
    list1=[]
    for song in song_list:
        song_row=f"{song['id']},{song['name']}  by  {', '.join([artist['name'] for artist in song['artists']])}"
    list1.append(song_row)
    return list1

with gr.Blocks(title="点歌台") as app:
    song_name = gr.Textbox(label="请输入歌曲名称")
    search_btn = gr.Button("查找歌曲")
    song_list_out = gr.DataFrame(label="歌曲信息",headers=['ID', '歌曲名称', '歌手'])
    search_btn.click(search_song, inputs=song_name, outputs=song_list_out)
    song_list=choose_song(search_song(song_name))
    song=gr.Dropdown(choices=song_list,label="选择你要点的歌")


app.launch(share=True)