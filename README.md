## slack RAG

slackのスレッドをS3にアップロードするシステム

## 実行に必要な環境変数

```shell
AWS_DEFAULT_REGION=ap-northeast-1
AWS_ACCESS_KEY_ID=YOUR_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=YOUR_SECRET_ACCESS_KEY
SLACK_API_USER_TOKEN=xoxp-XXXXXXXXXXXXX
SLACK_CHANNEL_ID=CXXXXXXXXXX
S3_NAME=YOUR_S3_NAME
```

SLACK APIのトークンはBOT用の権限(xoxb-から始まるトークン)でないことに注意
