# unredact

A tool to remove weak redactions from PDF files. When a PDF is poorly redacted
by drawing a (normally black) rectangle over text (rather than permanently
removing the underlying content), `unredact` detects those rectangles and
removes them revealing the text underneath. By default, `unredact` also
highlights the text that has been revealed to indicate the text that had
been previously redacted.

There are many programs that can detect and extract text that has been redacted
in this way. `unredact` has the added feature of revealing text within the 
PDF file itself. In other words, after running `unredact`, you will have a
nearly identical PDF file, but with the redacted text highlighted instead of 
blacked out.

---

## Requirements

- **Python 3.10 or higher** — check by running `python --version` in your 
  terminal.
- **pikepdf** — the only external dependency

---

## Getting the source code

**Option A — Git:**

You can check out the code directly from GitHub:

```bash
git clone https://github.com/your-username/unredact.git
cd unredact
```

**Option B — ZIP download:**

On the GitHub page, click the green **Code** button, then **Download ZIP**.
Unzip the file noting the path to the resulting folder.

---

## Installing dependencies

`unredact` has one external dependency:
[pikepdf](https://pikepdf.readthedocs.io/). You can install it using your
favorite Python package manager.

### pip (standard)

If you're not sure which package manager to use, this is the most
straightforward option. It's included with Python 3.10+. On a command line,
change your current working directory to where the `unredact` code is located.
Then type:

```bash
pip install -e .
```

The `-e` flag installs in "editable" mode, so if you update `unredact`, changes
to the source code will take effect immediately without reinstalling.

### Poetry

```bash
poetry install
```

Poetry will read `pyproject.toml` and install `pikepdf` automatically.

### uv

```bash
uv sync
```

### Conda / Anaconda

`pikepdf` is available on the `conda-forge` channel rather than the default 
Conda channel. Install it with:

```bash
conda install -c conda-forge pikepdf
```

Then install `unredact` itself:

```bash
pip install -e .
```

---

## Usage

Once installed, run `unredact` from a terminal. You can specify one or more
PDF files to be processed. To process a single file, simply type:

```bash
unredact input.pdf
```

which will produce an unredacted PDF file called `input-unredacted.pdf` in the 
current directory.

The general syntax is

```bash
unredact [-h] [-v] [-o OUTPUT_DIR] pdf_file [pdf_file ...]
```

You can specify one or more files to be processed and optionally an output 
directory where the unredacted files should be written. An example with
multiple files written to an output directory:

```bash
unredact  -o unredacted_pdf_files input1.pdf input2.pdf input3.pdf
```

After running this example you should see the three files 
`input1-unredacted.pdf`, `input2-unredacted.pdf`, and `input3-unredacted.pdf`
in the `unredacted_pdf_files/` directory.

---

## How it works

`unredact` reads each page of the PDF and inspects the drawing instructions.
When it finds a rectangle that looks like a redaction, it replaces the solid
rectangle with a transparent highlight so the underlying content shows through.
All other content — text, images, fonts, layout — is left completely unchanged.

> **Important:** this tool only works on PDFs where the original text is still 
present in the file and has simply been covered up. If a PDF was redacted by 
scanning a printed copy, or by permanently deleting the content, `unredact` 
cannot recover that information.

---

## Using unredact as a library

`unredact` can be imported and used directly in your own Python code, which is 
useful if you want to integrate redaction removal into a larger workflow---for 
example, processing uploaded files, a pipeline, or an in-memory source rather 
than the command line.

### Installation

Add `unredact` as a dependency in your project the same way you would any 
other package. If your project uses pip:

```bash
pip install git+https://github.com/your-username/unredact.git
```

Or add it to your `pyproject.toml` dependencies:

```toml
dependencies = [
    "unredact @ git+https://github.com/your-username/unredact.git"
]
```

### Basic usage

The main class is `UnredactPdf`. The typical pattern is to open a PDF, call 
`process_page` on each page, then save the result:

```python
from unredact.core import UnredactPdf

# Open from a file path
doc = UnredactPdf.from_path("redacted.pdf")

# Process every page
for page in doc.pages:
    doc.process_page(page)

# Save to a file path
doc.save("unredacted.pdf")
```

### Working with file-like objects

If you're working with PDFs in memory — for example, from a web framework or a 
pipeline that hands you a stream — you can open a pikepdf object directly and 
save to a `BytesIO` buffer rather than a file on disk:

```python
import io
import pikepdf
from unredact.core import UnredactPdf

# Open from a file-like object (e.g. a BytesIO buffer or an uploaded file)
pdf_bytes = io.BytesIO(uploaded_file_content)
pdf_obj = pikepdf.open(pdf_bytes)
doc = UnredactPdf(pdf_obj)

for page in doc.pages:
    doc.process_page(page)

# Save to a buffer instead of a file
output_buffer = io.BytesIO()
doc.save(output_buffer)
output_buffer.seek(0)
# output_buffer.read() now contains the processed PDF bytes
```

### Processing a subset of pages

If you only want to process specific pages rather than the whole document, 
iterate over the pages you need. Pages are zero-indexed:

```python
doc = UnredactPdf.from_path("redacted.pdf")

# Process only the first three pages
for page in doc.pages[:3]:
    doc.process_page(page)

doc.save("partially_unredacted.pdf")
```

### API reference

#### `UnredactPdf(pdf_obj)`

Constructor. Accepts an open `pikepdf.Pdf` object directly. Use this when you 
already have a pikepdf object, or are working with in-memory PDF data.

#### `UnredactPdf.from_path(file_path)`

Class method. Opens a PDF from a file path and returns an `UnredactPdf` 
instance. Raises `FileNotFoundError` if the path does not exist.

#### `doc.process_page(page)`

Processes a single page in place, replacing any detected redaction rectangles 
with semi-transparent highlights. The page object is modified directly with no 
return value.

#### `doc.save(target)`

Saves the processed PDF. `target` can be either a file path string or any 
writable file-like object (such as `io.BytesIO`).

#### `doc.pages`

A reference to the underlying `pikepdf` page list. Supports indexing and 
slicing, so you can iterate over all pages or a subset.

---

## Troubleshooting

**The output PDF looks the same as the input**
The redactions in your file may not be simple filled rectangles. They may be 
true redactions where the content has been permanently removed. `unredact` can 
only recover content that is still present in the file.

**A `FileNotFoundError` or similar appears when running the command**
Double-check the path to your input file. If the path contains spaces, wrap it 
in quotes:

```bash
unredact "~/Documents/my redacted file.pdf" 
```

---

## Running the tests

First install pytest (substitute the install command for your package manager 
if not using pip):

```bash
pip install pytest
```

Then run:

```bash
python -m pytest tests/ -v
```

---

## License

`unredact` is open source software released under the MIT License. See the 
`LICENSE` file for details.
