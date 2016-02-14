from flask import Flask, request

app = Flask(__name__)

services = [
    "cesi",
    "slackinv",
    "hubot",
    "website",
]


__all__ = [
    "app",
]


def git_pull_service_restart(service):
    """
    A service name should match with both its name in supervisor and its /srv/*
    path.
    """

for service in services:
    def fn():
        pass
    

