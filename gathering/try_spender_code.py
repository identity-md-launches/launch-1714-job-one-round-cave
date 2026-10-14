#!/usr/bin/env python3
"""Run Line 2's read-only example without urllib consulting proxy environment."""
import runpy
import urllib.request

# The original tool's default urlopen builds an environment-aware opener.
# Supply a direct, credential-free transport without changing any line file.
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
urllib.request.urlopen = opener.open
runpy.run_path('line-2/tools/spender-code/spender_code.py', run_name='__main__')
