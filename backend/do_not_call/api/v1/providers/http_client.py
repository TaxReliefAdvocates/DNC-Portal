from typing import Optional, Dict, Any
import httpx
from loguru import logger


class HttpClient:
	def __init__(self, base_url: Optional[str] = None, headers: Optional[Dict[str, str]] = None, timeout: float = 30.0):
		self.base_url = base_url
		self.headers = headers or {}
		self.timeout = timeout
		self._client: Optional[httpx.AsyncClient] = None

	async def __aenter__(self):
		if self.base_url:
			self._client = httpx.AsyncClient(base_url=self.base_url, headers=self.headers, timeout=self.timeout)
		else:
			self._client = httpx.AsyncClient(headers=self.headers, timeout=self.timeout)
		return self

	async def __aexit__(self, exc_type, exc, tb):
		if self._client:
			await self._client.aclose()

	async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
		if not self._client:
			raise RuntimeError("HttpClient not initialized. Use 'async with HttpClient(...)' context manager.")
		try:
			logger.debug(f"HTTP {method} {url} | params={kwargs.get('params')} | data={kwargs.get('data')} | json={kwargs.get('json')}")
			response = await self._client.request(method, url, **kwargs)
			logger.debug(f"HTTP {method} {url} -> {response.status_code}")
			response.raise_for_status()
			return response
		except httpx.HTTPStatusError as e:
			logger.error(f"HTTP error {e.response.status_code} for {method} {url}: {e.response.text}")
			raise
		except Exception as e:
			logger.exception(f"Unexpected HTTP error for {method} {url}: {e}")
			raise

	async def get(self, url: str, **kwargs) -> httpx.Response:
		return await self.request("GET", url, **kwargs)

	async def post(self, url: str, **kwargs) -> httpx.Response:
		return await self.request("POST", url, **kwargs)

	async def patch(self, url: str, **kwargs) -> httpx.Response:
		return await self.request("PATCH", url, **kwargs)

	async def delete(self, url: str, **kwargs) -> httpx.Response:
		return await self.request("DELETE", url, **kwargs)
