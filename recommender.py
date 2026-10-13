# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
from pathlib import Path
import sqlite3
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_FILENAME = os.environ.get("MUSIC_DB", "music.db")
DB_PATH = os.path.join(BASE_DIR, DB_FILENAME)

# 读取歌曲数据
def load_ratings():
    conn = sqlite3.connect(DB_PATH)

    ratings = pd.read_sql_query(
        """
        SELECT
            user_id,
            music_id,
            rating
        FROM ratings
        """,
        conn
    )

    conn.close()

    ratings["user_id"] = pd.to_numeric(
        ratings["user_id"],
        errors="coerce"
    )

    ratings["music_id"] = pd.to_numeric(
        ratings["music_id"],
        errors="coerce"
    )

    ratings["rating"] = pd.to_numeric(
        ratings["rating"],
        errors="coerce"
    )

    ratings = ratings.dropna().copy()

    ratings["user_id"] = ratings["user_id"].astype(int)
    ratings["music_id"] = ratings["music_id"].astype(int)

    ratings["rating"] = ratings["rating"].clip(1, 5)

    ratings = ratings.groupby(
        ["user_id", "music_id"],
        as_index=False
    )["rating"].mean()

    return ratings



# 构建用户-音乐评分矩阵
def build_matrix(ratings):
    matrix = ratings.pivot_table(
        index="user_id",
        columns="music_id",
        values="rating",
        aggfunc="mean"
    )
    return matrix


# 计算用户余弦相似度
def calc_similarity(matrix):
    data = matrix.fillna(0).to_numpy(
        dtype=float, copy=True
    )

    norms = np.linalg.norm(data, axis=1)
    norms[norms == 0] = 1

    sim = np.dot(data, data.T) / np.outer(
        norms, norms
    )

    sim = np.clip(sim, 0, 1)
    np.fill_diagonal(sim, 0)

    return pd.DataFrame(
        sim,
        index=matrix.index,
        columns=matrix.index
    )


# 找最相似的用户
def get_similar_users(similarity, user_id, top_n=3):
    if user_id not in similarity.index:
        return pd.Series(dtype=float)

    result = similarity.loc[user_id].copy()
    result = result[result > 0]
    result = result.sort_values(ascending=False)

    return result.head(top_n)


# 个性化推荐
def recommend_music(
        user_id,
        matrix,
        similarity,
        music,
        top_n=5
):
    if user_id not in matrix.index:
        return pd.DataFrame(), pd.Series(dtype=float)

    similar_users = get_similar_users(
        similarity,
        user_id,
        top_n=3
    )

    # 如果没有相似用户，就使用热门推荐
    if similar_users.empty:
        return (
            recommend_popular_for_user(
                user_id, matrix, music, top_n
            ),
            similar_users
        )

    user_mean = matrix.mean(axis=1)
    target_mean = user_mean.loc[user_id]

    rated_music = set(
        matrix.loc[user_id].dropna().index
    )

    scores = {}

    for music_id in matrix.columns:
        if music_id in rated_music:
            continue

        total = 0
        weight = 0

        for other_user, sim_score in similar_users.items():
            rating = matrix.loc[other_user, music_id]

            if pd.isna(rating):
                continue

            diff = rating - user_mean.loc[other_user]

            total += sim_score * diff
            weight += abs(sim_score)

        if weight > 0:
            predict = target_mean + total / weight
            predict = max(1, min(5, predict))
            scores[music_id] = predict

    if not scores:
        return (
            recommend_popular_for_user(
                user_id, matrix, music, top_n
            ),
            similar_users
        )

    sorted_scores = sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True
    )[:top_n]

    result = []

    for music_id, score in sorted_scores:
        info = music[music["music_id"] == music_id]

        if info.empty:
            continue

        row = info.iloc[0]

        result.append({
            "music_id": int(music_id),
            "title": row["title"],
            "artist": row["artist"],
            "genre": row["genre"],
            "tags": row["tags"],
            "audio_file": row["audio_file"],
            "cover_file": row["cover_file"],
            "recommend_score": round(float(score), 2),
            "recommend_type": "协同过滤推荐"
        })

    return pd.DataFrame(result), similar_users


# 给没有推荐结果的用户做热门推荐
def recommend_popular_for_user(
        user_id,
        matrix,
        music,
        top_n=5
):
    rated = set()

    if user_id in matrix.index:
        rated = set(
            matrix.loc[user_id].dropna().index
        )

    count = matrix.notna().sum()
    avg = matrix.mean()

    hot = pd.DataFrame({
        "rating_count": count,
        "average_rating": avg
    })

    hot["popular_score"] = (
        hot["average_rating"]
        * np.log1p(hot["rating_count"])
    )

    hot = hot.sort_values(
        "popular_score",
        ascending=False
    )

    result = []

    for music_id, row_score in hot.iterrows():
        if music_id in rated:
            continue

        info = music[music["music_id"] == music_id]

        if info.empty:
            continue

        row = info.iloc[0]

        result.append({
            "music_id": int(music_id),
            "title": row["title"],
            "artist": row["artist"],
            "genre": row["genre"],
            "tags": row["tags"],
            "audio_file": row["audio_file"],
            "cover_file": row["cover_file"],
            "recommend_score": round(
                float(row_score["popular_score"]), 2
            ),
            "recommend_type": "热门推荐"
        })

        if len(result) >= top_n:
            break

    return pd.DataFrame(result)


