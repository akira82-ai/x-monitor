#!/usr/bin/env python3
"""Demo mode for x-monitor - generates fake tweets for UI testing."""

import sys
import os

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from datetime import datetime, timezone, timedelta
from random import choice, randint

from src.config import Config
from src.types import AppState, Tweet
from src.ui import run_ui


# Sample tweet content
SAMPLE_TWEETS = [
    "Just shipped a new feature! 🚀",
    "Working on some exciting AI research",
    "Coffee + Code = Productivity",
    "Debugging is like being a detective in a crime movie where you're also the murderer",
    "The best code is no code at all",
    "Always be learning, always be building",
    "Excited to announce our new project!",
    "Sometimes the best debugging tool is a good night's sleep",
    "Code review time! Let's make this better together",
    "Refactoring old code feels so good",
]

SAMPLE_USERS = [
    ("karpathy", "Andrej Karpathy"),
    ("suhail", "Suhail"),
    ("levelsio", "Pieter Levels"),
    ("naval", "Naval"),
    ("paulg", "Paul Graham"),
]


def generate_fake_tweet(user_handle: str, user_name: str, offset_minutes: int = 0) -> Tweet:
    """Generate a fake tweet for testing."""
    timestamp = datetime.now(timezone.utc) - timedelta(minutes=offset_minutes)
    tweet_id = f"fake_{user_handle}_{timestamp.timestamp()}"

    return Tweet(
        id=tweet_id,
        author=user_handle,
        author_name=user_name,
        content=choice(SAMPLE_TWEETS),
        timestamp=timestamp,
        url=f"https://twitter.com/{user_handle}/status/{tweet_id}",
        is_retweet=False,
    )


async def demo_mode():
    """Run x-monitor in demo mode with fake data."""
    print("=" * 60)
    print("x-monitor DEMO MODE")
    print("=" * 60)
    print()
    print("Running with fake data for UI testing")
    print("Press Q to quit, Space to pause, R to refresh")
    print()

    # Load config (or use defaults)
    try:
        config = Config.load("config.toml")
    except Exception:
        config = Config()

    # Create state with fake tweets
    state = AppState()

    # Generate initial tweets
    for i in range(20):
        user_handle, user_name = choice(SAMPLE_USERS)
        tweet = generate_fake_tweet(user_handle, user_name, offset_minutes=i * 5)
        state.add_tweet(tweet)

    print(f"Generated {len(state.tweets)} fake tweets")
    print()

    # Callback to add new fake tweets
    async def add_fake_tweets():
        """Add a few random fake tweets."""
        new_count = randint(1, 3)
        for _ in range(new_count):
            user_handle, user_name = choice(SAMPLE_USERS)
            tweet = generate_fake_tweet(user_handle, user_name)
            state.add_tweet(tweet)

    # Run UI
    await run_ui(config, state, add_fake_tweets)


def main():
    """Entry point."""
    try:
        asyncio.run(demo_mode())
    except KeyboardInterrupt:
        print("\nDemo interrupted")


if __name__ == "__main__":
    main()
