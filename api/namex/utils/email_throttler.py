
import threading
import asyncio
import signal
import sys
from typing import Callable

class EmailThrottler:
    """
    Manages the throttling of sending emails by using a dedicated emailer thread. The emailer thread 
    manages an event loop where email tasks are scheduled and awaited for each NR. Once a task completes
    on the emailer thread, the task makes a call to send the most recent email stored for the NR. 

    Handles both system termination and error conditions by flushing the emails ensuring that no emails are lost. 
    """

    def __init__(self, app):
        self.app = app
        self.throttle_time = 120
        # self.shutting_down = False
        # self.shutdown_complete = threading.Event()
        try:
            self.email_thread = threading.Thread(target=self.start_event_loop, daemon=True)
            self.email_thread_loop = asyncio.new_event_loop()
            self.email_thread_status = threading.Event()
            self.threading_lock = threading.Lock()
            self.email_thread.start()

            self.email_tasks: dict[str, asyncio.Task] = {}
            self.email_callbacks: dict[str, Callable] = {}

            # signal.signal(signal.SIGTERM, self.handle_app_termination)
            # signal.signal(signal.SIGINT, self.handle_app_termination)

            self.initialized = True
            
        except Exception as e:
            self.app.logger.error(f'Failed to Initialize Email Throttler, {e}')
            self.initialized = False


    def start_event_loop(self):
        """
        Starts the event loop that runs indefinetly on the emailer thread. Email tasks from the
        main thread are scheduled using this loop. If an exception occurs, all of the emails 
        are flushed and the loop is stopped and emailer thread closed.
        """
        try:
            asyncio.set_event_loop(self.email_thread_loop)
            self.email_thread_status.set()
            self.email_thread_loop.run_forever()
        except Exception as e:
            self.app.logger.error(f'Exception in Email Throttler Loop: {e}')
            asyncio.run_coroutine_threadsafe(self.flush_and_stop_emailer_thread(), self.email_thread_loop)
            self.email_thread.join()


    def schedule_or_update_email_task(self, nr_num: str, email: Callable):
        """
        Schedules a new email task on the emailer thread or updates an existing task's email callback.
        Once the task completes only the most recent email for the NR will be sent.

        If an error is encountered all of the pending emails are sent and the emailer thread is closed.
        """
        try:
            with self.threading_lock:
                self.email_callbacks[nr_num] = email

                if nr_num not in self.email_tasks.keys():
                    self.email_thread_loop.call_soon_threadsafe(
                        lambda: self.email_tasks.update(
                            {nr_num: asyncio.create_task(self.send_email_after_delay(nr_num))}
                        )
                    )
        except Exception as e:
            self.app.logger.error(f'Exception when throttling the email: {e}')
            asyncio.run_coroutine_threadsafe(self.flush_and_stop_emailer_thread(), self.email_thread_loop)
            self.email_thread.join()


    async def send_email_after_delay(self, nr_num: str):
        """Waits for a specified delay, then sends an email for the given identifier from the emailer thread."""
        await asyncio.sleep(self.throttle_time)
        with self.app.app_context():
            try:
                with self.threading_lock:
                    self.email_callbacks[nr_num]()
                    self.email_tasks.pop(nr_num, None)
                    self.email_callbacks.pop(nr_num, None)
            except Exception as e:
                self.app.logger.error(f'Error handling email for {nr_num}: {e}')


    async def flush_and_stop_emailer_thread(self):
        with self.app.app_context():
            with self.threading_lock:
                self.app.logger.debug('Flushing all pending emails from emailer thread')
                nr_nums = list(self.email_callbacks.keys())
                tasks = []

                for nr_num in nr_nums:
                    try:
                        if nr_num in self.email_tasks:
                            task = self.email_tasks.pop(nr_num)
                            task.cancel()
                            tasks.append(task)
                        if nr_num in self.email_callbacks:
                            self.email_callbacks[nr_num]()
                            self.email_callbacks.pop(nr_num)
                    except Exception as e:
                        self.app.logger.error(f'Error handling email for {nr_num}: {e}')

                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                
            self.email_thread_loop.stop()
            # self.shutdown_complete.set()

        
    # def handle_app_termination(self, signum, frame):
    #     """Signals to the emailer thread to send all pending emails and close the thread."""
    #     if not self.shutting_down:
    #         self.shutting_down = True
    #         asyncio.run_coroutine_threadsafe(self.flush_and_stop_emailer_thread(), self.email_thread_loop)
    #         self.shutdown_complete.wait()
    #         self.email_thread.join()
    #         sys.exit(0)
