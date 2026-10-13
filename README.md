# 个性化音乐推荐系统

这是我的本科毕业设计项目，主要使用 Python、Flask、Pandas 和 NumPy 实现。

系统采用基于用户的协同过滤算法，根据用户对歌曲的评分计算用户相似度，然后给用户推荐还没有评分过的歌曲。

## 一、主要功能

1. 热门音乐推荐
2. 个性化音乐推荐
3. 新用户兴趣推荐
4. 歌曲搜索
5. 按音乐类型筛选
6. 用户给歌曲评分
7. 数据统计
8. 本地音乐试听

## 二、运行方法

第一次运行先安装依赖：

```bash
pip install -r requirements.txt
```

然后运行：

```bash
python app.py
```

浏览器打开：

```text
http://127.0.0.1:5000
```

Windows 也可以使用项目中的：

```text
首次安装依赖.bat
启动系统.bat
```

## 三、项目结构

```text
music_recommend_student/
├─ app.py
├─ recommender.py
├─ data/
│  ├─ music.csv
│  └─ ratings.csv
├─ templates/
└─ static/
```

`app.py` 主要负责网页路由。

`recommender.py` 主要负责数据读取、相似度计算和推荐。

## 四、音乐试听

如果需要试听，把音频文件放到：

```text
static/music/
```

然后在 `music.csv` 的 `audio_file` 中填写，例如：

```text
music/test.mp3
```

封面放到：

```text
static/covers/
```

对应填写：

```text
covers/test.jpg
```

音频文件请使用自己有权使用的文件。

## 五、增加歌曲

在 `data/music.csv` 中继续增加歌曲即可。

基本字段：

```text
music_id,title,artist,genre,tags,audio_file,cover_file
```

如果希望新歌曲参与协同过滤推荐，还需要在 `ratings.csv` 中有用户对它进行评分。

## 六、算法说明

系统使用余弦相似度计算用户之间的相似程度。

推荐评分使用用户平均分进行修正，主要目的是减少不同用户评分习惯的影响。

如果没有合适的协同过滤结果，就使用热门音乐推荐。

对于完全没有评分历史的新用户，使用音乐类型和标签进行简单的兴趣推荐。
