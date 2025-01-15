import os
import json
import boto3
from slack_sdk import WebClient
from datetime import datetime
import hashlib
from typing import Any, Dict, List, NoReturn, Optional

# Slack APIクライアント
slack_token: str = os.environ["SLACK_API_USER_TOKEN"]
client: WebClient = WebClient(token=slack_token)

# AWS S3クライアント
s3 = boto3.client('s3')
bucket_name: str = os.environ["S3_NAME"]

MiB: int = 1024 ** 2
MAX_FILE_SIZE: int = 10 * MiB


def generate_file_name(channel_name: str, channel_id: str) -> str:
    """タイムスタンプとハッシュ値でファイル名を生成"""
    timestamp: int = int(datetime.now().timestamp())
    hash_value: str = hashlib.md5(f"{channel_name}_{channel_id}_{timestamp}".encode()).hexdigest()
    return f"slack_history/{channel_name}/{channel_id}/{timestamp}_{hash_value}.json"


def fetch_users() -> Dict[str, str]:
    """Slack APIからユーザーリストを取得"""
    response: Dict[str, Any] = client.users_list()
    return {user["id"]: user["name"] for user in response["members"]}


def fetch_thread_replies(channel_id: str, thread_ts: str) -> List[Dict[str, Any]]:
    """スレッド内の返信メッセージを取得"""
    replies: List[Dict[str, Any]] = client.conversations_replies(channel=channel_id, ts=thread_ts)["messages"]
    for reply in replies:
        reply["datetime"] = datetime.fromtimestamp(float(reply["ts"])).isoformat()
    return replies


def fetch_channel_history(channel_id: str, users: Dict[str, str], start_time: Optional[float] = None) -> List[Dict[str, Any]]:
    """Slack APIから履歴を取得し、スレッド情報を構造化"""
    latest_ts: float = datetime.now().timestamp()
    messages: List[Dict[str, Any]] = []
    while True:
        params: Dict[str, Any] = {
            "channel": channel_id,
            "limit": 1000,
            "latest": str(latest_ts)
        }
        if start_time:
            params["oldest"] = str(start_time)
        response: Dict[str, Any] = client.conversations_history(**params)
        messages.extend(response["messages"])
        if not response["has_more"]:
            break
        latest_ts = float(response["messages"][-1]["ts"])

    structured_data: List[Dict[str, Any]] = []

    for message in messages:
        if "reply_broadcast" in message and message["reply_broadcast"]:
            continue

        if "thread_ts" in message and message["thread_ts"] == message["ts"]:
            thread_replies: List[Dict[str, Any]] = fetch_thread_replies(channel_id, message["ts"])
            topic_data: Dict[str, Any] = {
                "topic": normalize_slack_text(message.get("text", ""), users),
                "messages": [
                    {
                        "user": users.get(message.get("user", "unknown"), "unknown"),
                        "text": normalize_slack_text(message.get("text", ""), users),
                        "datetime": datetime.fromtimestamp(float(message["ts"])).isoformat()
                    }
                ]
            }
            for reply in thread_replies[1:]:
                topic_data["messages"].append({
                    "user": users.get(reply.get("user", "unknown"), "unknown"),
                    "text": normalize_slack_text(reply.get("text", ""), users),
                    "datetime": reply["datetime"]
                })
            structured_data.append(topic_data)

    return structured_data


def normalize_slack_text(text: str, users: Dict[str, str]) -> str:
    """Slackの特殊フォーマットを展開"""
    for user_id, user_name in users.items():
        text = text.replace(f"<@{user_id}>", f"@{user_name}")
    return text


def get_latest_timestamp(channel_id: str, channel_name: str) -> Optional[int]:
    """S3内の最新のタイムスタンプを取得"""
    prefix: str = f"slack_history/{channel_name}/{channel_id}/"
    response: Dict[str, Any] = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    if "Contents" not in response:
        return None
    timestamps: List[int] = []
    for obj in response["Contents"]:
        file_name: str = obj["Key"].split("/")[-1]
        try:
            timestamp: int = int(file_name.split("_")[0])
            timestamps.append(timestamp)
        except ValueError:
            pass
    return max(timestamps) if timestamps else None


def save_to_s3(data: List[Dict[str, Any]], channel_id: str, channel_name: str) -> None:
    """データをS3に保存、容量単位で分割"""
    total_size: int = 0
    file_data: List[Dict[str, Any]] = []

    for entry in data:
        entry_size: int = len(json.dumps(entry, ensure_ascii=False).encode('utf-8'))
        if total_size + entry_size > MAX_FILE_SIZE and file_data:
            file_name: str = generate_file_name(channel_name, channel_id)
            s3.put_object(
                Bucket=bucket_name,
                Key=file_name,
                Body=json.dumps(file_data, ensure_ascii=False, indent=2),
                ContentType="application/json"
            )
            print(f"Saved to S3: {file_name}")
            file_data = []
            total_size = 0
        total_size += entry_size
        file_data.append(entry)

    if file_data:
        file_name: str = generate_file_name(channel_name, channel_id)
        s3.put_object(
            Bucket=bucket_name,
            Key=file_name,
            Body=json.dumps(file_data, ensure_ascii=False, indent=2),
            ContentType="application/json"
        )
        print(f"Saved to S3: {file_name}")


def main() -> NoReturn:
    # チャンネル一覧を取得して履歴を保存
    users: Dict[str, str] = fetch_users()
    response: Dict[str, Any] = client.conversations_list()
    for channel in response["channels"]:
        if channel["is_member"]:
            channel_id: str = channel["id"]
            if channel_id == os.environ["SLACK_CHANNEL_ID"]:
                channel_name: str = channel.get("name", "unknown_channel")
                latest_ts: Optional[int] = get_latest_timestamp(channel_id, channel_name)
                start_time: Optional[float] = latest_ts if latest_ts else None
                history: List[Dict[str, Any]] = fetch_channel_history(channel_id, users, start_time=start_time)
                save_to_s3(history, channel_id, channel_name)


if __name__ == "__main__":
    main()