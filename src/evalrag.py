# 外部ライブラリをインポート
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import FAISS
from langchain_aws import ChatBedrockConverse, BedrockEmbeddings

from datasets import Dataset
from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.metrics import (
    answer_relevancy,
    faithfulness,
    context_recall,
    context_precision,
)

# LLMと埋め込みモデルを設定
llm = ChatBedrockConverse(model="anthropic.claude-3-5-sonnet-20240620-v1:0")
embeddings = BedrockEmbeddings(model_id="amazon.titan-embed-text-v2:0")

# chunkデータをそのまま社内情報として活用
chunk = [
    {
        "topic": "たかこってさ、わるいやつだよな",
        "messages": [
            {
                "user": "dummy",
                "text": "たかこってさ、わるいやつだよな",
                "datetime": "2025-01-09T22:01:20.581349"
            },
            {
                "user": "dummy",
                "text": "とかいうやつおおい、本当はいい人なのに。彼は男の中の男だ。",
                "datetime": "2025-01-09T22:01:45.458769"
            },
            {
                "user": "dummy",
                "text": "正義感が強く、よく子どもの後をつけては、助ける機会を伺っている。",
                "datetime": "2025-01-09T22:02:10.123456"
            }
        ]
    }
]

# chunk全体を文字列に変換
chunk_as_string = str(chunk)

# ベクトルDBに渡す文字列として扱う
# texts = [entry["messages"] for entry in chunk]
texts = [chunk_as_string]

# ベクトルDBをローカルPC上に作成
vectorstore = FAISS.from_texts(texts=texts,embedding=embeddings)

# RAGの検索対象としてベクトルDBを指定
retriever = vectorstore.as_retriever()

# プロンプトテンプレートを定義
prompt = ChatPromptTemplate.from_template(
    "背景情報をもとに質問に回答してください。背景情報： {context} 質問： {question}"
)

# RAGを使ったLangChainチェーンを定義
chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# 質問文を入れてチェーンを実行
question = "たかこは男の中の男と認識されていますか？"
answer = chain.invoke(question)

# LLMからの出力を表示
print(answer)

# 評価対象のデータセットを定義
dataset = Dataset.from_dict({
    "question": [question],
    "answer": [answer],
    "contexts": [texts],
    "ground_truth": ["たかこは、正義感が強く、多くの人から「男の中の男」と称されています。"],
})

# 評価を実行
result = evaluate(
    dataset,
    metrics=[
        faithfulness, # 忠実性：背景情報と一貫性のある回答ができているか
        answer_relevancy, # 関連性：質問と関連した回答ができているか
        context_precision, # 文脈精度：質問や正解に関連した背景情報を取得できているか
        context_recall, # 文脈回収：回答に必要な背景情報をすべて取得できているか
    ],
    llm=LangchainLLMWrapper(llm),
    embeddings=LangchainEmbeddingsWrapper(embeddings),
)

# 評価結果を表示
print(result)
