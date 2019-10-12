from setuptools import setup

setup(
    name='subreddit_archiver',
    version='0.1',
    packages=[''],
    url='',
    license='MIT',
    author='LightUmbra',
    author_email='',
    description='Archives a subreddit using web.archive.org.',
    install_requires=[
        "requests",
        "praw",
        "prawcore"
    ]
)
