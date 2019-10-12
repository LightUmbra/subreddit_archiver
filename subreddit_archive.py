import requests
import praw
import logging
import time
import argparse

from os import path
from typing import List, TextIO
from praw.exceptions import APIException, ClientException
from prawcore.exceptions import RequestException, ResponseException, OAuthException
from requests.exceptions import ConnectionError, ConnectTimeout


user_name: str = ""  # Username for praw to use. Should be same as on praw.ini.
RECOVERABLE_EXC: tuple = (
    APIException,
    ClientException,
    ResponseException,
    RequestException,
    OAuthException,
    ConnectionError,
)


class PostType:
    def __init__(self, post_id: str):
        self.post_id: str = post_id
        self.post_url: str = ""
        self.archive_url: str = ""
        self.link: str = ""
        self.title: str = ""
        self.self_text: str = ""
        self.author: str = ""
        self.flair: str = ""
        self.subreddit: str = ""
        self.archived_date_unfmt: str = ""
        self.archived_date_fmt: str = ""
        self.stickied: bool = False
        self.locked: bool = False
        self.edited: bool = False
        self.distinguished: bool = False
        self.is_self: bool = False
        self.locked: bool = False
        self.spoiler: bool = False
        self.cant_archive: bool = False
        self.post_score: int = -100000
        self.num_of_comments: int = -1
        self.percent_upvoted: float = 0
        self.time_created: float = 0


def build_post_urls(in_path: str) -> List[PostType]:
    """
    Builds list of PostType objects, containing just the post IDs, from list of IDs in txt file in reverse chronological
    order. File should be have one ID per line, which should be 6 characters a-z (lowercase) and 0-9.
    No separating character should be used.
    :param in_path: File path to file containing post IDs.
    :return: List of PostType objects containing only post IDs.
    """
    id_list: List[str]
    posts: List[PostType]
    id_file: TextIO

    with open(in_path, 'r') as id_file:
        id_list = id_file.read().splitlines()

    id_list.reverse()  # Puts post in chronological order.
    posts = [PostType(post_id) for post_id in id_list]
    log.info("URLs built.")
    return posts


def get_reddit_details(posts: List[PostType], reddit_inst: praw.Reddit) -> List[PostType]:
    """
    Gets details of each post (i.e. score, title, etc.) and puts them into their PostType objects.
    :param posts: List of PostType objects with post ID and partial
    :param reddit_inst: Current reddit instance from praw.
    :return:
    """
    post: PostType
    submission: praw.models.submission.Submission
    getting_sub: bool = True

    log.info("Collecting post data.")

    for post in posts:  # Iterate through posts
        while getting_sub:  # Loop to make sure the submission gets grabbed.
            try:
                submission = reddit_inst.submission(post.post_id)
                getting_sub = False

            except RECOVERABLE_EXC as err:
                log.debug(f"Couldn't get submission: {err}")
                time.sleep(5)

        try:
            # First get string items from post.
            post.post_url = f"https://old.reddit.com{submission.permalink}"
            post.title = submission.title
            post.author = submission.author if submission.author is not None else "Deleted"
            post.flair = submission.link_flair_text if submission.link_flair_text is not None else ""
            post.link = submission.url if not submission.is_self else ""
            post.self_text = submission.selftext if submission.is_self else ""
            post.subreddit = submission.subreddit.display_name

            # Then booleans
            post.stickied = submission.stickied
            post.locked = submission.locked
            post.edited = submission.edited
            post.distinguished = submission.distinguished
            post.is_self = submission.is_self
            post.locked = submission.locked
            post.spoiler = submission.spoiler

            # Lastly numerics
            post.post_score = submission.score
            post.num_of_comments = submission.num_comments
            post.percent_upvoted = submission.upvote_ratio
            post.time_created = submission.created_utc

        except NameError:
            log.debug("Submission could not be found and was not caught.")
    log.info("All post data collected.")
    return posts


