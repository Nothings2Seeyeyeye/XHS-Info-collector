"""Local terminal-only password recovery; never exposed as an HTTP endpoint."""
from getpass import getpass
from argon2 import PasswordHasher
from sqlalchemy import delete
from .db import LoginSession, Store, User


def main():
    password = getpass("输入新密码（至少 8 个字符）: ")
    if len(password) < 8 or len(password) > 256:
        raise SystemExit("密码长度需为 8–256 个字符")
    if getpass("再次输入新密码: ") != password:
        raise SystemExit("两次输入不一致")
    store = Store()
    with store.session() as db:
        user = db.get(User, 1)
        if not user:
            raise SystemExit("尚未创建管理员，请先打开工作台初始化")
        user.password_hash = PasswordHasher().hash(password)
        db.execute(delete(LoginSession))
    print("密码已更新，旧登录会话已退出。请重新打开网页登录。")
    store.close()


if __name__ == "__main__":
    main()
