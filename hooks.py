from flask import Flask, request
import os
import subprocess as sp
import xmlrpc.client
import requests
import json

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


def slack_post(git_pull_result, sueprvisor_result):
    def format():
        return "A thing happend, I don't know what."
    slack_hooks = os.environ.get("SLACK_HOOK_URL")
    if slack_hooks:
        requests.post(slack_hooks, json.dumps({
                "username": "hookbot",
                "icon_emoji": ":fc:",
                "text": format()
            }))


def supervisor_restart(service):
    server = xmlrpc.client.ServerProxy(
        'http://{username}:{password}@localhost:9001/RPC2'.format(
                username=os.environ.get("SUPERVISOR_USER","user"),
                password=os.environ.get("SUPERVISOR_PASS","123"),
            )
        )
    # if error in stop, doesn't try and start - short circuited booleans
    return server.supervisor.stopProcess(service) and server.supervisor.startProcess(service) and server.supervisor.getProcessInfo(service)


def git_pull_in_dir(service):
    """
    A service name should match with both its name in supervisor and its /srv/*
    path.
    """
    previous_cwd = os.getcwd()
    os.chdir("/srv/" + service)
    try:
        out = sp.check_output(["git", "pull"], timeout=120).decode('utf-8')
        code = 0
    except sp.CalledProcessError as e:
        out = e.output.decode('utf-8')
        out += "\nErrored out with code " + str(e.returncode) + "."
        code = e.returncode
    out += "\n"
    os.chdir(previous_cwd)
    return out, code

def wrap(service):
    def fn():
        slack_post(1, 1)
        git = git_pull_in_dir(service)
        sup = supervisor_restart(service)
        msg = template.format(
                git[0],
                sup[-1],
            )
        return msg
    fn.__name__ = service + "_update"
    return fn

for service in services:
    app.route('/'+service, methods=["GET", "POST"])(wrap(service))

