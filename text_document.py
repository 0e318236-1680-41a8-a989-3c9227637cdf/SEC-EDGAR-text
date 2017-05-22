"""
[License Boilerplate here: Alex copyright, license etc.]
"""
import re

from utils import logger
from document import Document


class TextDocument(Document):
    def __init__(self, *args, **kwargs):
        super(TextDocument, self).__init__(*args, **kwargs)

    def document_type(self):
        return "txt"

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
            # st = super().search_terms_pattern_to_regex()
            # st = Reader.search_terms_pattern_to_regex(st)
            item_search = re.findall(st['start'] + '.*?' + st['end'],
                                     self.doc_text,
                                     re.DOTALL | re.IGNORECASE)
            if item_search:
                longest_text_length = 0
                for s in item_search:
                    if len(s) > longest_text_length:
                        text_extract = s.strip()
                        longest_text_length = len(s)
                # final_text_new = re.sub('^\n*', '', final_text_new)
                final_text_lines = text_extract.split('\n')
                start_text = final_text_lines[0]
                end_text = final_text_lines[-1]
                break
        extraction_method = 'text_document'
        if text_extract:
            # final_text = '\n'.join(final_text_lines)
            # text_extract = remove_table_lines(final_text)
            text_extract = remove_table_lines(text_extract)
        else:
            warnings.append('Extraction did not work for text file')
            logger.warning('No excerpt produced for text file')
            extraction_method = 'text_document: failed'

        return text_extract, extraction_method, start_text, end_text, warnings

def remove_table_lines(input_text):
    """Replace lines believed to be part of numeric tables with a placeholder.

    :param input_text:
    :return:
    """
    text_lines = []
    table_lines = []
    post_table_lines = []
    is_in_a_table = False
    is_in_a_post_table = False
    for i, line in enumerate(input_text.splitlines(True), 0):
        if is_table_line(line):
            # a table line, possibly not part of an excerpt
            if is_in_a_post_table:
                # table resumes: put the inter-table lines into the table_line list
                table_lines = table_lines + post_table_lines
                post_table_lines = []
                is_in_a_post_table = False
            table_lines.append(line)
            is_in_a_table = True
        else:
            # not a table line
            if is_in_a_table:
                # the first post-table line
                is_in_a_table = False
                is_in_a_post_table = True
                post_table_lines.append(line)
            elif is_in_a_post_table:
                # 2nd and subsequent post-table lines
                if len(post_table_lines) >= 5:
                    # sufficient post-table lines have accumulated now that we revert to standard 'not a post table' mode
                    # Note we append the post-table lines to the text_lines, and we discard the table_lines
                    if len(table_lines) >= 3:
                        text_lines = text_lines + [
                            '\n[DATA_TABLE_REMOVED_' + str(len(table_lines)) + '_LINES]\n\n']
                    else:
                        # very short table, just leave it in the document regardless
                        text_lines = text_lines + table_lines
                    text_lines = text_lines + post_table_lines
                    table_lines = []
                    post_table_lines = []
                    is_in_a_post_table = False
                else:
                    post_table_lines.append(line)
        if not (is_in_a_table) and not (is_in_a_post_table):
            # normal excerpt line: just append it to text_lines
            text_lines.append(line)

    final_text = ''.join(text_lines)
    return final_text


def is_table_line(s):
    """Is text line string s likely to be part of a numeric table?

    gaps between table 'cells' are expected to have three or more whitespaces,
    and table rows are expected to have at least 3 such gaps, i.e. 4 columns

    :param s:
    :return:
    """
    s = s.replace('\t', '    ')
    rs = re.findall('\S\s{3,}', s)  # \S = non-whitespace, \s = whitespace
    r = re.search('(<TABLE>|^\s{10,}[a-zA-z]|(-|=|_){5,})',
                  s)  # check for TABLE quasi-HTML tag, or lots of spaces prior to the first (non-numeric i.e. not just a page number marker) character, or use of lots of punctuation marks as table gridlines
    return len(rs) >= 2 or r != None