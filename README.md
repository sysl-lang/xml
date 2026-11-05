# xml

XML 1.0 for [sysl](https://github.com/sysl-lang/sysl): read as a tree or as a stream of events, and
written with the escaping done. Namespaces are resolved as it reads.

It is pure sysl. The cursor, the byte tables and the numeric-reference digits come from
[sysl-lang/parsing](https://github.com/sysl-lang/parsing); everything XML-shaped is here.

```sysl
import sh.sysl.xml.*

val book = parse_bytes(entry_bytes)?                     // a Document, or an XmlError with line:col

book.root.child("sheets") match
    Some(sheets) ->
        for sheet in sheets.elements_named("sheet")
            print(sheet.attr("name"), sheet.attr_ns(REL, "id"))   // `r:id`, whatever the prefix
    None -> ()

var r = reader(sheet_xml)                                // a 50 MB sheet need not become a tree

loop
    r.next()? match
        Start(name, _, _) -> if name.local == "c" then count += 1
        Text(t) -> total += parse_long(t)?
        Eof -> break
        _ -> ()

var w = writer()

w.declaration(Some(true))
w.open("worksheet")
w.ns("", MAIN)
w.element("v", "42")
w.close()

val text = w.finish()?                                   // the same bytes for the same calls
```

## Using it

```hocon
dependencies {
  xml { git = "github.com/sysl-lang/xml", version = "0.1.1" }
}
```

The module is **`sh.sysl.xml`**.

## The surface

```sysl
parse(text: string) -> Result[&Document, XmlError]
parse_bytes(bytes: []const u8) -> Result[&Document, XmlError]     // checked as UTF-8, a BOM dropped
text_of(bytes: []const u8) -> Result[string, XmlError]            // that check alone, for `reader`

struct Document
    version, encoding: string        // as the declaration said, or ""
    standalone: Option[bool]
    doctype: string                  // the name a DOCTYPE gave, or ""
    children: Buf[Node]              // comments and PIs around the root, and the root, in order
    root: &Element
    to_xml(self) -> Result[string, WriteError]   // a DOCTYPE is not written

struct Element                       // derives Eq: two are equal when they are the same tree
    name: Name
    attrs: Buf[Attr]                 // document order; namespace declarations are NOT here
    decls: Buf[NsDecl]               // the xmlns and xmlns:p written on this element
    children: Buf[Node]
    local -> string
    attr(self, local: string) -> Option[string]                   // by local name, any namespace
    attr_ns(self, ns: string, local: string) -> Option[string]    // "" is no namespace
    child(self, local: string) -> Option[&Element]
    child_ns(self, ns: string, local: string) -> Option[&Element]
    elements(self) -> Buf[&Element]
    elements_named(self, local: string) -> Buf[&Element]
    text(self) -> string             // text and CDATA, all the way down
    to_xml(self) -> Result[string, WriteError]   // declares the prefixes it inherited

enum Node      Elem(&Element) | Text(string) | CData(string) | Comment(string) | Pi(target, data)
struct Name    qname, prefix, local, ns: string;  is(self, ns, local) -> bool
struct Attr    name: Name, value: string
struct NsDecl  prefix: string, uri: string            // prefix "" is the default namespace
struct XmlError  line, col, offset: usize, message: string   // displays as `line:col: message`

reader(text: string) -> Reader
struct Reader
    next(*self) -> Result[Event, XmlError]
    depth -> usize
    version, encoding: string, standalone: Option[bool]   // read before the first event

enum Event
    Start(name: Name, attrs: Buf[Attr], decls: Buf[NsDecl])   // <e/> is a Start and then an End
    End(name: Name)
    Text(text: string) | CData(text: string) | Comment(text: string) | Pi(target, data)
    Doctype(name: string)
    Eof                                                       // asked again, answers it again

writer() -> XmlWriter
struct XmlWriter
    declaration(*self, standalone: Option[bool] = None)       // <?xml version="1.0" encoding="UTF-8"?>
    open(*self, name: string)
    attr(*self, name: string, value: string)
    ns(*self, prefix: string, uri: string)
    text(*self, text: string)
    cdata(*self, text: string)                                // ]]> is split across two sections
    comment(*self, text: string)
    pi(*self, target: string, data: string)
    close(*self)                                              // `/>` if nothing went inside
    element(*self, name: string, text: string)                // open, text, close
    finish(self) -> Result[string, WriteError]                // the first mistake, if one was made

val XML_NS, XMLNS_NS
```

**What a reader hands back is what XML 1.0 says the document contains.** Line ends are `\n`, CRLF
and a lone CR alike. An attribute value has each tab, newline and carriage return turned into a space
and its references replaced, so `&#10;` is how a value keeps a newline. Text is a slice of the input
wherever nothing in it was replaced, so a sheet of numbers is read without copying them.

**Whitespace between elements is text**, because XML says so; a consumer that does not want it skips
it. Whitespace outside the root element is not an event at all.

**Every error says where it is and what was expected**: `3:1: `</a>` does not close `<b>`, opened at
2:3`. The column counts characters, not bytes. The reader and the tree refuse a document with the same
error at the same place, since the tree is built from the reader's events.

**The writer holds its mistakes rather than stopping on them** — a name that is not one, an attribute
after content, `--` in a comment, a character XML cannot carry — and `finish` answers the first. It
escapes `&`, `<` and `>` everywhere, `"`, tab, newline and carriage return in attributes, and carriage
return in text, so what it writes reads back as exactly the strings it was given. Nothing is indented
or reordered.

## Checked

- **Well-formedness**: one root, tags matched and closed, no duplicate attribute (by name, and by
  namespace and local name), no `<` in an attribute value, no `&` that does not begin a reference, no
  `]]>` in text, no `--` in a comment, names made of name characters (XML 1.0 fifth edition, above
  ASCII too), only characters XML allows, the declaration only first, a DOCTYPE only before the root.
- **Namespaces in XML 1.0**: one colon at most and not at either end, every prefix declared, `xml`
  predefined, `xmlns` and the two reserved URIs undeclarable, `xmlns:p=""` refused.
- **References**: the five predefined entities; decimal and hex character references, encoded as
  UTF-8, refused when they name what is not a `Char` — `&#0;`, a surrogate, `&#xFFFE;`, past
  `&#x10FFFF;`.

## Not here, on purpose

- **DTDs.** A DOCTYPE's shape is checked — its external identifier, and that an internal subset is
  declarations, comments, processing instructions and parameter-entity references — and nothing in it
  is acted on. So there is **no validation, no attribute defaults, and no entities beyond the five
  predefined ones**: a reference to an entity a DOCTYPE declares is an error saying exactly that. The
  inside of a declaration is stepped over, not parsed, so a malformed content model goes unreported.
  OOXML, SVG, RSS and nearly everything else written today declares nothing in a DOCTYPE.
- **External entities are never fetched**, and nothing here opens a file or a socket. A document
  cannot make this package read anything a caller did not hand it.
- **Encodings other than UTF-8.** The input is a `string`, which is UTF-8 by construction; a
  declaration naming another encoding (US-ASCII aside, being part of UTF-8) is refused rather than
  misread. UTF-16 is the one a conforming processor must also take, and it is absent.
- **XML 1.1**'s wider rules. A `version="1.1"` is read with 1.0's.
- **Automatic namespace prefixes in the writer.** `ns` writes the declaration it is given, where it is
  given; choosing prefixes is the caller's business.

## Tests

`sysl test .` runs the suite. It needs `python3` on the path for the oracle, and `curl`, `shasum`
and `tar` and the network the first time, to fetch the W3C suite — whose licence allows it to be
passed on only as the original archive, so it is fetched from w3.org and checked against its SHA-256
rather than kept here. It is checked against:

- **Python's expat**, on fixtures that include the five parts of an `.xlsx` as Excel writes them
  (`[Content_Types].xml`, `workbook.xml`, a worksheet, shared strings, styles) and three written for
  the corners: names, values and namespaces are compared line by line, through both the tree and the
  events.
- **The W3C XML conformance suite** (James Clark's `xmltest`, `xmlts20130923`): 181 standalone
  not-well-formed cases, of which the 132 outside DTD declarations are refused and the 49 inside them
  are named as accepted; and 53 standalone valid cases read and compared byte for byte with the
  suite's canonical output.
- **Round trips**: every fixture written out from its tree and read back as the same document, and
  written a second time as the same bytes.
