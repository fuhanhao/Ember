"""Seed script: import X/Twitter KOL sources via RSSHub."""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from mine.config import settings
from mine.models import DataSource

RSSHUB_BASE = "http://rsshub:1200"
ACCESS_KEY = "forge_mine_2026"

# PRD 中的 44 个 KOL，按 Tier 分组
X_KOLS = [
    # T1 - Core AI Leaders
    ("karpathy", "Andrej Karpathy", "t1"),
    ("sama", "Sam Altman", "t1"),
    ("ylecun", "Yann LeCun", "t1"),
    ("demishassabis", "Demis Hassabis", "t1"),
    ("aidangomez", "Aidan Gomez (Cohere)", "t1"),
    ("DrJimFan", "Jim Fan (NVIDIA)", "t1"),

    # T1 - AI Research/Engineering
    ("_akhaliq", "AK (Daily Papers)", "t1"),
    ("swyx", "Swyx (Latent Space)", "t1"),
    ("GregKamradt", "Greg Kamradt", "t1"),
    ("jerryjliu0", "Jerry Liu (LlamaIndex)", "t1"),
    ("hwchase17", "Harrison Chase (LangChain)", "t1"),

    # T2 - AI Builders/Influencers
    ("levelsio", "Pieter Levels", "t2"),
    ("EMostaque", "Emad Mostaque", "t2"),
    ("arthurmensch", "Arthur Mensch (Mistral)", "t2"),
    ("ClaudAI", "Anthropic Claude", "t2"),
    ("OpenAI", "OpenAI", "t2"),
    ("GoogleDeepMind", "Google DeepMind", "t2"),
    ("MetaAI", "Meta AI", "t2"),
    ("xai", "xAI", "t2"),
    ("MistralAI", "Mistral AI", "t2"),
    ("StabilityAI", "Stability AI", "t2"),
    ("huggingface", "Hugging Face", "t2"),
    ("LangChainAI", "LangChain", "t2"),

    # T2 - Tech/VC
    ("elonmusk", "Elon Musk", "t2"),
    ("satyanadella", "Satya Nadella", "t2"),
    ("sundarpichai", "Sundar Pichai", "t2"),
    ("a16z", "a16z", "t2"),
    ("ycombinator", "Y Combinator", "t2"),

    # T3 - AI Community
    ("AlphaSignalAI", "AlphaSignal", "t3"),
    ("TheRundownAI", "The Rundown AI", "t3"),
    ("ai_for_success", "AI for Success", "t3"),
    ("LinusEkenstam", "Linus Ekenstam", "t3"),
    ("mckaywrigley", "McKay Wrigley", "t3"),
    ("realGeorgeHotz", "George Hotz", "t3"),
]


def run():
    engine = create_engine(settings.database_url_sync)
    with Session(engine) as session:
        for handle, name, tier in X_KOLS:
            source_id = f"G-X-{handle.upper()[:20]}"
            existing = session.get(DataSource, source_id)
            if existing:
                print(f"  skip (exists): {source_id}")
                continue

            source = DataSource(
                id=source_id,
                name=f"X: {name}",
                region="global",
                tier=tier,
                crawler_type="rss",
                crawler_config={
                    "feed_url": f"{RSSHUB_BASE}/twitter/user/{handle}?key={ACCESS_KEY}"
                },
                poll_interval_seconds=3600 if tier == "t1" else 7200,
            )
            session.add(source)
            print(f"  added: {source_id} - X: {name}")

        session.commit()
    engine.dispose()
    print(f"X KOL seed complete. {len(X_KOLS)} KOLs configured.")


if __name__ == "__main__":
    run()
