from tkinter import ttk


class HoldableButton(ttk.Button):
    """
    calls the command repeatedly while the Button is held
    :command: the function to run
    :timeout: the number of milliseconds between :command: calls
      if timeout is not supplied, this Button runs the function once on the DOWN click,
      unlike a normal Button, which runs on release
    """
    def __init__(self, master=None, **kwargs):
        self.command = kwargs.pop('command', None)
        self.timeout = kwargs.pop('timeout', None)
        ttk.Button.__init__(self, master, **kwargs)
        self.bind('<ButtonPress-1>', self.start)
        self.bind('<ButtonRelease-1>', self.stop)
        self.timer = ''

    def start(self, event=None):
        if self.command is not None:
            self.command()
            if self.timeout is not None:
                self.timer = self.after(self.timeout, self.start)

    def stop(self, event=None):
        self.after_cancel(self.timer)
