from flask import Flask
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
]

with open("template.html") as f:
    template = f.read()

__all__ = [
    "app",
]


def slack_post(service, git_pull_result, supervisor_result):
    def format():
        if git_pull_result[-1] == 0:
            gitmsg = "Git pull successful"
            if "Already up-to-date" in git_pull_result[0]:
                gitmsg += ". No new commits"
        else:
            gitmsg = "Git pull had non-zero exit status"
        if len(supervisor_result) == 3:
            supmsg = "Service status: " + supervisor_result[-1]["statename"]
        elif len(supervisor_result) == 2:
            supmsg = "Error starting process"
        else:
            supmsg = "Error stopping process"

        return "Hook for {} triggered. {}. {}.".format(service, gitmsg, supmsg)
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
                username=os.environ.get("SUPERVISOR_USER", "user"),
                password=os.environ.get("SUPERVISOR_PASS", "123"),
            )
        )
    # if error in stop, doesn't try and start - short circuited booleans
    res = server.supervisor.stopProcess(service),
    if res[-1]:
        res += server.supervisor.startProcess(service),
    if res[-1]:
        res += server.supervisor.getProcessInfo(service),
    return res


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
        git = git_pull_in_dir(service)
        sup = supervisor_restart(service)
        msg = template.format(
                git[0],
                sup[-1],
            )
        slack_post(service, git, sup)
        return msg
    fn.__name__ = service + "_update"
    return fn

for service in services:
    app.route('/'+service, methods=["GET", "POST"])(wrap(service))


@app.route("/hooks", methods=["GET", "POST"])
def hookbot_hook():
    git = git_pull_in_dir("hooks")

    msg = "Someone triggered my reset switch! "
    msg += "There was a git pull with status code {}.".format(git[1])
    msg += " Can someone please restart me now? https://cesi.uqcs.org.au. Ask @trm for a signin."

    slack_hooks = os.environ.get("SLACK_HOOK_URL")
    if slack_hooks:
        requests.post(slack_hooks, json.dumps({
                "username": "hookbot",
                "icon_emoji": ":fc:",
                "text": msg
            }))
    supervisor_restart("hooks")
