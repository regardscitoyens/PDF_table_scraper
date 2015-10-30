global lineskip
global verbose
import re
right = lambda x: x['left'] + x['width']
left = lambda x: x['left']
bottom = lambda x: x['top'] + x['height']
top = lambda x: x['top']
width = lambda x:x['width']

def textline_to_dict(l,strip_html=True):
    r"""
    Turns a XML '<text> ... </text>' line into a python dictionary.

    The (main) fields of this dictionary d are:
        - d['text']
        - d['top']
        - d['bottom']
        - d['width']
        - d['height']

    INPUT:

    - strip_html (boolean) -- whether to remove html tags from the 'text' field.
    """
    d = {}
    kw = [xx.groups()[0] for xx in re.finditer(' ([^ ]*="[0-9]+")',l)]
    for k in kw:
        k = k.split('=')
        d[k[0]] = int(k[1].strip('"'))
    d['text'] = l[l.index('>')+1:l.index('</text>')]
    if strip_html:
        d['text'] = re.sub('<.*?>','',d['text'])
    d['text'] = d['text'].lstrip(' ')
    return d

def merge_text_fields(A,B):
    r"""
    This function merges A and B into B.

    The new text of B becomes A['text']+B['text'], and all dimensions of B are
    updated accordingly.

    A is left unchanged.
    """
    B['text'] = A['text'] +' ' +B['text']
    B['height'] = max(bottom(A),bottom(B)) - min(top(A),top(B))
    B['width'] =  max(right(A),right(B)) - min(left(A),left(B))
    B['top'] = min(top(A),top(B))
    B['left'] = min(left(B),left(A))

def guess_and_merge_split_lines(page):
    r"""
    This function tries to locate and merge split lines.

    This can happen with text lines like "The 1|st| of January" where 'st' is
    written as an exponent. The line is thus cut into three parts in the
    original file.
    """
    # Bottom first
    page_copy = sorted(page,key=right,reverse=True)

    while page_copy:

        # Can this element be merged with anything else?
        rightmost_element = page_copy[0]

        for beginning in page_copy: # potential beginning of the sentence

            if right(beginning) > left(rightmost_element) + lineskip/2: # too close to be the previous sentence
                continue
            if right(beginning) < left(rightmost_element) - lineskip/2: # too far. End of search.
                page_copy.remove(rightmost_element)
                break

            # If one is right above the other, we merge.
            if (top(beginning)    > top(rightmost_element) - lineskip/2 and
                bottom(beginning) < bottom(rightmost_element) + lineskip/2):
                merge_text_fields(beginning,rightmost_element)
                page.remove(beginning)
                page_copy.remove(beginning)
                break
        else:
            page_copy.remove(rightmost_element) # this element can't be merged with anything else

def guess_and_merge_paragraphs(page):
    r"""
    Merge text fields which apparently belong to the same paragraph.

    This function relies on the value of 'lineskip'
    """
    # Bottom first
    page_copy = sorted(page,key=bottom,reverse=True)

    while page_copy:

        # Can this element be merged with anything else?
        lowest_element = page_copy[0]

        for upper in page_copy: # list potential candidates

            if bottom(upper) > top(lowest_element): # too low to be the previous sentence
                continue
            if bottom(upper) < top(lowest_element) - lineskip: # too high. End of search
                page_copy.remove(lowest_element)
                break

            # If one is right above the other, we merge.
            if ((left(upper)-lineskip < left(lowest_element) and right(lowest_element) < right(upper)+lineskip) or
                (left(lowest_element)-lineskip < left(upper) and right(upper) < right(lowest_element)+lineskip)):
                merge_text_fields(upper,lowest_element)
                page.remove(upper)
                page_copy.remove(upper)
                break

        else:
            page_copy.remove(lowest_element) # this element can't be merged with anything else

def split_rows(page, vertical=True):
    r"""
    Split a page into rows.

    ALGORITHM:

    1) Find the element which reaches the lowest in the page.

    2) define top_row as the top level of this element.

    3) Add in the new row all elements whose top is lower than top_row.

    INPUT:

    - vertical (boolean) -- if set to False, works horizontally instead of
      vertically (i.e. split a row into cells).

    """
    if vertical:
        l_top, l_bottom = top, bottom
    else:
        l_top, l_bottom = left, right

    page.sort(key=l_bottom,reverse=True)
    # Not computationally optimal. (Bad data structure: calls to .remove())
    rows = []
    while page:
        lowest_element = page[0]
        top_row = min(l_top(x) for x in page if l_bottom(x) >= l_bottom(lowest_element)-lineskip)
        row = [x for x in page if l_top(x) >= top_row-lineskip]
        for x in row:
            page.remove(x)

        rows.append(row)
    return reversed(rows)

def split_columns(row):
    r"""
    Split a row into cells

    If several elements are contained in the same cells, they are merged into
    one. This is usually a bad sign.
    """
    cells = split_rows(row,vertical=False)
    merged_cells = []
    for C in cells:
        C.sort(key=lambda x:(top(x),left(x)))
        cell_top = min(x['top'] for x in C)
        cell_left = min(x['left'] for x in C)
        cell = {
            'text'  :" ".join(x['text'] for x in C).replace('  ',' '),
            'top'   : cell_top,
            'left'  : cell_left,
            'width' : max(x['left']+x['width']-cell_left for x in C),
            'height': max(x['top']+x['height']-cell_top  for x in C),
        }
        if verbose and len(C)>1:
            print "\n------ Unexpected merge: perhaps a bad value for vskip? ------"
            print cell['text']
        merged_cells.append(cell)

    return merged_cells

def refine_row(A,B):
    r"""
    Add to B the cells of A that could fit. This is a way to 'detect' a blank
    cell in a table by looking at the cells of the surrounding row.
    """
    for a in A:
        if all(right(b) < a['left'] or b['left'] > right(a)
               for b in B):
            a = a.copy()
            a['top'] = B[0]['top']
            a['text'] = ""
            B.append(a)
    B.sort(key=left)

def refine_table(table):
    r"""
    Create missing cells (those who are blank in the pdf)
    """
    for i in range(len(table)-1):
        refine_row(table[-i-1],table[-i-2])
    for i in range(len(table)-1):
        refine_row(table[i],table[i+1])
    return table

def get_cells(page,vskip,verbose_output):
    r"""
    Tries to interpret 'page' as a table, and returns it as a list (rows) of
    text fields (cells).
    """
    global lineskip
    global verbose
    lineskip = vskip
    verbose = verbose_output
    guess_and_merge_split_lines(page)
    guess_and_merge_paragraphs(page)
    rows = split_rows(page)
    table = [split_columns(row) for row in rows]
    table = refine_table(table)
    for x in table:
        yield x
