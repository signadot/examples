import os
import asyncio
import logging
import signal
import sys
from typing import List, Any
from temporalio.worker import Worker
from temporalio.client import Client
from temporalio.contrib.opentelemetry import TracingInterceptor

from routing import RoutesAPIClient
from interceptors import SelectiveTaskInterceptor

logger = logging.getLogger("temporal_worker.sandbox_aware_worker")

class SandboxAwareWorker:
    """
    A Temporal worker that automatically handles Signadot sandbox routing and context propagation.
    Developers can extend this class to add their domain-specific workflows and activities.
    """
    
    def __init__(self, task_queue: str, workflows: List[Any], activities: List[Any]):
        """
        Initialize the SandboxAware worker.
        
        Args:
            task_queue: The task queue name for this worker
            workflows: List of workflow classes to register
            activities: List of activity functions to register
        """
        self.task_queue = task_queue
        self.workflows = workflows
        self.activities = activities
        self.sandbox_name = os.environ.get("SIGNADOT_SANDBOX_NAME", "")
        self.temporal_url = os.environ["TEMPORAL_SERVER_URL"]
        
        # Initialize routes client for sandbox routing
        self.routes_client = RoutesAPIClient(sandbox_name=self.sandbox_name)
        
        # Worker state
        self.worker = None
        self.client = None
        self.tasks = []
        self.stop_event = asyncio.Event()
    
    async def _cache_updater(self):
        """Background task to update routing cache."""
        try:
            await self.routes_client._periodic_cache_updater()
        except asyncio.CancelledError:
            logger.info("Cache updater cancelled.")
    
    async def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._shutdown)
    
    def _shutdown(self):
        """Handle shutdown signal."""
        logger.info("Received shutdown signal. Cancelling tasks...")
        for task in self.tasks:
            task.cancel()
        self.stop_event.set()
    
    async def _create_worker(self):
        """Create and configure the Temporal worker."""
        # Connect to Temporal server
        self.client = await Client.connect(
            self.temporal_url, 
            interceptors=[TracingInterceptor()]
        )
        logger.info(f"Connected to Temporal server: {self.temporal_url}")
        
        # Create worker with sandbox-aware interceptors
        self.worker = Worker(
            self.client,
            task_queue=self.task_queue,
            workflows=self.workflows,
            activities=self.activities,
            interceptors=[
                TracingInterceptor(always_create_workflow_spans=True),
                SelectiveTaskInterceptor(self.routes_client, self.sandbox_name, self.task_queue)
            ]
        )
        
        worker_identity = f"sandbox={self.sandbox_name or 'baseline'} task_queue={self.task_queue}"
        logger.info(f"Worker created successfully: {worker_identity}")
    
    async def _run_worker(self):
        """Run the worker and cache updater tasks."""
        try:
            # Create worker
            await self._create_worker()
            
            # Start cache updater task
            cache_task = asyncio.create_task(self._cache_updater())
            self.tasks.append(cache_task)
            
            # Start worker
            logger.info("Starting to poll for tasks...")
            await self.worker.run()
            
        except asyncio.CancelledError:
            logger.info("Worker cancelled.")
        except Exception as e:
            logger.error(f"Error running worker: {e}")
            self._shutdown()
    
    async def start(self):
        """Start the SandboxAware worker."""
        try:
            # Setup signal handlers
            await self._setup_signal_handlers()
            
            # Start worker task
            worker_task = asyncio.create_task(self._run_worker())
            self.tasks.append(worker_task)
            
            # Wait for shutdown signal
            await self.stop_event.wait()
            
            # Wait for all tasks to complete
            await asyncio.gather(*self.tasks, return_exceptions=True)
            
        finally:
            logger.info("Shutdown complete.")
            # Check for exceptions
            for task in self.tasks:
                if task.done() and not task.cancelled():
                    exc = task.exception()
                    if exc and not isinstance(exc, asyncio.CancelledError):
                        sys.exit(1)
    
    def run(self):
        """Entry point for running the worker."""
        asyncio.run(self.start()) 