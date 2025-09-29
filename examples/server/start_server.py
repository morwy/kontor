#!/usr/bin/env python
import logging
import os
import signal
import sys

from kontor.bureau import Bureau


def shutdown_signal_handler(sig, frame):
    logging.critical("Caught SIGINT signal, bureau will be shut down.")
    sys.exit(0)


if __name__ == "__main__":
    #
    # Catch Ctrl+C signal for notifying about bureau shutdown.
    #
    signal.signal(signal.SIGINT, shutdown_signal_handler)

    bureau = Bureau(os.path.dirname(os.path.realpath(__file__)))
    bureau.start()
