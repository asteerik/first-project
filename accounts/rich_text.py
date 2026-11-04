from html import escape
from html.parser import HTMLParser
from urllib.parse import urlsplit


ALLOWED_TAGS = {"a", "b", "br", "em", "i", "li", "ol", "p", "strong", "ul"}
VOID_TAGS = {"br"}
SKIPPED_TAGS = {"iframe", "object", "script", "style", "svg"}


class _RichTextSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output = []
        self.open_tags = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIPPED_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth or tag not in ALLOWED_TAGS:
            return

        if tag == "a":
            href = dict(attrs).get("href", "")
            try:
                parsed = urlsplit(href)
            except ValueError:
                parsed = None
            if parsed and parsed.scheme in {"http", "https"} and parsed.netloc:
                self.output.append(f'<a href="{escape(href, quote=True)}" rel="nofollow noopener">')
            elif parsed and parsed.scheme == "mailto" and parsed.path:
                self.output.append(f'<a href="{escape(href, quote=True)}">')
            else:
                self.output.append("<a>")
        else:
            self.output.append(f"<{tag}>")

        if tag not in VOID_TAGS:
            self.open_tags.append(tag)

    def handle_endtag(self, tag):
        if tag in SKIPPED_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth or tag not in self.open_tags:
            return

        while self.open_tags:
            opened = self.open_tags.pop()
            self.output.append(f"</{opened}>")
            if opened == tag:
                break

    def handle_data(self, data):
        if not self.skip_depth:
            self.output.append(escape(data))

    def finish(self):
        while self.open_tags:
            self.output.append(f"</{self.open_tags.pop()}>")
        return "".join(self.output)


def sanitize_rich_text(value):
    parser = _RichTextSanitizer()
    parser.feed(value or "")
    parser.close()
    return parser.finish()
