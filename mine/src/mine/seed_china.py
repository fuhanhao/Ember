"""Seed script: import China region data sources."""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from mine.config import settings
from mine.models import DataSource

SEEDS = [
    # === AI 垂直媒体 (RSS) ===
    {
        "id": "C-MEDIA-JIQIZHIXIN",
        "name": "机器之心",
        "region": "china",
        "tier": "t1",
        "crawler_type": "rss",
        "crawler_config": {"feed_url": "https://www.jiqizhixin.com/rss"},
        "poll_interval_seconds": 1800,
    },
    {
        "id": "C-MEDIA-LEIPHONE",
        "name": "量子位",
        "region": "china",
        "tier": "t1",
        "crawler_type": "rss",
        "crawler_config": {"feed_url": "https://www.qbitai.com/feed"},
        "poll_interval_seconds": 1800,
    },
    {
        "id": "C-MEDIA-XINZHIYUAN",
        "name": "新智元",
        "region": "china",
        "tier": "t1",
        "crawler_type": "rss",
        "crawler_config": {"feed_url": "https://www.xinzhiyuan.com/feed"},
        "poll_interval_seconds": 3600,
    },

    # === 商业科技媒体 (RSS) ===
    {
        "id": "C-MEDIA-36KR",
        "name": "36氪",
        "region": "china",
        "tier": "t1",
        "crawler_type": "rss",
        "crawler_config": {"feed_url": "https://36kr.com/feed"},
        "poll_interval_seconds": 1800,
    },
    {
        "id": "C-MEDIA-GEEKPARK",
        "name": "极客公园",
        "region": "china",
        "tier": "t1",
        "crawler_type": "rss",
        "crawler_config": {"feed_url": "https://www.geekpark.net/rss"},
        "poll_interval_seconds": 3600,
    },
    {
        "id": "C-MEDIA-HUXIU",
        "name": "虎嗅",
        "region": "china",
        "tier": "t2",
        "crawler_type": "rss",
        "crawler_config": {"feed_url": "https://www.huxiu.com/rss/0.xml"},
        "poll_interval_seconds": 3600,
    },
    {
        "id": "C-MEDIA-TMTPOST",
        "name": "钛媒体",
        "region": "china",
        "tier": "t2",
        "crawler_type": "rss",
        "crawler_config": {"feed_url": "https://www.tmtpost.com/rss.xml"},
        "poll_interval_seconds": 3600,
    },

    # === 国产大模型 (GitHub Releases) ===
    {
        "id": "C-LLM-DEEPSEEK",
        "name": "DeepSeek",
        "region": "china",
        "tier": "t1",
        "crawler_type": "github_api",
        "crawler_config": {"mode": "releases", "repos": ["deepseek-ai/DeepSeek-LLM", "deepseek-ai/DeepSeek-Coder", "deepseek-ai/DeepSeek-V3"]},
        "poll_interval_seconds": 3600,
    },
    {
        "id": "C-LLM-QWEN",
        "name": "Qwen (通义千问)",
        "region": "china",
        "tier": "t1",
        "crawler_type": "github_api",
        "crawler_config": {"mode": "releases", "repos": ["QwenLM/Qwen", "QwenLM/Qwen2"]},
        "poll_interval_seconds": 3600,
    },
    {
        "id": "C-LLM-ZHIPU",
        "name": "智谱 GLM",
        "region": "china",
        "tier": "t1",
        "crawler_type": "github_api",
        "crawler_config": {"mode": "releases", "repos": ["THUDM/ChatGLM-6B", "THUDM/GLM-4"]},
        "poll_interval_seconds": 7200,
    },

    # === 国产基建 (GitHub) ===
    {
        "id": "C-INFRA-DIFY",
        "name": "Dify (CN)",
        "region": "china",
        "tier": "t1",
        "crawler_type": "github_api",
        "crawler_config": {"mode": "releases", "repos": ["langgenius/dify"]},
        "poll_interval_seconds": 7200,
    },
    {
        "id": "C-INFRA-MODELSCOPE",
        "name": "魔搭 ModelScope",
        "region": "china",
        "tier": "t1",
        "crawler_type": "github_api",
        "crawler_config": {"mode": "releases", "repos": ["modelscope/modelscope"]},
        "poll_interval_seconds": 7200,
    },

    # === 中文播客 ===
    {
        "id": "C-POD-SV101",
        "name": "硅谷101",
        "region": "china",
        "tier": "t2",
        "crawler_type": "podcast_rss",
        "crawler_config": {"feed_url": "https://feeds.fireside.fm/sv101/rss"},
        "poll_interval_seconds": 14400,
    },
    {
        "id": "C-POD-ONBOARD",
        "name": "OnBoard",
        "region": "china",
        "tier": "t2",
        "crawler_type": "podcast_rss",
        "crawler_config": {"feed_url": "https://feeds.fireside.fm/onboard/rss"},
        "poll_interval_seconds": 14400,
    },
    {
        "id": "C-POD-WANDIAN",
        "name": "晚点聊 LateTalk",
        "region": "china",
        "tier": "t2",
        "crawler_type": "podcast_rss",
        "crawler_config": {"feed_url": "https://feeds.fireside.fm/latetalk/rss"},
        "poll_interval_seconds": 14400,
    },

    # === Web Scrape 站点 ===
    {
        "id": "C-COMM-SSPAI",
        "name": "少数派 AI",
        "region": "china",
        "tier": "t3",
        "crawler_type": "web_scrape",
        "crawler_config": {
            "url": "https://sspai.com/tag/AI",
            "language": "zh",
            "selectors": {
                "article_pattern": "<div[^>]*class=\"[^\"]*article[^\"]*\"[^>]*>(.*?)</div>\\s*</div>",
                "title_pattern": "<h[23][^>]*>(.*?)</h[23]>",
                "link_pattern": "<a[^>]+href=[\"'](/post/\\d+)[\"']",
            }
        },
        "poll_interval_seconds": 7200,
    },
    {
        "id": "C-COMM-JUEJIN",
        "name": "掘金 AI",
        "region": "china",
        "tier": "t3",
        "crawler_type": "web_scrape",
        "crawler_config": {
            "url": "https://juejin.cn/tag/AI",
            "language": "zh",
        },
        "poll_interval_seconds": 7200,
    },

    # === 资本/智库 (RSSHub) ===
    {
        "id": "C-VC-BAAI",
        "name": "智源 BAAI",
        "region": "china",
        "tier": "t2",
        "crawler_type": "web_scrape",
        "crawler_config": {
            "url": "https://hub.baai.ac.cn/",
            "language": "zh",
        },
        "poll_interval_seconds": 7200,
    },
]


def run():
    engine = create_engine(settings.database_url_sync)
    with Session(engine) as session:
        for seed in SEEDS:
            existing = session.get(DataSource, seed["id"])
            if existing:
                print(f"  skip (exists): {seed['id']}")
                continue
            source = DataSource(**seed)
            session.add(source)
            print(f"  added: {seed['id']} - {seed['name']}")
        session.commit()
    engine.dispose()
    print("China seed complete.")


if __name__ == "__main__":
    run()
