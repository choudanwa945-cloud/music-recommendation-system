
import sqlite3
from pathlib import Path

# ==========================================
# 1. 项目路径
# ==========================================

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = BASE_DIR / "music_public.db"
MUSIC_DIR = BASE_DIR / "static" / "music"
COVER_DIR = BASE_DIR / "static" / "covers"

# ==========================================
# 2. 新增20首歌曲
# 格式：编号、歌名、歌手、类型、兴趣标签
# ==========================================

SONGS = [
    (41, "月光", "胡彦斌", "流行", "流行 国风 情感"),
    (42, "我听人说思念像风一样", "顿珠拉姆、白游诗", "抒情", "抒情 思念 情感"),
    (43, "月亮之下", "黄龄、邓典", "流行", "流行 夜晚 情感"),
    (44, "散了就散了（陕西话版）", "张超洋", "流行", "流行 方言 情感"),
    (45, "爱人", "莉莉周她说", "流行", "流行 治愈 情感"),
    (46, "你疏远着关系（陕西方言）", "DJ铁柱", "电子", "电子 方言 情感"),
    (47, "明天过后", "张杰", "流行", "流行 青春 情感"),
    (48, "一城山水", "Lunhui轮回", "流行", "流行 旅行 治愈"),
    (49, "大山", "王睿卓", "流行", "流行 励志 情感"),
    (50, "野火", "宸格", "流行", "流行 青春 励志"),

    (51, "哀人 (i)(Live)", "汪苏泷、门尼", "流行", "流行 情感 现场"),
    (52, "爱恨难断", "曲央吉", "抒情", "抒情 怀旧 情感"),
    (53, "511.不温暖的歌-欧瑞SoulCore", "jay的实验室", "流行", "流行 青春 情感"),
    (54, "阿苏拉则2025", "蔡青年", "民族", "民族 节奏"),
    (55, "月半小夜曲", "陈乐基", "流行", "流行 怀旧 情感"),
    (56, "风语应", "风子", "民谣", "民谣 自然 治愈"),
    (57, "巴拉莱卡 (The Rod)", "门尼", "摇滚", "摇滚 节奏"),
    (58, "曾经是情侣 (Live)", "梁博", "摇滚", "摇滚 情感 现场"),
    (59, "出现又离开 (Live)", "梁博", "摇滚", "摇滚 情感 现场"),
    (60, "不如见一面", "海来阿木", "流行", "流行 思念 情感"),
]

# ==========================================
# 3. 安全检查
# ==========================================

if not DB_PATH.is_file():
    raise FileNotFoundError(f"没有找到数据库：{DB_PATH}")

if len(SONGS) != 20:
    raise RuntimeError("歌曲数量不是20首，请检查数据。")

song_ids = [song[0] for song in SONGS]

if song_ids != list(range(41, 61)):
    raise RuntimeError("歌曲编号不是41到60，请检查。")

missing_files = []

for song_id in song_ids:
    mp3_path = MUSIC_DIR / f"{song_id}.mp3"

    if not mp3_path.is_file() or mp3_path.stat().st_size == 0:
        missing_files.append(str(mp3_path))

if missing_files:
    print("以下MP3文件缺失或为空：")
    for filename in missing_files:
        print(filename)
    raise RuntimeError("音频文件检查未通过，已停止导入。")

# ==========================================
# 4. 准备数据库记录
# ==========================================

COVER_DIR.mkdir(parents=True, exist_ok=True)

placeholder = COVER_DIR / "new_song_placeholder.svg"

# 没有专辑封面时，使用统一的音乐占位图
if not placeholder.exists():
    placeholder.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg"
        width="400" height="400" viewBox="0 0 400 400">
        <defs>
            <linearGradient id="g" x2="1" y2="1">
                <stop stop-color="#20274d"/>
                <stop offset="1" stop-color="#6532a8"/>
            </linearGradient>
        </defs>
        <rect width="400" height="400" fill="url(#g)"/>
        <circle cx="200" cy="200" r="115"
                fill="#11162d" stroke="#8b5cf6"
                stroke-width="4"/>
        <path d="M225 115v139a30 22 0 1 1 -20 -21V145
                 l95 -24v113a30 22 0 1 1 -20 -21V105Z"
              fill="#c4b5fd"/>
        </svg>""",
        encoding="utf-8"
    )

records = []

for song_id, title, artist, genre, tags in SONGS:

    audio_file = f"music/{song_id}.mp3"

    # 有真实封面就使用真实封面，否则使用默认占位图
    if (COVER_DIR / f"{song_id}.jpg").is_file():
        cover_file = f"covers/{song_id}.jpg"
    elif (COVER_DIR / f"{song_id}.png").is_file():
        cover_file = f"covers/{song_id}.png"
    else:
        cover_file = "covers/new_song_placeholder.svg"

    records.append((
        song_id,
        title,
        artist,
        genre,
        tags,
        audio_file,
        cover_file
    ))

# ==========================================
# 5. 添加歌曲到数据库
# ==========================================

conn = sqlite3.connect(DB_PATH)

try:
    existing = conn.execute(
        """
        SELECT music_id, title
        FROM music
        WHERE music_id BETWEEN 41 AND 60
        """
    ).fetchall()

    if existing:
        raise RuntimeError(
            f"编号41到60已有歌曲，停止导入，避免覆盖：{existing}"
        )

    conn.executemany(
        """
        INSERT INTO music (
            music_id,
            title,
            artist,
            genre,
            tags,
            audio_file,
            cover_file
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        records
    )

    conn.commit()

    total = conn.execute(
        "SELECT COUNT(*) FROM music"
    ).fetchone()[0]

    print("=" * 45)
    print("20首歌曲导入成功！")
    print(f"线上数据库歌曲总数：{total}")
    print("新增歌曲编号：41～60")
    print("=" * 45)

    for song_id, title, artist, _, _ in SONGS:
        print(f"{song_id}. {title} - {artist}")

except Exception:
    conn.rollback()
    raise

finally:
    conn.close()
