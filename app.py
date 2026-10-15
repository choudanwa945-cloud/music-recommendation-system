# -*- coding: utf-8 -*-

import os
import sqlite3

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from werkzeug.utils import secure_filename

from recommender import (
    load_all_data,
    get_popular_music,
    recommend_music,
    recommend_by_interest,
    search_music,
    save_rating,
    get_statistics
)


# =========================
# Flask 应用
# =========================
app = Flask(__name__)


# =========================
# 项目路径
# =========================
BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


# =========================
# 数据库配置
# =========================
DB_FILENAME = os.environ.get(
    "MUSIC_DB",
    "music.db"
)

DB_PATH = os.path.join(
    BASE_DIR,
    DB_FILENAME
)


# =========================
# Flask Session 密钥
# =========================
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "music123"
)


# =========================
# 用户背景上传配置
# =========================
UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "static",
    "backgrounds"
)

# 允许作为背景上传的文件格式
ALLOWED_BACKGROUND_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp",
    "gif",
    "mp4",
    "webm"
}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# 最大上传文件大小：50MB
app.config["MAX_CONTENT_LENGTH"] = (
    50 * 1024 * 1024
)

# 如果 backgrounds 文件夹不存在，
# 程序启动时自动创建
os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


# =========================
# 程序启动时加载数据
# =========================
music_df, ratings_df, rating_matrix, similarity = (
    load_all_data()
)


# =========================
# 评分修改以后重新加载数据
# =========================
def refresh_data():
    global music_df
    global ratings_df
    global rating_matrix
    global similarity

    (
        music_df,
        ratings_df,
        rating_matrix,
        similarity
    ) = load_all_data()


# =========================
# 检查背景文件格式
# =========================
def allowed_background_file(filename):
    return (
        "." in filename
        and
        filename.rsplit(
            ".",
            1
        )[1].lower()
        in ALLOWED_BACKGROUND_EXTENSIONS
    )


