"""Seed script: import data sources for Phase 1 + Phase 2."""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from mine.config import settings
from mine.models import DataSource

SEEDS = [
    # === Phase 1: RSS ===
    {
        "id": "G-MEDIA-TC",
        "name": "TechCrunch AI",
        "region": "global",
        "tier": "t1",
        "crawler_type": "rss",
        "crawler_config": {"feed_url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
        "poll_interval_seconds": 1800,
    },
    {
        "id": "G-MEDIA-VERGE",
        "name": "The Verge AI",
        "region": "global",
        "tier": "t2",
        "crawler_type": "rss",
        "crawler_config": {"feed_url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
        "poll_interval_seconds": 1800,
    },
    {
        "id": "G-MEDIA-AB",
        "name": "Ars Technica AI",
        "region": "global",
        "tier": "t2",
        "crawler_type": "rss",
        "crawler_config": {"feed_url": "https://feeds.arstechnica.com/arstechnica/technology-lab"},
        "poll_interval_seconds": 3600,
    },
    {
        "id": "G-NL-TLDR",
        "name": "TLDR AI",
        "region": "global",
        "tier": "t1",
        "crawler_type": "rss",
        "crawler_config": {"feed_url": "https://tldr.tech/ai/rss"},
        "poll_interval_seconds": 3600,
    },
    {
        "id": "G-MEDIA-VB",
        "name": "VentureBeat AI",
        "region": "global",
        "tier": "t2",
        "crawler_type": "rss",
        "crawler_config": {"feed_url": "https://venturebeat.com/category/ai/feed/"},
        "poll_interval_seconds": 1800,
    },
    # === Phase 2: HN ===
    {
        "id": "G-COMM-HN",
        "name": "Hacker News",
        "region": "global",
        "tier": "t1",
        "crawler_type": "hn_api",
        "crawler_config": {"story_type": "top", "max_items": 30},
        "poll_interval_seconds": 1800,
    },
    # === Phase 2: GitHub ===
    {
        "id": "G-LLM-OPENAI",
        "name": "OpenAI Releases",
        "region": "global",
        "tier": "t1",
        "crawler_type": "github_api",
        "crawler_config": {"mode": "releases", "repos": ["openai/openai-python", "openai/whisper", "openai/tiktoken"]},
        "poll_interval_seconds": 3600,
    },
    {
        "id": "G-LLM-ANTHROPIC",
        "name": "Anthropic Releases",
        "region": "global",
        "tier": "t1",
        "crawler_type": "github_api",
        "crawler_config": {"mode": "releases", "repos": ["anthropics/anthropic-sdk-python", "anthropics/courses"]},
        "poll_interval_seconds": 3600,
    },
    {
        "id": "G-INFRA-LANGCHAIN",
        "name": "LangChain Releases",
        "region": "global",
        "tier": "t1",
        "crawler_type": "github_api",
        "crawler_config": {"mode": "releases", "repos": ["langchain-ai/langchain", "langchain-ai/langgraph"]},
        "poll_interval_seconds": 3600,
    },
    {
        "id": "G-INFRA-LLAMAINDEX",
        "name": "LlamaIndex Releases",
        "region": "global",
        "tier": "t1",
        "crawler_type": "github_api",
        "crawler_config": {"mode": "releases", "repos": ["run-llama/llama_index"]},
        "poll_interval_seconds": 3600,
    },
    {
        "id": "G-LLM-META",
        "name": "Meta AI Releases",
        "region": "global",
        "tier": "t1",
        "crawler_type": "github_api",
        "crawler_config": {"mode": "releases", "repos": ["meta-llama/llama", "facebookresearch/fairseq"]},
        "poll_interval_seconds": 7200,
    },
    {
        "id": "G-INFRA-VLLM",
        "name": "vLLM Releases",
        "region": "global",
        "tier": "t2",
        "crawler_type": "github_api",
        "crawler_config": {"mode": "releases", "repos": ["vllm-project/vllm"]},
        "poll_interval_seconds": 7200,
    },
    {
        "id": "G-INFRA-DIFY",
        "name": "Dify Releases",
        "region": "global",
        "tier": "t2",
        "crawler_type": "github_api",
        "crawler_config": {"mode": "releases", "repos": ["langgenius/dify"]},
        "poll_interval_seconds": 7200,
    },
    {
        "id": "G-COMM-GHTREND",
        "name": "GitHub AI Trending",
        "region": "global",
        "tier": "t2",
        "crawler_type": "github_api",
        "crawler_config": {"mode": "trending", "query": "topic:ai topic:llm stars:>50 pushed:>2026-03-01"},
        "poll_interval_seconds": 7200,
    },
    # === Phase 2: HuggingFace ===
    {
        "id": "G-ACAD-HFPAPER",
        "name": "HuggingFace Daily Papers",
        "region": "global",
        "tier": "t1",
        "crawler_type": "hf_api",
        "crawler_config": {"mode": "papers"},
        "poll_interval_seconds": 3600,
    },
    {
        "id": "G-ACAD-HFMODEL",
        "name": "HuggingFace Trending Models",
        "region": "global",
        "tier": "t2",
        "crawler_type": "hf_api",
        "crawler_config": {"mode": "models"},
        "poll_interval_seconds": 7200,
    },
    # === Phase 2: YouTube (via RSSHub channel feeds / Data API v3 search) ===
    {
        "id": "G-VIDEO-AIEXPLAINED",
        "name": "AI Explained (YouTube)",
        "region": "global",
        "tier": "t1",
        "crawler_type": "youtube_api",
        "crawler_config": {
            "mode": "channel",
            "channels": [{"channel_id": "UCNJ1Ymd5yFuUPtn21xtRbbw", "name": "AI Explained"}],
            "max_items": 15,
        },
        "poll_interval_seconds": 3600,
    },
    {
        "id": "G-VIDEO-MATTWOLFE",
        "name": "Matt Wolfe (YouTube)",
        "region": "global",
        "tier": "t2",
        "crawler_type": "youtube_api",
        "crawler_config": {
            "mode": "channel",
            "channels": [{"channel_id": "UChpleBmo18P08aKCIgti38g", "name": "Matt Wolfe"}],
            "max_items": 15,
        },
        "poll_interval_seconds": 3600,
    },
    {
        "id": "G-VIDEO-GREG",
        "name": "Greg Isenberg (YouTube)",
        "region": "global",
        "tier": "t2",
        "crawler_type": "youtube_api",
        "crawler_config": {
            "mode": "channel",
            "channels": [{"channel_id": "UCPjNBjflYl0-HQtUvOx0Ibw", "name": "Greg Isenberg"}],
            "max_items": 15,
        },
        "poll_interval_seconds": 3600,
    },
    {
        "id": "G-VIDEO-YTSEARCH",
        "name": "YouTube AI 24h Hot",
        "region": "global",
        "tier": "t2",
        "crawler_type": "youtube_api",
        "crawler_config": {
            "mode": "search",
            "query": "AI",
            "region_code": "US",
            "max_results": 30,
            "published_after_hours": 24,
        },
        "poll_interval_seconds": 7200,
    },
    # === Phase 2: Twitter/X (twitterapi.io, same provider as n8n) ===
    {
        "id": "G-X-OPENAI",
        "name": "OpenAI (X)",
        "region": "global",
        "tier": "t1",
        "crawler_type": "twitter_api_io",
        "crawler_config": {"mode": "last_tweets", "handles": ["OpenAI"], "max_tweets": 10},
        "poll_interval_seconds": 1800,
    },
    {
        "id": "G-X-GOOGLEDM",
        "name": "Google DeepMind (X)",
        "region": "global",
        "tier": "t1",
        "crawler_type": "twitter_api_io",
        "crawler_config": {"mode": "last_tweets", "handles": ["GoogleDeepMind"], "max_tweets": 10},
        "poll_interval_seconds": 1800,
    },
    {
        "id": "G-X-GOOGLEAI",
        "name": "Google AI Studio (X)",
        "region": "global",
        "tier": "t2",
        "crawler_type": "twitter_api_io",
        "crawler_config": {"mode": "last_tweets", "handles": ["GoogleAIStudio"], "max_tweets": 10},
        "poll_interval_seconds": 1800,
    },
    {
        "id": "G-X-TWSEARCH",
        "name": "X AI Trending Search",
        "region": "global",
        "tier": "t2",
        "crawler_type": "twitter_api_io",
        "crawler_config": {"mode": "advanced_search", "query": "AI", "query_type": "Top", "max_tweets": 20},
        "poll_interval_seconds": 3600,
    },
    # === Phase 2: Podcast ===
    {
        "id": "G-POD-LATENT",
        "name": "Latent Space Podcast",
        "region": "global",
        "tier": "t2",
        "crawler_type": "podcast_rss",
        "crawler_config": {"feed_url": "https://feeds.buzzsprout.com/2004266.rss"},
        "poll_interval_seconds": 14400,
    },
    {
        "id": "G-POD-GRADIENT",
        "name": "Gradient Dissent (W&B)",
        "region": "global",
        "tier": "t2",
        "crawler_type": "podcast_rss",
        "crawler_config": {"feed_url": "https://feeds.soundcloud.com/users/soundcloud:users:721224740/sounds.rss"},
        "poll_interval_seconds": 14400,
    },
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
    # === More RSS: VC/Newsletter/Media ===
    {
        "id": "G-NL-A16Z",
        "name": "a16z Blog",
        "region": "global",
        "tier": "t1",
        "crawler_type": "rss",
        "crawler_config": {"feed_url": "https://a16z.com/feed/"},
        "poll_interval_seconds": 3600,
    },
    {
        "id": "G-MEDIA-WIRED",
        "name": "WIRED AI",
        "region": "global",
        "tier": "t2",
        "crawler_type": "rss",
        "crawler_config": {"feed_url": "https://www.wired.com/feed/tag/ai/latest/rss"},
        "poll_interval_seconds": 3600,
    },
    {
        "id": "G-MEDIA-MIT",
        "name": "MIT Tech Review AI",
        "region": "global",
        "tier": "t1",
        "crawler_type": "rss",
        "crawler_config": {"feed_url": "https://www.technologyreview.com/feed/"},
        "poll_interval_seconds": 3600,
    },
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
        "id": "C-MEDIA-36KR",
        "name": "36氪AI",
        "region": "china",
        "tier": "t1",
        "crawler_type": "rss",
        "crawler_config": {"feed_url": "https://36kr.com/feed"},
        "poll_interval_seconds": 1800,
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
    print("Seed complete.")


if __name__ == "__main__":
    run()
