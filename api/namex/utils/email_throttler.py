import threading
import asyncio
from typing import Callable

class EmailThrottler:
    """
    Manages the throttling of sending emails by using a dedicated emailer thread. The emailer thread 
    manages an event loop where email tasks are scheduled and awaited for each NR. Once a task completes
    on the emailer thread, the task makes a call to send the most recent email stored for the NR. 

    This thread is created on start-up and each WSGI worker gets one of these. 
    """

    def __init__(self, app):
        self.app = app
        self.throttle_time = 10
        self.email_thread_status = threading.Event()
        self.email_thread_ready_to_close = threading.Event()
        self.email_thread_finished = threading.Event()
        try:
            self.email_thread = threading.Thread(target=self.start_event_loop, daemon=True)
            self.email_thread_loop = asyncio.new_event_loop()
            self.threading_lock = threading.Lock()
            self.email_thread.start()
            self.email_thread_status.set()

            self.email_tasks: dict[str, asyncio.Task] = {}
            self.email_callbacks: dict[str, Callable] = {}

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
            self.email_thread_loop.run_forever()
        except Exception as e:
            self.app.logger.error(f'Exception in Email Throttler Loop: {e}')
        finally:
            print("HERE")
            self.email_thread_ready_to_close.wait()
            print("THERE")
            self.email_thread_status.clear()
            self.app.logger.debug('Emailer Thread has been shutdown.')
            self.email_thread_loop.close()
            self.app.logger.debug('Closed the loop.')
            self.email_thread.join()


    def schedule_or_update_email_task(self, nr_num: str, email: Callable):
        """
        Schedules a new email task on the emailer thread or updates an existing task's email callback.
        Once the task completes only the most recent email for the NR will be sent.

        If an error is encountered all of the pending emails are sent and the emailer thread is closed.
        """
        try:
            self.email_callbacks[nr_num] = email

            if nr_num not in self.email_tasks.keys():
                self.email_thread_loop.call_soon_threadsafe(
                    lambda: self.email_tasks.update(
                        {nr_num: asyncio.create_task(self.send_email_after_delay(nr_num))}
                    )
                )
                raise Exception
        except Exception as e:
            self.app.logger.error(f'Exception when throttling the email: {e}')
            future = asyncio.run_coroutine_threadsafe(self.flush_and_stop_emailer_thread(), self.email_thread_loop)
            future.result()
            print("SETTING TO READY TO CLOSE")
            self.email_thread_ready_to_close.set()


    async def send_email_after_delay(self, nr_num: str):
        """
        Waits for a specified delay, then triggers the callback email for the given NR.
        Scheduled on the Emailer Thread Event Loop.
        """
        await asyncio.sleep(self.throttle_time)

        with self.app.app_context():
            try:
                self.email_callbacks[nr_num]()
                self.email_tasks.pop(nr_num, None)
                self.email_callbacks.pop(nr_num, None)
            except Exception as e:
                self.app.logger.error(f'Error handling email for {nr_num}: {e}')


    async def flush_and_stop_emailer_thread(self):
        """
        Sends all emails and prepares the emailer thread for closure. 
        """
        with self.app.app_context():
            # Cancel all tasks
            for task in self.email_tasks.values():
                task.cancel()
            await asyncio.gather(*self.email_tasks.values(), return_exceptions=True)
            self.email_tasks.clear()
            
            # Execute any pending callbacks
            for callback in self.email_callbacks.values():
                callback()
            self.email_callbacks.clear()

            # Stop the loop
            self.email_thread_loop.stop()
            self.email_thread_ready_to_close.set()
