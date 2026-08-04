import requests
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from typing import Dict, Optional, Any
from utils.logger import get_logger

log = get_logger("http-request")

# 全局默认配置
DEFAULT_TIMEOUT = 10
RETRY_TIMES = 2
RETRY_WAIT = 1  # 重试等待秒数


class HttpClient:
    def __init__(self):
        self.session = requests.Session()

    @retry(
        stop=stop_after_attempt(RETRY_TIMES),
        wait=wait_fixed(RETRY_WAIT),
        retry=retry_if_exception_type((requests.exceptions.ConnectionError, requests.exceptions.Timeout)),
        reraise=True
    )
    def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: int = DEFAULT_TIMEOUT,
        **kwargs
    ) -> Dict[str, Any]:
        """通用请求方法，自动重试网络异常"""
        method = method.upper()
        log.info(f"{method} {url} | params={params}")
        try:
            resp = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json,
                data=data,
                headers=headers,
                timeout=timeout,
                **kwargs
            )
            resp.raise_for_status()
            result = resp.json()
            log.debug(f"接口返回: {str(result)[:300]}")
            return result
        except requests.exceptions.HTTPError as e:
            log.error(f"HTTP状态码异常: {e}, response={resp.text if 'resp' in locals() else ''}")
            raise
        except Exception as e:
            log.error(f"接口请求失败: {str(e)}", exc_info=True)
            raise

    def get(self, url, params=None, headers=None, **kwargs):
        return self.request("GET", url, params=params, headers=headers,** kwargs)

    def post(self, url, json=None, data=None, headers=None, **kwargs):
        return self.request("POST", url, json=json, data=data, headers=headers, **kwargs)


# 全局单例
http_client = HttpClient()