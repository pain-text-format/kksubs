from abc import ABC, abstractmethod
import logging
import time
import traceback
from common.exceptions import *

logger = logging.getLogger(__name__)

class AbstractWatcher(ABC):
    
    def __init__(self):
        self.sleep_time = 1

    def setup_watch(self):
        logger.info(f'Setting up watcher.')

    @abstractmethod
    def event_trigger_action(self):
        ...
    
    @abstractmethod
    def event_idle_action(self):
        ...

    def close(self):
        logger.info('Closing watcher.')

    @abstractmethod
    def is_event_trigger(self) -> bool:
        ...

    def watch(self):
        try:
            self.setup_watch()
            unresolved_event_trigger = False
            while True:
                try:
                    event_triggered = self.is_event_trigger()
                    if unresolved_event_trigger:
                        self.event_trigger_action()
                        unresolved_event_trigger = False
                    elif event_triggered:
                        self.event_trigger_action()
                    else:
                        self.event_idle_action()
                except KeyboardInterrupt:
                    raise KeyboardInterrupt
                except RetryWatcherPrompt:
                    logger.info('Received prompt to restart watcher cycle.')
                    unresolved_event_trigger = True
                except Exception:
                    logger.error(f"An error occurred during watch cycle; retrying... Exception: {traceback.format_exc()}")

                time.sleep(self.sleep_time)

        except KeyboardInterrupt:
            self.close()
    pass

