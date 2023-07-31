# unredact.py

This repo contains a script to remove weak redactions from PDF files. Note that
this script will not uncover anything more than can be revealed by copying and
pasting redacted content(\*). However, it operates directly on the original
redacted PDF file and produces an unredacted version maintaining as much of the
original formatting as possible in a new unredacted PDF.

[\*] In addition to black rectangles that Adobe tools produce, `unredact.py`
also removes all black images that are sometimes placed over text and images.
I'm not sure that copy-paste works in that case.

Usage:
```
    $ ./unredact <redacted-pdf-file>
```

Executing the script will produce a new PDF file named the same as the orginal
docuemtn but with '-unredacted' appended to the end of the name.

## What is redaction?
Redaction is a form of censoring sensitive content from documents. It's
generally used in legal or government contexts where most or some of a document
can be released to the public or other parties but some of the information is
excluded from the release.

You'll recognize redactions as the thick black boxes that strike through lines
of text in certain documents. Originally redactions were actually done with a
thick black marker overwriting the text on paper. With digital documents,
redactions are generally handled by special software that can black out the
excluded information in a similar fashion. When done properly, redactions
cannot be reversed. But in some circumstances redacted text can be revealed by
simply copying the text on a page, including the text that is blacked out and
pasting it into another document.

These poorly done or weak redactions are [more
common](https://www.americanbar.org/groups/judicial/publications/judges_journal/2019/spring/embarrassing-redaction-failures/)
than you might think and have been the source of valuable information for 
investigative journalists, for example. Freedom of Information requests seeking
documents from government agencies often result in documents with some of the 
content redacted.

## About `unredact.py`

The script depends on the `pdfminer.six`, `reportlab` and `PIL` modules. So
those must be installed before running it. It's meant to be as simple as
possible and, so far, runs without any external dependencies or configuration
files. This may change in the future as more and more complicated features are
added.

The script is in a very early stage. While it has been run over many PDF files,
caution: it has been run against exactly one weakly redacted document. If you
have examples of redacted documents, I would be very happy to try the program
on them, so please let me know.

Also be aware of the following issues:

* The code is not fully commented and documented.
* There are many aspects of PDF that are not handled, e.g. slanted text or
other special layout features. Also, there are many PDF elements that
are not yet handled.
* Font handling needs improvement. Currently, there is font mapping at the
beginning of the script. This solution is not scalable, and I believe the
document's fonts are embedded within the PDF, so there should be a way to 
get them out.
* Some images that have a white background in the original PDF end up with a
black background in the unredacted version. Apparently PDF doesn't have
transparency in images, so that's accomplished by a second image that creates
the background. The code should figure out and fix the transparency when it
exists.
* Some unredacted files are much bigger than the original file.

