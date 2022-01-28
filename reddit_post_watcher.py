#!/usr/bin/python3
import logging
import praw
import config
import time
import hashlib
from email.mime.text import MIMEText
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import base64


format = "%(asctime)s %(levelname)s %(message)s"
logging.basicConfig(format=format, level=logging.INFO)


USER_IGNORE = config.USER_IGNORE
STREAM_RETRY_DELAY = config.STREAM_RETRY_DELAY
SUBREDDITS = config.SUBREDDITS
ITEMS = config.ITEMS
SCOPES = ['https://www.googleapis.com/auth/gmail.send']


def get_creds():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('gmail', 'v1', credentials=creds, cache_discovery=False)

    return service


def create_message(to, subject, message_text):
    """Create a message for an email.

    Args:
    sender: Email address of the sender.
    to: Email address of the receiver.
    subject: The subject of the email message.
    message_text: The text of the email message.

    Returns:
    An object containing a base64url encoded email object.
    """
    message = MIMEText(message_text)

    message_id = hashlib.md5(subject.encode())
    message_id = message_id.hexdigest()
    message_id = '<{}@urlmon>'.format(message_id)

    # handle email threading
    message["In-Reply-To"] = message_id
    message["References"] = message_id

    message['to'] = to
    message['subject'] = f"{subject}"

    return {
        'raw': base64.urlsafe_b64encode(message.as_string().encode()).decode()
    }


def notify(data, item):
    emails = item.get("email_to", [])
    description = item.get("description", "Unknown")
    subject = f"POST_WATCHER: Found item: {description}"
    content = f'https://reddit.com{data["link"]}\n\n{data["comment"]}'
    for email in emails:
        try:
            message = create_message(
                        email,
                        subject,
                        content
            )
            service = get_creds()
            user_id = "me"      # special value, meaning authenticated user
            message = (
                service.users().messages().send(
                    userId=user_id, body=message
                ).execute()
            )
            logging.info("*** Sent notifcation:"
                         f"message ID {message['id']}, "
                         f"to {email}")
            return message
        except Exception as e:
            logging.exception(f"Exception in send_notification: {e}")


def search_text(comment, item):
    include_words = item.get("include_words", [])
    exclude_words = item.get("exclude_words", [])

    # return false if any include words are not in comment
    logging.debug(f"comment: {comment.lower()}")
    logging.debug(f"include_words: {str(include_words).lower()}")
    for word in include_words:
        if word.lower() not in comment.lower():
            return False

    # return false if any exclude words are found in comment
    logging.debug(f"exclude_words: {str(exclude_words).lower()}")
    for word in exclude_words:
        if word.lower() in comment.lower():
            return False

    return True


def process_items(data):
    for item in ITEMS:
        comment = data['comment']
        title = data['title']

        # check title for keywords, otherwise check comment
        if search_text(title, item):
            notify(data, item)
        elif search_text(comment, item):
            notify(data, item)


def process_post(post):
    try:
        title = post.title
        link = f"https://reddit.com{post.permalink}"
        logging.info(f'{title} | {link}')
        author = post.author
        if author in USER_IGNORE:
            return
        data = {
            'id': post.id,
            'post': True,
            'author': author.name,
            'comment': post.selftext,
            'title': title,
            'created_at': post.created_utc,
            'link': post.permalink,
            'stickied': post.stickied,
            'source': 'reddit:' + str(post.subreddit),
            'subreddit_id': post.subreddit_id,
            'submission': str(post.id),
        }
        process_items(data)

    except Exception as e:
        logging.exception(f'Exception processing post: {e}')


def start_reddit_stream():
    try:
        reddit = praw.Reddit(client_id=config.REDDIT_CLIENT_ID,
                             client_secret=config.REDDIT_CLIENT_SECRET,
                             username=config.REDDIT_USERNAME,
                             password=config.REDDIT_PASSWORD,
                             redirect_uri=config.REDDIT_REDIRECT_URI,
                             user_agent=config.REDDIT_USER_AGENT)

        # stream reddit comments
        subs_str = '+'.join(SUBREDDITS)
        logging.info("starting PRAW streamer")
        for post in reddit.subreddit(subs_str).stream.submissions():
            process_post(post)
    except Exception as e:
        logging.exception("Exception starting_reddit_stream: e" % (e))
        raise


def main():
    while True:
        try:
            start_reddit_stream()
        except Exception:
            # sleep, and try to restart stream
            time.sleep(STREAM_RETRY_DELAY)


if __name__ == "__main__":
    main()
