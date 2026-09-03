import base64
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from spider_xhs.utils import network as requests
from loguru import logger


class OCRClient:
    def __init__(
        self,
        token: str,
        mode: str = "async",
        sync_url: str = "https://o6f4pfe0wf57ico6.aistudio-app.com/layout-parsing",
        async_job_url: str = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs",
        model: str = "PaddleOCR-VL-1.6",
        poll_interval: int = 5,
        timeout_seconds: int = 300,
        submit_retries: int = 5,
        submit_retry_delay: int = 30,
    ):
        if mode not in {"sync", "async"}:
            raise ValueError("mode 必须是 sync 或 async")
        if not token:
            raise ValueError("OCR token 不能为空")
        self.token = token
        self.mode = mode
        self.sync_url = sync_url
        self.async_job_url = async_job_url
        self.model = model
        self.poll_interval = poll_interval
        self.timeout_seconds = timeout_seconds
        self.submit_retries = max(0, submit_retries)
        self.submit_retry_delay = max(1, submit_retry_delay)
        self.optional_payload = {
            "useDocOrientationClassify": False,
            "useDocUnwarping": False,
            "useChartRecognition": False,
        }

    def parse_image_file(self, file_path: str) -> Tuple[bool, str, str]:
        if self.mode == "sync":
            return self._parse_image_sync(file_path)
        return self._parse_image_async(file_path)

    def _parse_image_sync(self, file_path: str) -> Tuple[bool, str, str]:
        with open(file_path, "rb") as file:
            file_bytes = file.read()
        file_data = base64.b64encode(file_bytes).decode("ascii")
        headers = {
            "Authorization": f"token {self.token}",
            "Content-Type": "application/json",
        }
        payload = {
            "file": file_data,
            "fileType": 1,
            **self.optional_payload,
        }
        response = requests.post(self.sync_url, json=payload, headers=headers, timeout=120)
        if response.status_code != 200:
            return False, f"sync OCR 请求失败: {response.status_code}, {response.text[:300]}", ""
        result = response.json().get("result", {})
        markdown_text = self._collect_markdown_text(result)
        return True, "success", markdown_text

    def _parse_image_async(self, file_path: str) -> Tuple[bool, str, str]:
        headers = {
            "Authorization": f"bearer {self.token}",
        }
        data = {
            "model": self.model,
            "optionalPayload": json.dumps(self.optional_payload),
        }
        job_response = None
        for attempt in range(1, self.submit_retries + 2):
            with open(file_path, "rb") as f:
                files = {"file": f}
                job_response = requests.post(self.async_job_url, headers=headers, data=data, files=files, timeout=120)
            if job_response.status_code == 200:
                break
            if not self._is_queue_full_response(job_response):
                return False, f"async OCR 提交失败: {job_response.status_code}, {job_response.text[:300]}", ""
            if attempt > self.submit_retries:
                return False, f"async OCR 提交失败: 队列已满，已重试 {self.submit_retries} 次", ""
            wait_seconds = min(self.submit_retry_delay * attempt, 180)
            logger.warning(
                f"async OCR 队列已满，{wait_seconds}s 后重试提交 "
                f"({attempt}/{self.submit_retries})"
            )
            self._sleep_interruptibly(wait_seconds)
        job_id = job_response.json().get("data", {}).get("jobId", "")
        if not job_id:
            return False, "async OCR 未返回 jobId", ""

        start_at = time.time()
        while True:
            if time.time() - start_at > self.timeout_seconds:
                return False, f"async OCR 超时（>{self.timeout_seconds}s）", ""
            result_response = requests.get(f"{self.async_job_url}/{job_id}", headers=headers, timeout=60)
            if result_response.status_code != 200:
                self._sleep_interruptibly(self.poll_interval)
                continue
            data_json = result_response.json().get("data", {})
            state = data_json.get("state")
            if state in {"pending", "running"}:
                self._sleep_interruptibly(self.poll_interval)
                continue
            if state == "failed":
                return False, f"async OCR 任务失败: {data_json.get('errorMsg', 'unknown')}", ""
            if state == "done":
                jsonl_url = data_json.get("resultUrl", {}).get("jsonUrl", "")
                if not jsonl_url:
                    return False, "async OCR 缺少结果地址 jsonUrl", ""
                return self._read_async_result(jsonl_url)
            return False, f"async OCR 未知状态: {state}", ""

    @staticmethod
    def _is_queue_full_response(response: requests.Response) -> bool:
        if response.status_code not in {400, 429, 503}:
            return False
        try:
            body = response.json()
        except ValueError:
            body = {}
        msg = str(body.get("msg", response.text))
        code = str(body.get("code", ""))
        return code == "10010" or "队列已满" in msg

    @staticmethod
    def _sleep_interruptibly(seconds: int) -> None:
        end_at = time.time() + max(0, seconds)
        while True:
            remaining = end_at - time.time()
            if remaining <= 0:
                return
            time.sleep(min(remaining, 0.5))

    def _read_async_result(self, jsonl_url: str) -> Tuple[bool, str, str]:
        res = requests.get(jsonl_url, timeout=120)
        if res.status_code != 200:
            return False, f"下载 OCR 结果失败: {res.status_code}", ""
        all_text: List[str] = []
        for line in res.text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            result = obj.get("result", {})
            text = self._collect_markdown_text(result)
            if text:
                all_text.append(text)
        return True, "success", "\n\n".join(all_text).strip()

    @staticmethod
    def _collect_markdown_text(result: Dict[str, Any]) -> str:
        texts: List[str] = []
        for layout_item in result.get("layoutParsingResults", []):
            text = layout_item.get("markdown", {}).get("text", "")
            if text:
                texts.append(text)
        return "\n\n".join(texts).strip()


def build_ocr_client_from_env(
    mode: str = "async",
    poll_interval: int = 5,
    timeout_seconds: int = 300,
    submit_retries: Optional[int] = None,
    submit_retry_delay: Optional[int] = None,
) -> Optional[OCRClient]:
    token = os.getenv("OCR_TOKEN", "").strip()
    if not token:
        logger.warning("未配置 OCR_TOKEN，已跳过 OCR。")
        return None
    sync_url = os.getenv("OCR_SYNC_URL", "https://o6f4pfe0wf57ico6.aistudio-app.com/layout-parsing")
    async_job_url = os.getenv("OCR_ASYNC_JOB_URL", "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs")
    model = os.getenv("OCR_MODEL", "PaddleOCR-VL-1.6")
    if submit_retries is None:
        submit_retries = _read_int_env("OCR_SUBMIT_RETRIES", 5)
    if submit_retry_delay is None:
        submit_retry_delay = _read_int_env("OCR_SUBMIT_RETRY_DELAY", 30)
    return OCRClient(
        token=token,
        mode=mode,
        sync_url=sync_url,
        async_job_url=async_job_url,
        model=model,
        poll_interval=poll_interval,
        timeout_seconds=timeout_seconds,
        submit_retries=submit_retries,
        submit_retry_delay=submit_retry_delay,
    )


def _read_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except ValueError:
        logger.warning(f"{name} 不是有效整数，已使用默认值 {default}。")
        return default
