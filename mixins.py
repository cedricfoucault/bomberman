from direct.task import Task
import threading

class TaskShutdownMixIn(object):
    """Mix-In class to execute a task to be called once each frame
    until a shutdown request is emitted. Based on Panda3d tasks."""
    
    def __init__(self):
        # Flag to tell if this task has been shutdown
        self._is_shut_down = False
            
    def do_task(self, fun, time_interval=None, name='No Name'):
        """Add to the task manager a task which calls fun().
        If time_interval is given, the task will be done once each
        time_interval seconds, otherwise it will be done once each frame."""
        self._is_shut_down = False
        if time_interval:
            def fun_task(task):
                fun()
                return Task.again
            self.task = taskMgr.doMethodLater(time_interval, fun_task, name)
        else:
            def fun_task(task):
                fun()
                return Task.cont
            self.task = taskMgr.add(fun_task, name)
    
    def _do_on_shutdown(self):
        """This function is called just before the process is shut-downed.
        
        May be overriden"""
        pass
        
    def shutdown(self, silent=False):
        """Stop the server from accepting new connections"""
        # if the silent option is true, the process will be shut down
        # without calling the usual _do_on_shutdown
        taskMgr.remove(self.task)
        self._is_shut_down = True
        if not silent:
            self._do_on_shutdown()
    
    def is_shut_down(self):
        return self._is_shut_down
        

class ThreadShutdownMixIn(object):
    """Mix-In class to execute a task forever until a shutdown request is emitted.
    Based on python threading."""
    
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

