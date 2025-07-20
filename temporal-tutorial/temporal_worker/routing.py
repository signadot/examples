import os
import asyncio
import time
import aiohttp
from typing import Set, Optional
from urllib.parse import urlencode, urlunparse, urlparse, ParseResult
import logging
logger = logging.getLogger("temporal_worker.routing")

# All config values are now read from environment variables, with safe fallbacks
class RoutesAPIClient:
    """
    Client for fetching routing rules from the central platform routing API.
    Handles caching and refresh of routing keys for sandbox/baseline selection.
    """
    def __init__(self, sandbox_name: str):
        self.sandbox_name = sandbox_name
        self.route_server_addr_base = os.environ["ROUTES_API_ROUTE_SERVER_ADDR"]
        parsed_addr = urlparse(self.route_server_addr_base)
        self.route_server_scheme = parsed_addr.scheme or "http"
        self.route_server_netloc = parsed_addr.netloc
        self.baseline_kind = os.environ["ROUTES_API_BASELINE_KIND"]
        self.baseline_namespace = os.environ["ROUTES_API_BASELINE_NAMESPACE"]
        self.baseline_name = os.environ["ROUTES_API_BASELINE_NAME"]
        self.refresh_interval = int(os.environ["ROUTES_API_REFRESH_INTERVAL_SECONDS"])
        self._routing_keys_cache: Set[str] = set()
        self._cache_update_lock = asyncio.Lock()
        self._cache_updated_event = asyncio.Event()
        self._last_successful_update_time: float = 0.0
        self._is_first_update_done = False

    def _build_routes_url(self) -> str:
        query_params = {
            'baselineKind': self.baseline_kind,
            'baselineNamespace': self.baseline_namespace,
            'baselineName': self.baseline_name
        }
        if self.sandbox_name:
            query_params['destinationSandboxName'] = self.sandbox_name
        path = '/api/v1/workloads/routing-rules'
        url_parts = ParseResult(
            scheme=self.route_server_scheme,
            netloc=self.route_server_netloc,
            path=path,
            params='',
            query=urlencode(query_params),
            fragment=''
        )
        return urlunparse(url_parts)

    async def _perform_fetch_and_update(self) -> None:
        url = self._build_routes_url()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        new_routing_keys = set()
                        if isinstance(data, dict) and 'routingRules' in data and isinstance(data['routingRules'], list):
                            for rule in data['routingRules']:
                                if isinstance(rule, dict) and 'routingKey' in rule and rule['routingKey'] is not None:
                                    new_routing_keys.add(str(rule['routingKey']))
                        # Only log if the routing keys have changed
                        if new_routing_keys != self._routing_keys_cache:
                            logger.info(f"RoutesAPIClient: Routing keys updated: {list(new_routing_keys)}")
                        self._routing_keys_cache = new_routing_keys
                        self._last_successful_update_time = time.monotonic()
                        self._is_first_update_done = True
                    else:
                        logger.error(f"RoutesAPIClient: Error fetching routes. Status: {response.status}, Body: {await response.text()}")
        except aiohttp.ClientError as e:
            logger.error(f"RoutesAPIClient: HTTP client error fetching routes: {e}")
        except Exception as e:
            logger.error(f"RoutesAPIClient: Error during route fetch/parse: {e}")

    async def _ensure_cache_fresh(self) -> None:
        current_time = time.monotonic()
        needs_update = not self._is_first_update_done or \
                       (current_time - self._last_successful_update_time > self.refresh_interval)
        if needs_update:
            if self._cache_update_lock.locked():
                await self._cache_updated_event.wait()
            else:
                async with self._cache_update_lock:
                    current_time_after_lock = time.monotonic()
                    if not self._is_first_update_done or \
                       (current_time_after_lock - self._last_successful_update_time > self.refresh_interval):
                        self._cache_updated_event.clear()
                        try:
                            await self._perform_fetch_and_update()
                        finally:
                            self._cache_updated_event.set()
                    else:
                        if not self._cache_updated_event.is_set(): self._cache_updated_event.set()

    async def _periodic_cache_updater(self):
        try:
            sandbox_info = f"sandbox '{self.sandbox_name}'" if self.sandbox_name else "baseline"
            logger.info(f"RoutesAPIClient: Starting periodic cache updater for {sandbox_info} with {self.refresh_interval}s polling interval")
            
            while True:
                await self._ensure_cache_fresh()
                await asyncio.sleep(self.refresh_interval)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"RoutesAPIClient: Periodic cache updater for sandbox '{self.sandbox_name or 'baseline'}' error: {e}")

    async def should_process(self, routing_key: Optional[str]) -> bool:
        """
        Determine if a workflow/activity with the given routing key should be processed by this worker.
        """
        current_cached_keys = self._routing_keys_cache
        if self.sandbox_name:
            if routing_key is None:
                logger.debug(f"Sandbox worker: No routing key provided, will not process.")
                return False
            should = routing_key in current_cached_keys
            logger.debug(
                f"Sandbox worker: routing_key={routing_key}, cache={list(current_cached_keys)}, should_process={should}"
            )
            return should
        else:
            if routing_key is None:
                logger.debug(f"Baseline worker: No routing key provided, will process.")
                return True
            should = routing_key not in current_cached_keys
            logger.debug(
                f"Baseline worker: routing_key={routing_key}, cache={list(current_cached_keys)}, should_process={should}"
            )
            return should