# =========================
# 每次请求刷新推荐数据
# =========================
@app.before_request
def auto_refresh_data():
    refresh_data()

    # 默认背景
    session["background_type"] = "default"
    session["background_file"] = ""

    # 登录用户读取自己的背景设置
    if "user_id" in session:

        conn = sqlite3.connect(
            DB_PATH
        )

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                background_type,
                background_file
            FROM users
            WHERE user_id = ?
            """,
            (
                int(
                    session["user_id"]
                ),
            )
        )

        row = cursor.fetchone()

        conn.close()

        if row is not None:

            session["background_type"] = (
                row[0]
                or "default"
            )

            session["background_file"] = (
                row[1]
                or ""
            )


# =========================
# 注册
# 数据保存到 SQLite
# =========================
@app.route(
    '/register',
    methods=['GET', 'POST']
)
def register():

    if request.method == 'POST':

        username = request.form.get(
            'username',
            ''
        ).strip()

        password = request.form.get(
            'password',
            ''
        ).strip()

        # 用户名和密码不能为空
        if username == '' or password == '':

            flash(
                '用户名和密码不能为空',
                'error'
            )

            return redirect(
                url_for('register')
            )

        # 连接数据库
        conn = sqlite3.connect(
            DB_PATH
        )

        cursor = conn.cursor()

        # 检查用户名是否已经存在
        cursor.execute(
            """
            SELECT user_id
            FROM users
            WHERE username = ?
            """,
            (username,)
        )

        existing_user = (
            cursor.fetchone()
        )

        if existing_user is not None:

            conn.close()

            flash(
                '这个用户名已经被注册了',
                'error'
            )

            return redirect(
                url_for('register')
            )

        # 自动生成新的 user_id
        cursor.execute(
            """
            SELECT MAX(user_id)
            FROM users
            """
        )

        max_user_id = (
            cursor.fetchone()[0]
        )

        # 1～30号保留给原测试用户
        if max_user_id is None:

            new_user_id = 31

        else:

            new_user_id = max(
                max_user_id + 1,
                31
            )

        # 密码加密
        password_hash = (
            generate_password_hash(
                password
            )
        )

        # 写入数据库
        cursor.execute(
            """
            INSERT INTO users (
                user_id,
                username,
                password
            )
            VALUES (?, ?, ?)
            """,
            (
                new_user_id,
                username,
                password_hash
            )
        )

        conn.commit()
        conn.close()

        refresh_data()

        flash(
            '注册成功，请登录',
            'success'
        )

        return redirect(
            url_for('login')
        )

    return render_template(
        'register.html'
    )


# =========================
# 登录
# 从 SQLite 查询用户
# =========================
@app.route(
    '/login',
    methods=['GET', 'POST']
)
def login():

    if request.method == 'POST':

        username = request.form.get(
            'username',
            ''
        ).strip()

        password = request.form.get(
            'password',
            ''
        ).strip()

        # 连接数据库
        conn = sqlite3.connect(
            DB_PATH
        )

        cursor = conn.cursor()

        # 根据用户名查询用户
        cursor.execute(
            """
            SELECT
                user_id,
                username,
                password
            FROM users
            WHERE username = ?
            """,
            (username,)
        )

        user = cursor.fetchone()

        conn.close()

        # 用户不存在
        if user is None:

            flash(
                '用户名不存在',
                'error'
            )

            return redirect(
                url_for('login')
            )

        user_id = user[0]
        db_username = user[1]
        password_hash = user[2]

        # 验证密码
        if not check_password_hash(
            password_hash,
            password
        ):

            flash(
                '密码错误',
                'error'
            )

            return redirect(
                url_for('login')
            )

        # 登录成功
        session['user_id'] = (
            user_id
        )

        session['username'] = (
            db_username
        )

        return redirect(
            url_for('index')
        )

    return render_template(
        'login.html'
    )


# =========================
# 退出登录
# =========================
@app.route('/logout')
def logout():

    session.clear()

    return redirect(
        url_for('index')
    )


# =========================
# 首页
# =========================
@app.route("/")
def index():

    users = (
        rating_matrix
        .index
        .tolist()
    )

    stats = get_statistics(
        music_df,
        ratings_df,
        rating_matrix
    )

    return render_template(
        "index.html",
        users=users,
        stats=stats
    )


# =========================
# 热门音乐
# =========================
@app.route("/popular")
def popular():

    result = get_popular_music(
        ratings_df,
        music_df,
        top_n=10
    )

    return render_template(
        "popular.html",
        songs=result.to_dict(
            "records"
        )
    )


# =========================
# 个性化推荐
# =========================
@app.route("/recommend")
def recommend():

    # 没有登录时先去登录
    if 'user_id' not in session:

        return redirect(
            url_for('login')
        )

    # 当前登录用户
    user_id = int(
        session['user_id']
    )

    # 如果还没有评分记录
    if user_id not in rating_matrix.index:

        return render_template(
            "recommend.html",
            users=[],
            user_id=user_id,
            songs=None,
            similar_users=[]
        )

    # 生成推荐
    result, similar = (
        recommend_music(
            user_id,
            rating_matrix,
            similarity,
            music_df,
            top_n=5
        )
    )

    similar_users = []

    for uid, score in (
        similar.items()
    ):

        similar_users.append({
            "user_id": int(uid),
            "score": round(
                float(score),
                3
            )
        })

    return render_template(
        "recommend.html",
        users=[],
        user_id=user_id,
        songs=result.to_dict(
            "records"
        ),
        similar_users=(
            similar_users
        )
    )


# =========================
# 兴趣推荐
# =========================
@app.route(
    "/interest",
    methods=["GET", "POST"]
)
def interest():

    genres = sorted(
        music_df[
            "genre"
        ]
        .dropna()
        .unique()
        .tolist()
    )

    tag_set = set()

    for text in music_df[
        "tags"
    ].fillna(""):

        for tag in str(
            text
        ).split():

            tag_set.add(
                tag
            )

    tags = sorted(
        tag_set
    )

    songs = None

    selected_genres = []
    selected_tags = []

    if request.method == "POST":

        selected_genres = (
            request.form.getlist(
                "genres"
            )
        )

        selected_tags = (
            request.form.getlist(
                "tags"
            )
        )

        result = (
            recommend_by_interest(
                music_df,
                ratings_df,
                selected_genres,
                selected_tags
            )
        )

        songs = result.to_dict(
            "records"
        )

    return render_template(
        "interest.html",
        genres=genres,
        tags=tags,
        songs=songs,
        selected_genres=(
            selected_genres
        ),
        selected_tags=(
            selected_tags
        )
    )


# =========================
# 歌曲库
# =========================
@app.route("/library")
def library():

    keyword = request.args.get(
        "q",
        ""
    )

    genre = request.args.get(
        "genre",
        ""
    )

    result = search_music(
        music_df,
        keyword,
        genre
    )

    genres = sorted(
        music_df[
            "genre"
        ]
        .dropna()
        .unique()
        .tolist()
    )

    return render_template(
        "library.html",
        songs=result.to_dict(
            "records"
        ),
        keyword=keyword,
        genre=genre,
        genres=genres
    )


# =========================
# 我的评分
# =========================
@app.route("/my-ratings")
def my_ratings():

    # 没有登录时先去登录
    if 'user_id' not in session:

        return redirect(
            url_for('login')
        )

    user_id = int(
        session['user_id']
    )

    # 当前用户评分
    user_ratings = (
        ratings_df[
            ratings_df[
                "user_id"
            ] == user_id
        ].copy()
    )

    # 没有评分
    if user_ratings.empty:

        return render_template(
            "my_ratings.html",
            ratings=[]
        )

    # 和歌曲信息合并
    result = (
        user_ratings.merge(
            music_df,
            on="music_id",
            how="left"
        )
    )

    return render_template(
        "my_ratings.html",
        ratings=result.to_dict(
            "records"
        )
    )


# =========================
# 个人中心
# =========================
@app.route("/profile")
def profile():

    # 没有登录时先去登录
    if 'user_id' not in session:

        return redirect(
            url_for('login')
        )

    user_id = int(
        session['user_id']
    )

    username = session[
        'username'
    ]

    # 已评分歌曲数量
    rating_count = len(
        ratings_df[
            ratings_df[
                "user_id"
            ] == user_id
        ]
    )

    return render_template(
        "profile.html",
        user_id=user_id,
        username=username,
        rating_count=rating_count
    )


# =========================
# 修改密码
# 使用 SQLite
# =========================
@app.route(
    "/change-password",
    methods=["GET", "POST"]
)
def change_password():

    # 没有登录时先去登录
    if 'user_id' not in session:

        return redirect(
            url_for('login')
        )

    if request.method == "POST":

        old_password = (
            request.form.get(
                "old_password",
                ""
            ).strip()
        )

        new_password = (
            request.form.get(
                "new_password",
                ""
            ).strip()
        )

        confirm_password = (
            request.form.get(
                "confirm_password",
                ""
            ).strip()
        )

        # 检查是否为空
        if (
            old_password == ""
            or
            new_password == ""
        ):

            flash(
                "密码不能为空",
                "error"
            )

            return redirect(
                url_for(
                    "change_password"
                )
            )

        # 两次新密码必须一致
        if (
            new_password
            !=
            confirm_password
        ):

            flash(
                "两次输入的新密码不一致",
                "error"
            )

            return redirect(
                url_for(
                    "change_password"
                )
            )

        user_id = int(
            session["user_id"]
        )

        # 连接数据库
        conn = sqlite3.connect(
            DB_PATH
        )

        cursor = conn.cursor()

        # 查询当前用户密码
        cursor.execute(
            """
            SELECT password
            FROM users
            WHERE user_id = ?
            """,
            (user_id,)
        )

        user = cursor.fetchone()

        # 用户不存在
        if user is None:

            conn.close()

            flash(
                "没有找到当前用户",
                "error"
            )

            return redirect(
                url_for(
                    "change_password"
                )
            )

        old_password_hash = (
            user[0]
        )

        # 验证原密码
        if not check_password_hash(
            old_password_hash,
            old_password
        ):

            conn.close()

            flash(
                "原密码错误",
                "error"
            )

            return redirect(
                url_for(
                    "change_password"
                )
            )

        # 生成新的加密密码
        new_password_hash = (
            generate_password_hash(
                new_password
            )
        )

        # 更新数据库
        cursor.execute(
            """
            UPDATE users
            SET password = ?
            WHERE user_id = ?
            """,
            (
                new_password_hash,
                user_id
            )
        )

        conn.commit()
        conn.close()

        # 修改成功后退出登录
        session.clear()

        flash(
            "密码修改成功，请使用新密码重新登录",
            "success"
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "change_password.html"
    )


# =========================
# 个性化背景设置
# =========================
@app.route(
    "/background-settings",
    methods=["GET", "POST"]
)
def background_settings():

    # 未登录不能设置背景
    if "user_id" not in session:
        return redirect(
            url_for("login")
        )

    user_id = int(
        session["user_id"]
    )

    conn = sqlite3.connect(
        DB_PATH
    )
    cursor = conn.cursor()

    # =========================
    # 保存背景
    # =========================
    if request.method == "POST":

        action = request.form.get(
            "action",
            "upload"
        )

        # -------------------------
        # 恢复默认背景
        # -------------------------
        if action == "reset":

            cursor.execute(
                """
                SELECT background_file
                FROM users
                WHERE user_id = ?
                """,
                (user_id,)
            )

            old_row = cursor.fetchone()

            # 删除旧背景文件
            if old_row is not None:
                old_file = old_row[0]

                if old_file:
                    old_path = os.path.join(
                        app.config[
                            "UPLOAD_FOLDER"
                        ],
                        old_file
                    )

                    if os.path.isfile(
                        old_path
                    ):
                        try:
                            os.remove(
                                old_path
                            )
                        except OSError:
                            pass

            # 清空数据库背景设置
            cursor.execute(
                """
                UPDATE users
                SET background_type = 'default',
                    background_file = ''
                WHERE user_id = ?
                """,
                (user_id,)
            )

            conn.commit()
            conn.close()

            flash(
                "已恢复默认背景",
                "success"
            )

            return redirect(
                url_for(
                    "background_settings"
                )
            )

        # -------------------------
        # 获取用户上传文件
        # -------------------------
        background = (
            request.files.get(
                "background_file"
            )
        )

        if (
            background is None
            or
            background.filename == ""
        ):
            conn.close()

            flash(
                "请先选择一个背景文件",
                "error"
            )

            return redirect(
                url_for(
                    "background_settings"
                )
            )

        # -------------------------
        # 检查文件格式
        # -------------------------
        if not allowed_background_file(
            background.filename
        ):
            conn.close()

            flash(
                "文件格式不支持，请上传 JPG、PNG、WEBP、GIF、MP4 或 WEBM 文件",
                "error"
            )

            return redirect(
                url_for(
                    "background_settings"
                )
            )

        # -------------------------
        # 获取扩展名
        # -------------------------
        extension = (
            background.filename
            .rsplit(".", 1)[1]
            .lower()
        )

        # 判断背景类型
        if extension == "gif":
            background_type = "gif"

        elif extension in {
            "mp4",
            "webm"
        }:
            background_type = "video"

        else:
            background_type = "image"

        # -------------------------
        # 生成安全、唯一的文件名
        # -------------------------
        filename = secure_filename(
            f"user_{user_id}_background.{extension}"
        )

        save_path = os.path.join(
            app.config[
                "UPLOAD_FOLDER"
            ],
            filename
        )

        # -------------------------
        # 查询旧背景
        # -------------------------
        cursor.execute(
            """
            SELECT background_file
            FROM users
            WHERE user_id = ?
            """,
            (user_id,)
        )

        old_row = cursor.fetchone()

        old_file = ""

        if old_row is not None:
            old_file = (
                old_row[0]
                or ""
            )

        # -------------------------
        # 保存新背景文件
        # -------------------------
        background.save(
            save_path
        )

        # -------------------------
        # 如果扩展名发生变化，
        # 删除旧背景文件
        # -------------------------
        if (
            old_file
            and
            old_file != filename
        ):

            old_path = os.path.join(
                app.config[
                    "UPLOAD_FOLDER"
                ],
                old_file
            )

            if os.path.isfile(
                old_path
            ):
                try:
                    os.remove(
                        old_path
                    )
                except OSError:
                    pass

        # -------------------------
        # 更新数据库
        # -------------------------
        cursor.execute(
            """
            UPDATE users
            SET background_type = ?,
                background_file = ?
            WHERE user_id = ?
            """,
            (
                background_type,
                filename,
                user_id
            )
        )

        conn.commit()
        conn.close()

        flash(
            "背景上传成功",
            "success"
        )

        return redirect(
            url_for(
                "background_settings"
            )
        )

    # =========================
    # GET：读取当前背景
    # =========================
    cursor.execute(
        """
        SELECT
            background_type,
            background_file
        FROM users
        WHERE user_id = ?
        """,
        (user_id,)
    )

    row = cursor.fetchone()

    conn.close()

    if row is None:
        background_type = "default"
        background_file = ""

    else:
        background_type = (
            row[0]
            or "default"
        )

        background_file = (
            row[1]
            or ""
        )

    return render_template(
        "background_settings.html",
        background_type=background_type,
        background_file=background_file
    )
# =========================
# 保存 / 修改评分
# 使用 SQLite
# =========================
@app.route(
    "/rate",
    methods=["POST"]
)
def rate():

    # 未登录不能评分
    if 'user_id' not in session:

        return redirect(
            url_for('login')
        )

    user_id = int(
        session['user_id']
    )

    music_id = (
        request.form.get(
            "music_id",
            type=int
        )
    )

    rating = (
        request.form.get(
            "rating",
            type=float
        )
    )

    next_page = (
        request.form.get(
            "next"
        )
    )

    if next_page is None:

        next_page = url_for(
            "library"
        )

    # 基础检查
    if (
        music_id is None
        or
        rating is None
    ):

        flash(
            "评分数据不完整",
            "error"
        )

        return redirect(
            next_page
        )

    if (
        rating < 1
        or
        rating > 5
    ):

        flash(
            "评分必须在 1 到 5 分之间",
            "error"
        )

        return redirect(
            next_page
        )

    try:

        # 连接数据库
        conn = sqlite3.connect(
            DB_PATH
        )

        cursor = conn.cursor()

        # 有评分就更新，没有就新增
        cursor.execute(
            """
            INSERT INTO ratings (
                user_id,
                music_id,
                rating
            )
            VALUES (?, ?, ?)

            ON CONFLICT(
                user_id,
                music_id
            )
            DO UPDATE SET
                rating = excluded.rating
            """,
            (
                user_id,
                music_id,
                rating
            )
        )

        conn.commit()
        conn.close()

        flash(
            "评分保存成功",
            "success"
        )

    except Exception as e:

        flash(
            f"评分保存失败：{e}",
            "error"
        )

    return redirect(
        next_page
    )


# =========================
# 删除评分
# 使用 SQLite
# =========================
@app.route(
    "/delete-rating",
    methods=["POST"]
)
def delete_rating():

    # 没有登录时先去登录
    if 'user_id' not in session:

        return redirect(
            url_for('login')
        )

    user_id = int(
        session['user_id']
    )

    music_id = (
        request.form.get(
            "music_id",
            type=int
        )
    )

    try:

        # 连接数据库
        conn = sqlite3.connect(
            DB_PATH
        )

        cursor = conn.cursor()

        # 删除当前用户对这首歌的评分
        cursor.execute(
            """
            DELETE FROM ratings
            WHERE user_id = ?
            AND music_id = ?
            """,
            (
                user_id,
                music_id
            )
        )

        conn.commit()
        conn.close()

        # 重新读取最新数据库数据
        refresh_data()

        flash(
            "评分删除成功",
            "success"
        )

    except Exception as e:

        flash(
            f"评分删除失败：{e}",
            "error"
        )

    return redirect(
        url_for("my_ratings")
    )


# =========================
# 数据统计
# =========================
@app.route("/statistics")
def statistics():

    stats = get_statistics(
        music_df,
        ratings_df,
        rating_matrix
    )

    return render_template(
        "statistics.html",
        stats=stats
    )


# =========================
# 系统说明
# =========================
@app.route("/about")
def about():

    return render_template(
        "about.html"
    )


# =========================
# robots.txt
# =========================
@app.route("/robots.txt")
def robots():

    return app.send_static_file(
        "robots.txt"
    )


# =========================
# sitemap.xml
# =========================
@app.route("/sitemap.xml")
def sitemap():

    return app.send_static_file(
        "sitemap.xml"
    )


# =========================
# Google Search Console 验证
# =========================
@app.route(
    "/googlebd10ec1f502b5bde.html"
)
def google_verify():

    return app.send_static_file(
        "googlebd10ec1f502b5bde.html"
    )


# =========================
# 启动程序
# =========================
if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )