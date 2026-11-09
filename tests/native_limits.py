"""Apply a real allocation limit after an owned native probe initializes."""
import os
from pathlib import Path
import resource
import subprocess
import time


def allocation_probe(arguments, ready, extra_bytes=32 * 1024 * 1024):
    ready = Path(ready)
    ready.unlink(missing_ok=True)
    process = subprocess.Popen(arguments, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 15
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.002)
        assert ready.exists() and process.poll() is None, 'Native allocation probe did not initialize'
        # Shared GTK/GIO libraries count toward virtual address space. Budget
        # actual additional allocations rather than assuming a static image size.
        with open(f'/proc/{process.pid}/statm') as stream:
            baseline = int(stream.read(256).split()[0]) * os.sysconf('SC_PAGE_SIZE')
        ceiling = baseline + extra_bytes
        for bound in resource.prlimit(process.pid, resource.RLIMIT_AS):
            if bound != resource.RLIM_INFINITY:
                ceiling = min(ceiling, bound)
        assert ceiling > baseline, 'Inherited allocation limit leaves no native test budget'
        resource.prlimit(process.pid, resource.RLIMIT_AS, (ceiling, ceiling))
        output, error = process.communicate('g', timeout=60)
        return subprocess.CompletedProcess(arguments, process.returncode, output, error), ceiling
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream:
                stream.close()
