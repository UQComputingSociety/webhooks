from flask import Flask, request
import os
import subprocess as sp
import xmlrpc.client

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
    out = sp.check_output(["git", "pull"], timeout=120).decode('utf-8')
    out += "\n"
    os.chdir(previous_cwd)
    return out

def wrap(service):
    def fn():
        return template.format(
                git_pull_in_dir(service),
                supervisor_restart(service),
            )
    fn.__name__ = service + "_update"
    return fn 

for service in services:
    app.route('/'+service)(wrap(service))

