import os
import platform
from time import sleep
import logging
import subprocess
from typing import Optional, List

logger = logging.getLogger(__name__)


def _locate_executable(name: str) -> List[str]:
    """
    Will start module from localdir if present there,
    otherwise will try to call what is available in PATH.

    Returns it as a Popen cmd list.
    """
    curr_filepath = os.path.realpath(__file__)
    curr_dir = os.path.dirname(curr_filepath)
    search_paths = [curr_dir, os.path.abspath(os.path.join(curr_dir, os.pardir))]
    exec_paths = [os.path.join(path, name) for path in search_paths]

    for exec_path in exec_paths:
        if os.path.isfile(exec_path):
            # logger.debug("Found executable for {} in: {}".format(name, exec_path))
            return [exec_path]
            break  # this break is redundant, but kept due to for-else semantics
    else:
        # TODO: Actually check if it is in PATH
        # logger.debug("Trying to start {} using PATH (executable not found in: {})"
        #              .format(name, exec_paths))
        return [name]


class Module:
    def __init__(self, name: str) -> None:
        self.name = name
        self.started = False
        self._process = None  # type: Optional[subprocess.Popen]
        self._last_process = None  # type: Optional[subprocess.Popen]
        self._log = ""

    def start(self, testing: bool = False) -> None:
        logger.info("Starting module {}".format(self.name))

        # Create a process group, become its leader
        if platform.system() != "Windows":
            os.setpgrp()

        exec_cmd = _locate_executable(self.name)
        if testing:
            exec_cmd.append("--testing")
        # logger.debug("Running: {}".format(exec_cmd))

        # There is a very good reason stdout and stderr is not PIPE here
        # See: https://github.com/ActivityWatch/aw-server/issues/27
        self._process = subprocess.Popen(exec_cmd, universal_newlines=True)

        # Should be True if module is supposed to be running, else False
        self.started = True

    def stop(self) -> None:
        """
        Stops a module, and waits until it terminates.
        """
        # TODO: What if a module doesn't stop? Add timeout to p.wait() and then do a p.kill() if timeout is hit
        if not self.started:
            logger.warning("Tried to stop module {}, but it hasn't been started".format(self.name))
            return
        elif not self.is_alive():
            logger.warning("Tried to stop module {}, but it wasn't running".format(self.name))
        else:
            logger.debug("Stopping module {}".format(self.name))
            self._process.terminate()
            logger.debug("Waiting for module {} to shut down".format(self.name))
            self._process.wait()
            logger.info("Stopped module {}".format(self.name))

        assert not self.is_alive()
        self._last_process = self._process
        self._process = None
        self.started = False

    def toggle(self, testing: bool = False) -> None:
        if self.started:
            self.stop()
        else:
            self.start(testing=testing)

    def is_alive(self) -> bool:
        if self._process is None:
            return False

        self._process.poll()
        # If returncode is none after p.poll(), module is still running
        return True if self._process.returncode is None else False

    def stderr(self) -> str:
        """Useful if you want to retrieve logs written to stderr"""
        if self.is_alive():
            return "Can't fetch output while running"
        if not self._process and not self._last_process:
            return "Module not started, no output available"

        # Trying to read stderr or a running process causes hang
        if self.started and not self.is_alive():
            print("Reading active process stderr...")
            self._log += self._process.stderr.read()
        elif self._last_process:
            print("Reading last process stderr...")
            self._log += self._last_process.stderr.read()
        else:
            self._log += "\n\nReading the output of a currently running module is currently broken, sorry."

        return self._log


# TODO: Fetch these from somewhere appropriate (auto detect or a config file)
#       Save to config wether they should autostart or not.
_possible_modules = [
    "aw-server",
    "aw-watcher-afk",
    "aw-watcher-window",
    # "aw-watcher-spotify",
    # "aw-watcher-network"
]

# TODO: Filter away all modules not available on system
modules = {name: Module(name) for name in _possible_modules}


def get_unexpected_stops():
    return list(filter(lambda x: x.started and not x.is_alive(), modules.values()))


if __name__ == "__main__":
    for module in modules.values():
        module.start()
        sleep(2)
        assert module.is_alive()
        module.stop()