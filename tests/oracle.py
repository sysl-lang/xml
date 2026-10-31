"""The oracle: a document as Python's expat reads it, one line per event.

    python3 -I tests/oracle.py <file>

prints the same canonical dump `dump` in `sh/sysl/xml/oracle_tests.sysl` makes from a parsed
`Document`, so the two can be compared line for line:

    S {uri}local          a start tag; `S local` where the element is in no namespace
    N prefix uri          a namespace declaration on it (`N  uri` for the default)
    A {uri}local value    an attribute, in document order
    T text                character data, CDATA merged in -- adjacent runs are one line
    C text                a comment
    P target data         a processing instruction
    E {uri}local          an end tag

Text is escaped so that a line is a line: backslash, newline, carriage return and tab are written
`\\\\`, `\\n`, `\\r` and `\\t`. Or, if expat refuses the document, the single line `ERROR`.
"""

import sys
import xml.parsers.expat


def esc(s):
    return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


def name(n):
    if " " in n:
        uri, local = n.split(" ", 1)
        return "{" + uri + "}" + local
    return n


def main(file):
    out = []
    text = []
    decls = []

    def flush():
        if text:
            out.append("T " + esc("".join(text)))
            text.clear()

    def start(n, attrs):
        flush()
        out.append("S " + name(n))
        for p, u in decls:
            out.append("N " + (p or "") + " " + esc(u or ""))
        decls.clear()
        for i in range(0, len(attrs), 2):
            out.append("A " + name(attrs[i]) + " " + esc(attrs[i + 1]))

    def end(n):
        flush()
        out.append("E " + name(n))

    # What is inside a DOCTYPE is not part of the document this package hands back -- a comment or a
    # processing instruction in an internal subset belongs to the DTD -- so expat's reports of them
    # are dropped here, the way the reader drops them.
    in_dtd = [False]

    def comment(t):
        if in_dtd[0]:
            return
        flush()
        out.append("C " + esc(t))

    def pi(t, d):
        if in_dtd[0]:
            return
        flush()
        out.append("P " + t + " " + esc(d))

    p = xml.parsers.expat.ParserCreate(namespace_separator=" ")
    p.ordered_attributes = True
    p.buffer_text = False
    p.StartElementHandler = start
    p.EndElementHandler = end
    p.CharacterDataHandler = text.append
    p.CommentHandler = comment
    p.ProcessingInstructionHandler = pi
    p.StartNamespaceDeclHandler = lambda pre, uri: decls.append((pre, uri))
    p.StartDoctypeDeclHandler = lambda *a: in_dtd.__setitem__(0, True)
    p.EndDoctypeDeclHandler = lambda: in_dtd.__setitem__(0, False)

    with open(file, "rb") as f:
        data = f.read()
    try:
        p.Parse(data, True)
    except xml.parsers.expat.ExpatError:
        print("ERROR")
        return
    flush()
    sys.stdout.buffer.write("".join(line + "\n" for line in out).encode("utf-8"))


main(sys.argv[1])
