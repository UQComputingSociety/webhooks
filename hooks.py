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
    "website",
    "codegolf",
    "payments",
    "slackwolf",
    "shirts"
]

with open("template.html") as f:
    template = f.read()

__all__ = [
    "main",
]


def slack_msg(message, channel="#projects", icon=":fc:", username="hookbot"):
    requests.post(os.environ.get("SLACK_HOOK_URL"), json.dumps({
            "username": username,
            "icon_emoji": icon,
            "text": message,
            "channel": channel,
        }))


def gitmsg_format(git_result):
    if git_result[1] == 0:
        gitmsg = "Git pull successful"
        if "Already up-to-date" in git_result[0]:
            gitmsg += ". No new commits"
        elif len(git_result) == 3:
            gitmsg += ". Last commit: " + git_result[2]
    else:
        gitmsg = "Git pull had non-zero exit status"
    return gitmsg


def supervisormsg_format(sup_result):
    if len(sup_result) == 3:
        supmsg = "Service status: " + sup_result[-1]["statename"]
    elif len(sup_result) == 2:
        supmsg = "Error starting process"
    else:
        supmsg = "Error stopping process"
    return supmsg


def slack_post(service, git_pull_result, supervisor_result):
    gitmsg = gitmsg_format(git_pull_result)
    supmsg = supervisormsg_format(supervisor_result)
    slack_msg(
        "Hook for {} triggered. {}. {}.".format(service, gitmsg, supmsg),
        channel="#codegolf" if service == "codegolf" else "#projects",
    )


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
    logmsg = "Error checking logs"
    if code == 0:
        try:
            logmsg = sp.check_output(["git", "log", "-n1", "--oneline"]).decode('utf-8').strip()
        except sp.CalledProcessError as e:
            logmsg = "Error checking logs"
    os.chdir(previous_cwd)
    return out, code, logmsg


def wrap(service, queue):
    def worker_fn():
        git = git_pull_in_dir(service)
        sup = supervisor_restart(service)
        msg = template.format(
                git[0],
                sup[-1],
            )
        slack_post(service, git, sup)
        return msg

    worker_fn.__name__ = service + "_worker"

    def resp():
        queue.put(worker_fn)
        return "Hook started"
    resp.__name__ = service + "_update"
    return resp


def add_hookbot(app, queue):
    def worker_fn():
        git = git_pull_in_dir("hooks")

        msg = "Someone triggered my reset switch! "
        msg += "There was a git pull with status code {}.".format(git[1])
        msg += " Can someone please restart me now? http://cesi.uqcs.org.au."
        msg += " (@trm)"

        slack_hooks = os.environ.get("SLACK_HOOK_URL")
        if slack_hooks:
            requests.post(slack_hooks, json.dumps({
                    "username": "hookbot",
                    "icon_emoji": ":fc:",
                    "text": msg,
                    "channel": "#projects",
                }))
        supervisor_restart("hooks")

    worker_fn.__name__ = "hooks_worker"

    @app.route("/hooks", methods=["GET", "POST"])
    def hooks_update():
        queue.put(worker_fn)
        return "Hook started"


def add_hubot(app, queue):
    good_build_types = [
        "no_tests",
        "fixed",
        "success",
    ]

    def worker_factory(payload):
        def worker_fn():
            buildmsg = "Hook for hubot triggered"
            status = payload['payload']['status']
            print(status)
            if status not in good_build_types:
                buildmsg += ". Hubot build failed with status " + status + "."
                return slack_msg(buildmsg)
            else:
                buildmsg += ". Passed with status " + status + ". "

            # clean git dir
            previous_cwd = os.getcwd()
            os.chdir("/srv/" + service)
            os.system('git clean -fd')
            os.chdir(previous_cwd)

            git = git_pull_in_dir("hubot")
            buildmsg += gitmsg_format(git) + "."
            build_num = payload['payload']['build_num']
            artifact_data = requests.get(
                "https://circleci.com/api/v1.1/project/github/" +
                "UQComputingSociety/uqcs-hubot/" +
                str(build_num) +
                "/artifacts"
            ).json()
            for item in artifact_data:
                file_url = item['url']
                file_path = os.path.join(
                    "/srv/hubot",
                    item['pretty_path'].lstrip("$CIRCLE_ARTIFACTS/"),
                )
                print(file_path)
                try:
                    os.makedirs(os.path.dirname(file_path))
                except FileExistsError:
                    pass
                with open(file_path, "wb+") as f:
                    f.write(requests.get(file_url).content)
            buildmsg += " " + str(len(artifact_data))
            buildmsg += " compiled files were loaded."
            return slack_msg(buildmsg)
        return worker_fn

    @app.route("/hubot-ci", methods=["GET", "POST"])
    def hubot_update():
        (worker_factory(json.loads(request.data.decode('utf-8'))))()
        return "Hook started"


def task_queue(queue):
    print("Starting task queue")
    for item in iter(queue.get, None):
        print(item.__name__)
        item()
    print("Task queue finished")


import threading
from queue import Queue
queue = Queue()
queuthread = threading.Thread(target=task_queue, args=(queue,))

for service in services:
    app.route('/'+service, methods=["GET", "POST"])(wrap(service, queue))
add_hookbot(app, queue)
add_hubot(app, queue)


def main(port, host):
    queuthread.start()

    app.run(port=port, host=host)

    queue.put(None)
    queuthread.join()
