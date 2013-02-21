from gameconst import *
import threading

class ThreadShutdownMixIn(object):
    """Mix-In class to execute a task forever until a shutdown request is emitted.
    Based on python threading."""
    # tells whether the server should be shut down when the main thread is done
    # daemon_threads
    
    def __init__(self):
        # flag set to True if a request for shutdown was emitted
        self._shutdown_request = False
        self._silent_shutdown = False
        # this event enables an other process to wait
        # until this process is effectively shut down
        self._is_shut_down = threading.Event()
    
    def do_while_not_shut_down(self, iter_fun=(lambda: None), args=()):
        """Iter calls to fun(args) until a shutdown request is emitted"""
        self._is_shut_down.clear()
        try:
            while not self._shutdown_request:
                iter_fun(*args)
        finally:
            self._shutdown_request = False
            if not self._silent_shutdown:
                self._do_on_shutdown()
            self._is_shut_down.set()
            
    def _do_on_shutdown(self):
        """This function is called just before the process is shut-downed.
        
        May be overriden"""
        pass
        
    def shutdown(self, non_blocking=False, silent=False):
        # if the silent option is true, the process will be shut down
        # without calling the usual _do_on_shutdown
        self._silent_shutdown = silent
        self._shutdown_request = True
        if not non_blocking:
            self._is_shut_down.wait()
    
    def is_shut_down(self):
        return self._is_shut_down.is_set()
        
    def do_in_thread(self, fun=(lambda: None), args=()):
        t = threading.Thread(
            target=fun,
            args=args
        )
        t.daemon = self.daemon_threads
        t.start()
        return t