# 热门歌曲排行榜
def get_popular_music(ratings, music, top_n=10):
    hot = ratings.groupby("music_id").agg(
        rating_count=("rating", "count"),
        average_rating=("rating", "mean")
    ).reset_index()

    hot["popular_score"] = (
        hot["average_rating"]
        * np.log1p(hot["rating_count"])
    )

    hot = hot.merge(
        music,
        on="music_id",
        how="left"
    )

    hot = hot.sort_values(
        "popular_score",
        ascending=False
    ).head(top_n)

    return hot


# 根据标签和类型给新用户推荐
def recommend_by_interest(
        music,
        ratings,
        genres,
        tags,
        top_n=8
):
    genres = set(genres)
    tags = set(tags)

    hot = ratings.groupby("music_id").agg(
        rating_count=("rating", "count"),
        average_rating=("rating", "mean")
    ).reset_index()

    hot["popular_score"] = (
        hot["average_rating"]
        * np.log1p(hot["rating_count"])
    )

    data = music.merge(
        hot,
        on="music_id",
        how="left"
    )

    data["popular_score"] = data[
        "popular_score"
    ].fillna(0)

    max_hot = data["popular_score"].max()
    if pd.isna(max_hot) or max_hot == 0:
        max_hot = 1

    result = []

    for _, row in data.iterrows():
        score = 0

        if row["genre"] in genres:
            score += 2

        song_tags = set(
            str(row["tags"]).replace(",", " ").split()
        )

        score += len(tags & song_tags)

        # 加一点热门度，避免很多歌曲同分
        score += (
            0.5
            * row["popular_score"]
            / max_hot
        )

        if genres or tags:
            if score <= 0.5:
                continue

        result.append({
            "music_id": int(row["music_id"]),
            "title": row["title"],
            "artist": row["artist"],
            "genre": row["genre"],
            "tags": row["tags"],
            "audio_file": row["audio_file"],
            "cover_file": row["cover_file"],
            "recommend_score": round(float(score), 2),
            "recommend_type": "兴趣推荐"
        })

    result = sorted(
        result,
        key=lambda x: x["recommend_score"],
        reverse=True
    )[:top_n]

    return pd.DataFrame(result)


# 搜索歌曲
def search_music(music, keyword="", genre=""):
    result = music.copy()

    keyword = keyword.strip()

    if keyword:
        mask = (
            result["title"].astype(str).str.contains(
                keyword, case=False, na=False
            )
            |
            result["artist"].astype(str).str.contains(
                keyword, case=False, na=False
            )
            |
            result["tags"].astype(str).str.contains(
                keyword, case=False, na=False
            )
        )

        result = result[mask]

    if genre:
        result = result[
            result["genre"] == genre
        ]

    return result


# 保存用户评分
def save_rating(user_id, music_id, rating):
    user_id = int(user_id)
    music_id = int(music_id)
    rating = float(rating)

    if rating < 1 or rating > 5:
        raise ValueError("评分只能是 1 到 5 分")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO ratings (
            user_id,
            music_id,
            rating
        )
        VALUES (?, ?, ?)

        ON CONFLICT(user_id, music_id)
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


# 数据统计
def get_statistics(music, ratings, matrix):
    density = 0

    if matrix.size > 0:
        density = (
            matrix.notna().sum().sum()
            / matrix.size
            * 100
        )

    return {
        "user_count":
            ratings["user_id"].nunique(),

        "music_count":
            music["music_id"].nunique(),

        "rating_count":
            len(ratings),

        "average_rating":
            round(ratings["rating"].mean(), 2),

        "max_rating":
            ratings["rating"].max(),

        "min_rating":
            ratings["rating"].min(),

        "matrix_rows":
            matrix.shape[0],

        "matrix_cols":
            matrix.shape[1],

        "matrix_density":
            round(density, 2)
    }


# 一次性初始化全部数据
def load_all_data():
    # 连接 SQLite 数据库
    conn = sqlite3.connect(DB_PATH)

    # 从数据库读取歌曲
    music = pd.read_sql_query(
        """
        SELECT
            music_id,
            title,
            artist,
            genre,
            tags,
            audio_file,
            cover_file
        FROM music
        ORDER BY music_id
        """,
        conn
    )

    # 从数据库读取评分
    ratings = pd.read_sql_query(
        """
        SELECT
            user_id,
            music_id,
            rating
        FROM ratings
        """,
        conn
    )

    conn.close()

    # 只保留歌曲库中实际存在的歌曲评分
    valid_ids = set(music["music_id"])

    ratings = ratings[
        ratings["music_id"].isin(valid_ids)
    ].copy()

    # 构建 用户-歌曲 评分矩阵
    matrix = build_matrix(ratings)

    # 计算用户相似度
    similarity = calc_similarity(matrix)

    return music, ratings, matrix, similarity