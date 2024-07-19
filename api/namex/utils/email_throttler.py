import threading
import asyncio
from typing import Callable

class EmailThrottler:
    """
    Manages the throttling of sending emails by using a dedicated emailer thread. The emailer thread 
    manages an event loop where email tasks are scheduled and awaited asynchronously for each NR. 
    Once a task completes on the emailer thread, it sends the most recent email stored for the NR. 
    All emails stored by this class are written to and deleted from the db.
    """

    def __init__(self, app):
        self.app = app
        self.throttle_time = 300
        self.email_thread_status = threading.Event()
        self._send_pending_emails_on_startup()
        try:
            self.email_thread = threading.Thread(target=self._start_event_loop, daemon=True)
            self.email_thread_loop = asyncio.new_event_loop()
            self.email_thread.start()

            self.email_tasks: dict[str, asyncio.Task] = {}
            self.email_callbacks: dict[str, Callable | None] = {}

            self.email_thread_status.set()
        except Exception as e:
            self.app.logger.error(f'Failed to Initialize Email Throttler, {e}')
            self.email_thread_status.clear()
    

    def _start_event_loop(self):
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
            self.app.logger.error('Uh oh, Email Throttler Loop has stopped unexpectedly.')
            self.email_thread_status.clear()


    def schedule_or_update_email_task(self, nr_num: str, decision: str, email: Callable):
        """
        Schedules a new email task on the emailer thread or updates an existing one.
        Once the task completes only the most recent email for the NR will be sent.
    
        If an error occurs when scheduling the task the email is sent immediately.
        """
        from namex.models import PendingEmail

        self.email_callbacks[nr_num] = email
        PendingEmail.add_or_update_email(nr_num, decision)


        try:
            if nr_num not in self.email_tasks.keys():
                # The callback creates & registers an async task in the email_tasks dictionary
                self.email_thread_loop.call_soon_threadsafe(
                    lambda: self.email_tasks.update(
                        {nr_num: asyncio.create_task(self._send_email_after_delay(nr_num))}
                    )
                )
        except Exception as e:
            self.app.logger.error(f'Exception when throttling the email: {e}')
            email()
            self.email_tasks.pop(nr_num, None)
            self.email_callbacks.pop(nr_num, None)
            PendingEmail.delete_record(nr_num)
    

    def hold_email_task(self, nr_num: str, decision: str):
        """
        Prevents an email from being sent if it is set to HOLD or INPROGRESS state. The
        email will still be held in memory / storage. This allows for a name to be approved
        and then put back on HOLD without sending and email to the client. 
        """
        from namex.models import PendingEmail

        self.email_callbacks[nr_num] = None
        PendingEmail.add_or_update_email(nr_num, decision)
    

    async def _send_email_after_delay(self, nr_num: str):
        """
        Waits for a specified delay, then calls the callback email for the given NR 
        on the emailer thread. If the email fails to send it will stay in persistent storage.
        """
        from namex.models import PendingEmail

        await asyncio.sleep(self.throttle_time)

        with self.app.app_context():
            try:
                if self.email_callbacks[nr_num]:
                    self.email_callbacks[nr_num]()
                PendingEmail.delete_record(nr_num)
            except Exception as e:
                self.app.logger.error(f'Error handling email for {nr_num}: {e}')
            finally:
                self.email_tasks.pop(nr_num, None)
                self.email_callbacks.pop(nr_num, None)


    def _send_pending_emails_on_startup(self):
        from namex.models import PendingEmail, State
        from namex.utils import queue_util

        with self.app.app_context():
            emails = PendingEmail.query.all()
            if emails:
                self.app.logger.debug(f'Processing {len(emails)} pending emails on startup after app shutdown')
                for email in emails:
                    if email.decision in [State.APPROVED, State.REJECTED, State.CONDITIONAL]:
                        queue_util.publish_email_notification(email.nr_num, email.decision)
                    PendingEmail.delete_record(email.nr_num)
