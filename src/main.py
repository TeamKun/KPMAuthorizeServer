import os
import random
import socket
import string
import threading
import time
import urllib.parse
import urllib.parse as parse
from enum import Enum
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingTCPServer
from urllib import request
import schedule
import json
from src.database import DataBase


def rand(n):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=n))


def randDig(n):
    return random.randint(10 ** (n - 1), (10 ** n) - 1)


class ERR_CAUSE(Enum):
    MISSING_FIELD = 400
    SESSION_ALREADY_EXIST = 409
    CODE_EXPIRED = 404

    def getCode(self):
        return self.value


PORT = int(os.getenv("PORT", "810"))
GH_PRIV = os.getenv("GH_PRIV")
GH_CID = os.getenv("GH_CID")
TOKEN_LENGTH = int(os.getenv("TOKEN_LENGTH", "6"))

sql = DataBase(
    os.getenv("DB_ADDR"),
    os.getenv("DB_PORT"),
    os.getenv("DB_USER"),
    os.getenv("DB_PASS"),
    os.getenv("DB_DATABASE")
)

sql.execute("CREATE TABLE IF NOT EXISTS SESSION("
            "SESSID TEXT,"
            "CLTID TEXT,"
            "CREATED_AT INTEGER"
            ")")

sql.execute("CREATE TABLE IF NOT EXISTS CODE("
            "CODE TEXT,"
            "CLTID TEXT,"
            "TOKEN TEXT,"
            "SESSID TEXT,"
            "CREATED_AT INTEGER"
            ")")


def grand(sv, path, data):
    p = "public/html" + path
    if os.path.exists(p):
        with open(p, "rb") as obj:
            sv.send_response(200)
            sv.end_headers()
            sv.wfile.write(obj.read())
        return True
    return False


def text(path, replaces):
    with open("public/html" + path, "r", encoding="utf-8") as r:
        txt = r.read()
    for replace in replaces:
        txt = txt.replace("%%" + replace[0] + "%%", replace[1])
    return txt


def error(sv, code, name, detail):
    write(sv, code, text("/error.html", [
        ["ERROR", name],
        ["DETAIL", detail]
    ]).encode())


def errCause(sv, cause):
    write(sv, cause.getCode(), ('{"success":false,"cause":"' + cause.name + '"}').encode())


def write(sv, code, txt):
    sv.send_response(code)
    sv.end_headers()
    sv.wfile.write(txt)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            path = parse.urlparse(self.path)
            params = parse.parse_qs(path.query)

            if path.path == "/login/gentoken":
                if "client_id" not in params:
                    errCause(self, ERR_CAUSE.MISSING_FIELD)
                    return
                if sql.count("SESSION", [("CLTID", params.get("client_id")[0])]) > 0:
                    errCause(self, ERR_CAUSE.SESSION_ALREADY_EXIST)
                    return

                r = rand(32)
                sql.execute("INSERT INTO SESSION VALUES(?, ?, ?)", (r, params.get("client_id")[0], time.time()))
                write(self, 200, ('{"success": true, "code":"' + r + '"}').encode())
                return

            if path.path == "/login/oauth":
                if "session_id" not in params:
                    error(self, 400, "エラー", "セッションが見つかりませんでした。もう一度<code>/kpm register</code>を使用してください。")
                    return

                sessionId = params.get("session_id")[0]

                if sql.count("SESSION", [("SESSID", sessionId)]) == 0:
                    error(self, 400, "エラー", "セッションが見つかりませんでした。もう一度<code>/kpm register</code>を使用してください。")
                    return

                self.send_response(200)
                self.send_header("Set-Cookie", "SESSID=" + sessionId + "; Max-Age=300; HttpOnly")
                self.end_headers()

                self.wfile.write(text("/login.html", [
                    ["URL",
                     "https://github.com/login/oauth/authorize?scope=repo%3Astatus,public_repo&client_id=" + GH_CID]
                ]).encode())
                return

            if path.path == "/login/oauth/callback":
                cookies = SimpleCookie(self.headers.get('Cookie'))
                if "SESSID" not in cookies or "code" not in params:
                    error(self, 400, "エラー", "セッションが見つかりませんでした。もう一度<code>/kpm register</code>を使用してください。")
                    return

                sessionId = cookies["SESSID"].value
                data = sql.getOne("SESSION", [("SESSID", sessionId)])

                if data is None:
                    error(self, 400, "エラー", "セッションが見つかりませんでした。もう一度<code>/kpm register</code>を使用してください。")
                    return

                clientId = data[1]

                data = {
                    "client_id": GH_CID,
                    "client_secret": GH_PRIV,
                    "code": params.get("code")[0],
                }

                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "Mozilla/8.10 (Peyantosh NT; OS Peyandows X, like Linux 114.514.191; Peyantu; i386) "
                                  "PeyangleWebKit/810.931(H-PONF, like Pecko) Peyang/11.4.514.810; "
                                  "KungleBot/1919.810.931; Kungle,kChrome/810.931;",
                    "Accept": "application/json"
                }

                req = request.Request("https://github.com/login/oauth/access_token",
                                      urllib.parse.urlencode(data).encode(),
                                      headers)

                with urllib.request.urlopen(req) as res:
                    body = json.loads(res.read())
                    if "error" in body:
                        error(self, 400, "エラー", "エラーが発生しました。。もう一度<code>/kpm register</code>を使用してください。"
                                                "<br><code>" + body["error_description"] + "</code>")
                        return

                    code = randDig(TOKEN_LENGTH)
                    sql.execute("INSERT INTO CODE VALUES (?, ?, ?, ?, ?)", (code,
                                                                         clientId,
                                                                         body["access_token"],
                                                                         sessionId,
                                                                         time.time()))

                    write(self, 200, text("/success.html", [
                        ["CODE", str(code)],
                        [
                            "CODE_DISPLAY",
                            "".join(["<code>" + ta + "</code>" for ta in str(code)])
                        ]
                    ]).encode())
                    return

            if path.path == "/login/claim":
                if "client_id" not in params or "code" not in params or "session_id" not in params:
                    errCause(self, ERR_CAUSE.MISSING_FIELD)
                    return

                clientId = params.get("client_id")[0]
                code = params.get("code")[0]
                sessionId = params.get("session_id")[0]

                data = sql.getOne("CODE", [
                    ("SESSID", sessionId),
                    ("CODE", code),
                    ("CLTID", clientId)
                ])

                if data is None:
                    errCause(self, ERR_CAUSE.CODE_EXPIRED)
                    return

                write(self, 200, ('{"success": true, "token": "' + data[2] + '"}').encode())
                sql.execute("DELETE FROM CODE WHERE SESSID=?", [sessionId])
                return

            if not grand(self, path.path, params):
                error(self, 404, "Not Found", "ページが見つかりませんでした。")
        except Exception as e:
            print(e)
            error(self, 503, "Internal Server Error", "サーバエラーが発生しました。もう一度お待ち下さい。")


class Server(ThreadingTCPServer, object):
    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)


def watchdog():
    sql.execute("DELETE FROM SESSION WHERE CREATED_AT < " + str(time.time() - 300))
    sql.execute("DELETE FROM CODE WHERE CREATED_AT < " + str(time.time() - 600))


def thread():
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    server = Server(("", PORT), Handler)
    schedule.every(5).seconds.do(watchdog)
    t = threading.Thread(target=thread)
    t.start()
    server.serve_forever()
