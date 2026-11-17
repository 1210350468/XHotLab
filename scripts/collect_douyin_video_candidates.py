import argparse
from datetime import datetime

import httpx


API = "http://127.0.0.1:8000"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-id", type=int, required=True)
    parser.add_argument("--keyword", action="append", required=True)
    options = parser.parse_args()
    with httpx.Client(base_url=API, timeout=30, trust_env=False) as client:
        accounts = client.get("/api/accounts")
        accounts.raise_for_status()
        match = [
            item for item in accounts.json()
            if item["id"] == options.account_id
            and item["platform"] == "douyin"
            and item["status"] == "active"
        ]
        if len(match) != 1:
            raise ValueError("抖音账号尚未处于有效登录状态")
        values = {
            "platform": "douyin",
            "account_id": options.account_id,
            "source_type": "keyword",
            "source_name": "XHotLab 视频选题 " + datetime.now().strftime("%m-%d"),
            "keywords": options.keyword,
            "max_contents_per_keyword": 15,
            "max_pages_per_keyword": 4,
            "stagnant_pages": 2,
            "search_sort": "most_liked",
            "publish_time": "week",
            "content_type": "video",
            "min_likes": 1000,
            "min_comments": 0,
            "max_comments_per_content": 0,
            "include_replies": False,
            "download_media": False,
        }
        response = client.post("/api/collections", json=values)
        response.raise_for_status()
        job = response.json()
        print("CREATORHUB_DOUYIN_JOB", job["id"], job["status"],
              "keywords", ",".join(options.keyword))


if __name__ == "__main__":
    main()
