#!/usr/bin/env python

# Parse input
import argparse
parser = argparse.ArgumentParser(description='Extracts a table from a .pdf file')
parser.add_argument('filename', help="the .pdf file", type=argparse.FileType('r'))
parser.add_argument('--vskip', help="max vertical space between consecutive lines in the same paragraph (usually ~8)",type=int,default=8)
parser.add_argument('--page', help="run the script on a specific page",type=int,default=-1)
parser.add_argument('--html', help="A filename for html output",type=argparse.FileType('w'))
parser.add_argument('--pickle', help="A filename for Python .pickle output",type=argparse.FileType('w'))
parser.add_argument('-v', help="Increase the verbosity level", dest='verbose', action='store_true',default=False)

args = parser.parse_args()
vskip = args.vskip

# Turn the .pdf into a .xml and read it
import tempfile, os, subprocess
xml_file = tempfile.mkstemp(suffix=".xml")[1]
os.remove(xml_file)
subprocess.check_call(["pdftohtml", args.filename.name,"-xml", xml_file],stdout=open(os.devnull,'w'))
if not os.path.isfile(xml_file):
    raise Exception("There was an error when running the pdftohtml command")

with open(xml_file,'r') as f:
    data = [x.strip() for x in f.readlines()]


# Parse the .xml data into individual pages
import page_to_cells
pages = []
while data:
    # Beginning of page
    if not data[0].startswith('<page'):
        data.pop(0)
        continue

    pages.append([])
    while not data[0].startswith('</page'):
        x = data.pop(0)
        # we only keep text zones
        if x.startswith('<text'):
            x = page_to_cells.textline_to_dict(x)
            if x['text']: # skip empty text zones
                pages[-1].append(x)

# Keep only one page if requested
if args.page != -1:
    pages = [pages[args.page]]

# Actual work
pages = [list(page_to_cells.get_cells(p,vskip=vskip,verbose_output=args.verbose))
         for p in pages]

# HTML output
if args.html:
    s = ""
    for p in pages:
        s += "<table border=1>"
        for r in p:
            s += "<tr>"
            for i,x in enumerate(r):
                s += "<td>"+x['text']+"</td>"
            s += "</tr>"
        s += "</table><br><br>"
    args.html.write(s)
    args.html.close()

# Pickle output
if args.pickle:
    import pickle
    pickle.dump(pages,args.pickle)