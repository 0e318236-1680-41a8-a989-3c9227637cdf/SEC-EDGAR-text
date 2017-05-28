"""
    secedgartext: extract text from SEC corporate filings
    Copyright (C) 2017  Alexander Ions

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import re
import time
from statistics import median
from bs4 import BeautifulSoup, NavigableString, Tag, Comment

from utils import logger
from document import Document


class HtmlDocument(Document):
    soup = None
    plaintext = None

    def __init__(self, *args, **kwargs):
        super(HtmlDocument, self).__init__(*args, **kwargs)

    def document_type(self):
        return "html"

    def prepare_text(self):
        """Strip unwanted text and parse the HTML.

        Remove some unhelpful text from the HTML, and parse the HTML,
        initialising the 'soup' attribute
        """
        html_text = self.doc_text
        # remove whitespace sometimes found inside tags,
        # which breaks the parser
        html_text = re.sub('<\s', '<', html_text)
        # remove small-caps formatting tags which can confuse later analysis
        html_text = re.sub('(<small>|</small>)', '', html_text,
                           flags=re.IGNORECASE)
        # for simplistic no-tags HTML documents (example: T 10K 20031231),
        # make sure the section headers get treated as new blocks.
        html_text = re.sub(r'(\nITEM\s{1,10}[1-9])', r'<br>\1', html_text,
                           flags=re.IGNORECASE)

        # we prefer to use lxml parser for speed, this requires seprate
        # installation. Straightforward on Linux, somewhat tricky on Windows.
        # http://stackoverflow.com/questions/29440482/how-to-install-lxml-on-windows
        # ...note install the 32-bit version for Intel 64-bit?
        start_time = time.clock()
        try:
            soup = BeautifulSoup(html_text, 'lxml')
        except:
            soup = BeautifulSoup(html_text, 'html.parser')      # default parser
        parsing_time_elapsed = time.clock() - start_time
        logger.debug('parsing time: ' + '% 3.2f' %
                     (parsing_time_elapsed) + 's; ' + "{:,}".
                     format(len(html_text)) + ' characters; ' + "{:,}".
                     format(len(soup.find_all())) + ' HTML elements')

        # for some old, simplistic documents lacking a proper HTML tree,
        # put in <br> tags artificially to help with parsing paragraphs, ensures
        # that section headers get properly identified
        if len(html_text) / len(soup.find_all()) > 500:
            html_text = re.sub(r'\n\n', r'<br>', html_text,
                               flags=re.IGNORECASE)
            soup = BeautifulSoup(html_text, 'html.parser')

        # Remove numeric tables from soup
        tables_generator = (s for s in soup.find_all('table') if
                            should_remove_table(s))
        # debug: save the extracted tables to a text file
        # tables_debug_file = open(r'tables_deleted.txt', 'wt', encoding='latin1')
        for s in tables_generator:
            s.replace_with('[DATA_TABLE_REMOVED]')
            # tables_debug_file.write('#' * 80 + '\n')
            # tables_debug_file.write('\n'.join([x for x in s.text.splitlines()
            # if x.strip()]).encode('latin-1','replace').decode('latin-1'))
        # tables_debug_file.close()
        self.soup = soup

        # paragraphs_analysis = []
        # p_idx = 0
        # has_href = False
        # has_crossreference = False
        paragraph_string = ''
        document_string = ''
        all_paras = []
        ec = soup.find()
        is_in_a_paragraph = True
        while not (ec is None):
            if is_line_break(ec) or ec.next_element is None:
                # end of a paragraph; insert line-break (double for readability)
                if is_in_a_paragraph:
                    is_in_a_paragraph = False
                    all_paras.append(paragraph_string)
                    document_string = document_string + '\n\n' + paragraph_string
            else:
                # continuation of the current paragraph
                if isinstance(ec, NavigableString) and not \
                        isinstance(ec, Comment):
                    # remove line breaks and other whitespace at the ends,
                    # and in the middle, of the string
                    ecs = re.sub(r'\s+', ' ',
                                 ec.string.strip())
                    if len(ecs) > 0:
                        if not (is_in_a_paragraph):
                            # set up for the start of a new paragraph
                            is_in_a_paragraph = True
                            paragraph_string = ''
                        paragraph_string = paragraph_string + ' ' + ecs
            ec = ec.next_element
        self.plaintext = document_string


    def extract_section(self, search_pairs):
        """

        :param search_pairs:
        :return:
        """
        start_text = 'na'
        end_text = 'na'
        warnings = []
        text_extract = None
        for st_idx, st in enumerate(search_pairs):
            # ungreedy search (note '.*?' regex expression between 'start' and 'end' patterns
            # also using (?:abc|def) for a non-capturing group
            # also an extra pair of parentheses around the whole expression,
            # so that we always return just one object, not a tuple of groups
            # st = super().search_terms_pattern_to_regex()
            # st = Reader.search_terms_pattern_to_regex(st)
            item_search = re.findall(st['start']+'.*?'+ st['end'],
                                     self.plaintext,
                                     re.DOTALL | re.IGNORECASE)
            # item_search = re.findall('(' + st['start']+'.*?'+ st['end']+')',
            #                          self.plaintext,
            #                          re.DOTALL | re.IGNORECASE)
            if item_search:
                longest_text_length = 0
                for s in item_search:
                    if isinstance(s, tuple):
                        # If use of multiple regex groups has caused more
                        # than one match, then s is returned as a tuple ,
                        # so we have to instead take the first (encompassing)
                        # group as our found string
                        s = s[0]
                    if len(s) > longest_text_length:
                        text_extract = s.strip()
                        longest_text_length = len(s)
                # final_text_new = re.sub('^\n*', '', final_text_new)
                final_text_lines = text_extract.split('\n')
                start_text = final_text_lines[0]
                end_text = final_text_lines[-1]
                break
        extraction_method = 'html_document'
        if not text_extract:
            warnings.append('Extraction did not work for HTML file')
            extraction_method = 'html_document: failed'
        else:
            text_extract = re.sub('\n\s{,5}Table of Contents\n', '',
                                  text_extract, flags=re.IGNORECASE)

        return text_extract, extraction_method, start_text, end_text, warnings




def should_remove_table(html):
    """Decide whether <table> html contains a mostly-numeric table.

    Identify text in table element 'html' which cannot (realistically) be
    subject to downstream text analysis. Note there is a risk that we
    inadvertently remove any Section headings that are inside <table> elements
    We reduce this risk by only seeking takes with more than 5 (nonblank)
    elements, the median length of which is fewer than 30 characters
    """
    char_counts = []
    if html.stripped_strings:
        for t in html.stripped_strings:
            if len(t) > 0:
                char_counts.append(len(t))
        return len(char_counts) > 5 and median(char_counts) < 30
    else:
        logger.error("the should_remove_table function is broken")



def is_line_break(e):
    """Is e likely to function as a line break when document is rendered?

    we are including 'HTML block-level elements' here. Note <p> ('paragraph')
    and other tags may not necessarily force the appearance of a 'line break',
    on the page if they are enclosed inside other elements, notably a
    table cell
    """


    is_block_tag = e.name != None and e.name in ['p', 'div', 'br', 'hr', 'tr',
                                                 'table', 'form', 'h1', 'h2',
                                                 'h3', 'h4', 'h5', 'h6']
    # handle block tags inside tables: if the apparent block formatting is
    # enclosed in a table cell <td> tags, and if there are no other block
    # elements within the <td> cell (it's a singleton, then it will not
    # necessarily appear on a new line so we don't treat it as a line break
    if is_block_tag and e.parent.name == 'td':
        if len(e.parent.findChildren(name=e.name)) == 1:
            is_block_tag = False
    # inspect the style attribute of element e (if any) to see if it has
    # block style, which will appear as a line break in the document
    if hasattr(e, 'attrs') and 'style' in e.attrs:
        is_block_style = re.search('margin-(top|bottom)', e['style'])
    else:
        is_block_style = False
    return is_block_tag or is_block_style

