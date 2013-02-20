from gameconst import *
from direct.task import Task

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