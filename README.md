# reddit_post_watcher

This app uses pythons PRAW module to stream all posts to a subreddit, and notify a user via email if a post title or comment contains and/or excludes certain strings.

Requirements:
- Reddit API account
- Google API account

Define your Reddit API creds in config.py, and your Google API creds in the credentials.json file.


Install:

```
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Running:

```
python reddit_post_watcher.py
```