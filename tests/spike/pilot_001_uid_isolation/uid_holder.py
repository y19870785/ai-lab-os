"""Protected process holding the capability FD (client end) without using it.

The capability is a pre-connected anonymous socketpair end mapped to FD 198.
In the Option A model this process is the signing service that must run under
a dedicated UID so its capability cannot be stolen via pidfd_getfd.
"""

from __future__ import annotations

import os
import sys
import time

CAPABILITY_FD = 198


def main() -> int:
    try:
        os.fstat(CAPABILITY_FD)
    except OSError:
        print("capability fd missing", file=sys.stderr)
        return 2
    time.sleep(30)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