def archive_posts(posts: List[PostType]) -> List[PostType]:
    """
    Archives to archive.org. The website gives a 403 Forbidden when the
    archive cannot be generated (because it follows robots.txt rules)
    :param posts: List of PostType objects, with all posts in ID file
    :return: List of PostType objects, with web.archive.org links included.
    """
    not_complete: bool
    max_tries: int
    sleep_time: int
    archive_date: float
    curr_time: time.struct_time

    log.info(f"Archiving {len(posts)} posts. This may take a while.")

    for post in posts:
        not_complete = True
        max_tries = 0
        sleep_time = 3

        while not_complete and max_tries <= 1000:
            try:
                resp = requests.get(post.post_url)
                if resp.status_code == 404:
                    post.cant_archive = True
                not_complete = False
            except (ConnectTimeout, ConnectionError):
                if max_tries == 1000:
                    logging.error("Can not connect to web.archive.org. Please check your connection and retry later.")
                    exit(0)
                else:
                    max_tries += 1
                time.sleep(sleep_time)
                sleep_time += 1

        # Gets archived time for link and reference
        curr_time = time.gmtime()
        post.archived_date_unfmt = time.strftime("%Y%m%d", curr_time)
        post.archived_date_fmt = time.strftime("%Y/%m/%d", curr_time)

        # Builds link to post archive
        post.archive_url = f"https://web.archive.org/web/{post.archived_date_unfmt}/{post.post_url}"

        time.sleep(5)

    log.info("All archive links collected.")
    return posts


def write_file_output(posts: List[PostType], out_path: str) -> None:
    """
    Writes post data to output file.
    :param posts: List of PostType objects to be written to file.
    :param out_path: Path for output file.
    :return: None
    """
    posts: PostType
    num_upvotes: int
    num_downvotes: int
    post_type: str
    stickied: str
    Locked: str
    spoiler: str

    log.info("Writing data to file.")

    with open(out_path, "w") as archive_file:
        for post in posts:
            num_upvotes = post.post_score * post.percent_upvoted
            num_downvotes = post.post_score - num_upvotes
            post_type = "Self Post" if post.is_self else "Link Post"

            archive_file.write(f"Title: {post.title}\n")
            archive_file.write(f"Posted by: {post.author}\n")
            archive_file.write(f"Sub Posted on: {post.subreddit}\n")
            archive_file.write(f"Date Posted: {post.archived_date_fmt}\n")
            archive_file.write(f"Original Link: {post.post_url}\n")
            archive_file.write(f"Score: {post.post_score}\t% Upvoted: {post.percent_upvoted}\t"
                               f"# of Upvotes: {num_upvotes}\t# of Downvotes: {num_downvotes}\n")
            archive_file.write(f"Flair: {post.flair}\n")
            archive_file.write(f"Post Type: {post_type}\n")
            archive_file.write(f"Stickied: {post.stickied}\tLocked: {post.locked}\tSpoiler: {post.spoiler}\n")
            archive_file.write(f"Date Archived: {post.archived_date_fmt}\n")
            archive_file.write(f"Archive Link: {post.archive_url}\n\n\n")


def main(in_path: str, out_path: str, bot_name) -> None:
    """
    :param in_path: Path to input file.
    :param out_path: Path to output file.
    :param bot_name: Name for bot to use. Should be same as on praw.ini.
    :return: None
    """
    post_lists: List[PostType]
    reddit: praw.Reddit
    user_agent: str = "Archiving /r/drama for future e-archaeologists."

    reddit = praw.Reddit(bot_name, user_agent=user_agent)
    post_lists = build_post_urls(in_path)
    post_lists = get_reddit_details(post_lists, reddit)
    post_lists = archive_posts(post_lists)
    write_file_output(post_lists, out_path)
    log.info("Archive completed.")


if __name__ == '__main__':
    debug: bool
    overwrite: bool
    path_relative: bool
    log_level: int
    input_path: str
    output_path: str

    parser = argparse.ArgumentParser(description='Archive a subreddit.')
    parser.add_argument("-d", "--debug", help='Run with debug messages.', action="store_true")
    parser.add_argument("-o", "--overwrite", help='Overwrite existing output file.', action="store_true")
    parser.add_argument("input", type=str, help="Path to file with IDs.")
    parser.add_argument("output", type=str, help="Path to output file.")
    args = parser.parse_args()
    debug = args.debug
    overwrite = args.overwrite
    input_path = path.abspath(args.input)
    output_path = path.abspath(args.output)

    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=log_level, format="[%(asctime)s] [%(levelname)s] %(message)s")
    log = logging.getLogger("drama_archive")

    if user_name == "":
        log.error("Please enter a username for the bot in subreddit_archive.py.")
        exit(0)

    if path.exists(output_path) and not overwrite:
        log.error('Output file already exists. Please choose a different name or use "-o" to overwrite it.')
        exit(0)
    elif path.exists(output_path) and not overwrite:
        log.info("Overwriting existing file.")
    else:
        log.info("Running...")

    main(input_path, output_path, user_name)
