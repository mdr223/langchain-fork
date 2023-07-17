import asyncio
import sys


def print_msg(*largs):
    print("[agent]>>", *largs)

def print_err(*largs):
    print("[agent]!! error:", *largs)

def print_to_stderr(*largs):
    print(*largs, file=sys.stderr)

def input_msg(msg):
    return input("[agent]?? " + msg + " ")

def prompt_proceed(msg="proceed (y/[n])?"):
    proceed = input_msg(msg)

    if proceed != "y":
        print_err("aborting.")
        sys.exit(1)


class AsyncShellException(Exception):
    def __init__(self, cmd, retcode, stdout, stderr):
        super().__init__()
        self.cmd = cmd
        self.retcode = retcode
        self.stdout = stdout
        self.stderr = stderr

class AsyncShellSuccess(AsyncShellException):
    pass

class AsyncShellFailure(AsyncShellException):
    pass



# run a shell command async
async def run_sh_async(
        cmd,
        print_cmd=True,
        print_stdout=True,
        print_stderr=True,
        silent=False,
        exception_on_failure=False,
        exception_on_success=False,
):

    if not silent and print_cmd:
        print_msg("running:\n  >", cmd)

    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()

    retcode = proc.returncode
    stdout = stdout.decode()
    stderr = stderr.decode()

    if not silent and print_stdout and stdout != "":
        print(stdout)

    if not silent and print_stderr and stderr != "":
        print_to_stderr(stderr)

    if exception_on_failure and retcode != 0:
        raise AsyncShellFailure(cmd, retcode, stdout, stderr)

    if exception_on_success and retcode == 0:
        raise AsyncShellSuccess(cmd, retcode, stdout, stderr)

    return retcode, stdout, stderr


# a lazy solution that effectively turns `run_sh_async` to synchronous ver.
def run_sh(cmd, **kwargs):
    return asyncio.run(run_sh_async(cmd, **kwargs))


# wrapping `run_sh_async` coroutine into a task.
def run_sh_task(cmd, **kwargs):
    return asyncio.create_task(run_sh_async(cmd, **kwargs))

