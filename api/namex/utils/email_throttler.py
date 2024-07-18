import threading
import asyncio
from typing import Callable
from namex.models import PendingEmail

class EmailThrottler:
    """
    Manages the throttling of sending emails by using a dedicated emailer thread. The emailer thread 
    manages an event loop where email tasks are scheduled and awaited for each NR. Once a task completes
    on the emailer thread, the task makes a call to send the most recent email stored for the NR. 

    All emails stored by this class are written to and deleted from the db as they are used to have 
    peristent storage of pending emails.
    """

    def __init__(self, app):
        self.app = app
        self.throttle_time = 10
        self.email_thread_status = threading.Event()
        try:
            self.email_thread = threading.Thread(target=self.start_event_loop, daemon=True)
            self.email_thread_loop = asyncio.new_event_loop()
            self.threading_lock = threading.Lock()
            self.email_thread.start()
            self.email_thread_status.set()

            self.email_tasks: dict[str, asyncio.Task] = {}
            self.email_callbacks: dict[str, Callable] = {}

        except Exception as e:
            self.app.logger.error(f'Failed to Initialize Email Throttler, {e}')
            self.email_thread_status.clear()


    def start_event_loop(self):
        """
        Starts the event loop that runs indefinetly on the emailer thread. Email tasks from the
        main thread are scheduled using this loop. 
        """
        try:
            asyncio.set_event_loop(self.email_thread_loop)
            self.email_thread_loop.run_forever()
        except Exception as e:
            self.app.logger.error(f'Exception in Email Throttler Loop: {e}')
        finally:
            self.app.logger.debug('Uh oh, Email Throttler Loop has stopped unexpectedly.')
            self.email_thread_status.clear()


    def schedule_or_update_email_task(self, nr_num: str, decision: str, email: Callable):
        """
        Schedules a new email task on the emailer thread or updates an existing task's email callback.
        Once the task completes only the most recent email for the NR will be sent.

        If an error is encountered all of the pending emails are sent and the emailer thread is closed.
        """
        with self.threading_lock:
            self.email_callbacks[nr_num] = email
            PendingEmail.add_or_update_email(nr_num, decision)

            try:
                if nr_num not in self.email_tasks.keys():
                    self.email_thread_loop.call_soon_threadsafe(
                        lambda: self.email_tasks.update(
                            {nr_num: asyncio.create_task(self.send_email_after_delay(nr_num))}
                        )
                    )
            except Exception as e:
                self.app.logger.error(f'Exception when throttling the email: {e}')
                email()
                PendingEmail.delete_record(nr_num)


    async def send_email_after_delay(self, nr_num: str):
        """
        Waits for a specified delay, then triggers the callback email for the given NR.
        Scheduled on the Emailer Thread Event Loop.
        """
        await asyncio.sleep(self.throttle_time)

        with self.app.app_context():
            try:
                self.email_callbacks[nr_num]()
                PendingEmail.delete_record(nr_num)
            except Exception as e:
                self.app.logger.error(f'Error handling email for {nr_num}: {e}')
            finally:
                self.email_tasks.pop(nr_num, None)
                self.email_callbacks.pop(nr_num, None)
