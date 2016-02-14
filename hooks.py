from flask import Flask, request
import os
import subprocess as sp
import xmlrpclib

app = Flask(__name__)

services = [
    "cesi",
    "slackinv",
    "hubot",
    "website",
    "hooks",
]

with open("template.html") as f:
    template = f.read()

__all__ = [
    "app",
]


def supervisor_restart(service):
    server = xmlrpclib.Server(
        'http://{username}:{password}@localhost:9001/RPC2'.format(
                username=os.environ.get("SUPERVISOR_USER","user"),
                password=os.environ.get("SUPERVISOR_PASS","123"),
            )
        )

def git_pull_in_dir(service):
    """
    A service name should match with both its name in supervisor and its /srv/*
    path.
    """
    previous_cwd = os.getcwd()
    os.chdir(path)
    out = sp.check_output(["git", "pull"], timeout=120)
    out ++ "\n"
    os.chdir(previous_cwd)
    return out


for service in services:
    def fn():
        return template.format(
                git_pull_service_restart(service),
                supervisor_restart(service),
            )
    fn.__name__ = serivce + "_update"
    app.add_url_rule('/'+service, service, fn)

