"""
Tools to extract information from biller pdfs
"""
import glob
import math
import os
import re

from dateutil.parser import parse as parse_date
import pandas as pd
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFTextExtractionNotAllowed
from pdfminer.layout import LAParams, LTTextBox, LTTextLine
from pdfminer.converter import PDFPageAggregator


class LocalPDFPageAggregator(PDFPageAggregator):
    """Override undefined char handling."""
    def handle_undefined_char(self, font, cid):
        return chr(cid)


def pdf_page_layouts(fobj):
    """
        Deal with the actual extraction of layout objects from the PDF.
    """
    # Create parser object to parse the pdf content
    parser = PDFParser(fobj)

    # Store the parsed content in PDFDocument object
    document = PDFDocument(parser, "")

    # Check if document is extractable, if not abort
    if not document.is_extractable:
        raise PDFTextExtractionNotAllowed

    # Create PDFResourceManager object that stores shared resources such as
    # fonts or images
    rsrcmgr = PDFResourceManager()

    # set parameters for analysis
    laparams = LAParams()

    # Extract the decive to page aggregator to get LT object elements
    device = LocalPDFPageAggregator(rsrcmgr, laparams=laparams)

    # Create interpreter object to process page content from PDFDocument
    # Interpreter needs to be connected to resource manager for shared
    # resources and device
    interpreter = PDFPageInterpreter(rsrcmgr, device)

    # Ok now that we have everything to process a pdf document, lets process it page by page
    for page in PDFPage.create_pages(document):
        # As the interpreter processes the page stored in PDFDocument object
        interpreter.process_page(page)
        # The device renders the layout from interpreter
        yield device.get_result()


def get_matching_objects(pattern, layout):
    """
        Iterate over all object in layout and find wanted ones.
    """
    matched = []
    for lt_obj in layout:
        # We only want to inspect objects that contain text.
        if isinstance(lt_obj, LTTextBox) or isinstance(lt_obj, LTTextLine):
            # Try and match against the given regexp pattern
            found = re.findall(pattern, lt_obj.get_text().lower())
            if found:
                centroid = (
                    (lt_obj.bbox[2] + lt_obj.bbox[0]) / 2,
                    (lt_obj.bbox[3] + lt_obj.bbox[1]) / 2,
                )
                matched.append((centroid, lt_obj, found))
    return matched


def distance(pta, ptb):
    """Determine distance between two points (as tuples)."""
    return math.sqrt(
        (pta[0] - ptb[0]) ** 2 +
        (pta[1] - ptb[1]) ** 2
    )


def find_field_value_near_text(layout, pattern_text, pattern_val, processor):
    """
        Iterate over the layout looking for field values.

        It does this by finding the text node that best matches
        ``pattern_text``. We then find the geometrically closest node to that
        which matches ``pattern_val``. The first sub-pattern match is then
        extracted and the result of calling ``processor(value)`` is retured.

        If no match is found then None is returned.

        The aim here is pass a regular expression that matches a value label
        as ``pattern_text`` and one the matches the wanted value as
        ``pattern_val``.
    """
    # find matches for the label text
    due_centres = get_matching_objects(pattern_text, layout)
    if not due_centres:
        return
    # Choose centroid of shortest string match
    due_centre = sorted(due_centres, key=lambda val: len(val[1].get_text()))[0][0]

    # find matches for the value pattern.
    due_values = get_matching_objects(pattern_val, layout)
    due_value_distances = [(distance(due_centre, val[0]), val[1], val[2]) for val in due_values]
    if not due_value_distances:
        return
    due_value_distances = sorted(due_value_distances, key=lambda v: v[0])[0]
    return processor(due_value_distances[2][0].strip())


def extract_data(fobj, values_config):
    """
        Extract text values from a PDF file.
    """
    results = {}
    for layout in pdf_page_layouts(fobj):
        # Iterate over each configured pattern.
        for ident, pattern_text, pattern_val, dtype in values_config:
            if ident in results:
                continue
            field_value = find_field_value_near_text(
                layout, pattern_text, pattern_val, dtype
            )
            if field_value:
                results[ident] = field_value
    return results


def main():
    """Entrypoint. Iterate over files."""
    allres = []
    values_config = [
        ('amount', r'(invoice number)', r'\$.*?([0-9\.-]+)', float),
        ('amount', r'\d\d/\d\d/\d\d\d\d\n\$[\d\.]+', r'\$.*?([0-9\.-]+)', float),
        ('amount', r'((total\s+)?amount\sdue)|(new charges)', r'\$.*?([0-9\.-]+)', float),
        ('due_date', r'due( date)?', r'(\d\d [a-z]+ \d\d(?:\d\d)?)', parse_date),
        ('due_date', r'\d\d/\d\d/\d\d\d\d\n\$[\d\.]+', r'(\d\d/\d\d/\d\d\d\d)', parse_date),
    ]
    for fname in (
            glob.glob('/Users/dkent/Documents/Finance/Bills/Rates*.pdf') +
            glob.glob('/Users/dkent/Documents/Finance/Bills/Water*.pdf') +
            glob.glob('/Users/dkent/Documents/Finance/Bills/Gas*.pdf') +
            glob.glob('/Users/dkent/Documents/Finance/Bills/Electricity*.pdf')
    ):
        res = extract_data(fname, values_config)
        res['bill'] = os.path.basename(fname).split('_')[0].lower()
        allres.append(res)
    allres = pd.DataFrame(allres)
    allres.set_index(['bill', 'due_date'], inplace=True)
    allres = allres.amount.dropna()
    print(allres)

if __name__ == '__main__':
    main()