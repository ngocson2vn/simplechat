from __future__ import absolute_import

import sys
PY3 = sys.version>'3'

if PY3: # pragma: no cover
    long = int
    basestring = str
    unichr = chr
    raw_input = input
    class unicode(str):
        def __init__(self, string, encoding, errors):
            str.__init__(self, string)
    def as_bytes(s): return s if isinstance(s,bytes) else s.encode('utf8')
    def as_string(s): return s if isinstance(s,str) else s.decode('utf8')
    from functools import reduce

else: # pragma: no cover
    long = long
    raw_input = raw_input
    unicode = unicode
    basestring = basestring
    def as_bytes(s): return s if isinstance(s, str) else s.encode('utf-8')
    def as_string(s): return s if isinstance(s, unicode) else s.decode('utf-8')
    reduce = reduce