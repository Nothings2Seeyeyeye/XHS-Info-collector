import fcntl
import signal
import time

from sqlalchemy import select
from .db import Job, JobItem, Store
from .tasks import Runner


def recover(store):
    with store.session() as db:
        for job in db.scalars(select(Job).where(Job.state == "running")):
            job.state, job.message = "queued", "已恢复上次任务进度，等待继续"
        for item in db.scalars(select(JobItem).where(JobItem.state == "running")):
            item.state = "pending"


def main():
    store = Store()
    stopped = False

    def stop(*_):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with open(store.root / "worker.lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("后台任务进程已经在运行")
        recover(store)
        while not stopped:
            store.put("worker_heartbeat", time.time())
            with store.session() as db:
                job = db.scalar(select(Job).where(Job.state == "queued").order_by(Job.created_at))
                if job:
                    job.state, job.updated_at = "running", time.time()
                    job_id = job.id
                else:
                    job_id = None
            if job_id:
                Runner(store, job_id, lambda: stopped).run()
            else:
                time.sleep(0.5)
        store.close()


if __name__ == "__main__":
    main()
