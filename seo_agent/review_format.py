"""Conservative report formatting. All source text remains escaped and inert."""
import html
import re


def inline(text):
    text = html.escape(text)
    # Remote images/links and arbitrary HTML remain literal text. Only emphasis
    # and inline code are generated; no source-controlled attributes exist.
    text = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", text)
    return re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", text)


def report_html(text):
    if len(text.encode("utf-8")) > 2 * 1024 * 1024:
        raise ValueError("Report exceeds display limit")
    lines = text.splitlines()
    out, paragraph = [], []
    listing = None
    def flush():
        if paragraph:
            out.append("<p>" + inline(" ".join(paragraph)) + "</p>")
            paragraph.clear()
    def close_list():
        nonlocal listing
        if listing:
            out.append("</" + listing + ">")
            listing = None
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "|" in line and i + 1 < len(lines) and re.fullmatch(r"\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*", lines[i+1]):
            flush(); close_list()
            cells = line.strip("|").split("|")
            out.append("<table><thead><tr>" + "".join("<th>" + inline(c.strip()) + "</th>" for c in cells) + "</tr></thead><tbody>")
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                out.append("<tr>" + "".join("<td>" + inline(c.strip()) + "</td>" for c in lines[i].strip().strip("|").split("|")) + "</tr>")
                i += 1
            out.append("</tbody></table>")
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        item = re.match(r"^(?:([-*])|\d+\.)\s+(.+)$", line)
        if not line:
            flush(); close_list()
        elif heading:
            flush(); close_list()
            level = len(heading[1])
            out.append(f"<h{level}>" + inline(heading[2]) + f"</h{level}>")
        elif item:
            flush()
            kind = "ul" if item[1] else "ol"
            if listing != kind:
                close_list(); out.append("<" + kind + ">"); listing = kind
            out.append("<li>" + inline(item[2]) + "</li>")
        elif line.startswith("> "):
            flush(); close_list()
            out.append("<blockquote>" + inline(line[2:]) + "</blockquote>")
        else:
            close_list(); paragraph.append(line)
        i += 1
    flush(); close_list()
    return '<article class="review-report">' + "\n".join(out) + "</article>"
