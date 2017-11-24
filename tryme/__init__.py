#!/usr/bin/env python3

from http.server import BaseHTTPRequestHandler
from configparser import ConfigParser
from cgi import FieldStorage
import json


def join(*elements):
    if len(elements) == 1:
        elements = elements[0]
    return ''.join(str(e) for e in elements)


class Tag(dict):
    empty = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.children = []

    @classmethod
    def new(cls, name, empty=False):
        return type(name, (cls,), dict(name=name, empty=bool(empty)))

    def __call__(self, *children):
        self.children = list(children)
        return self

    def start_tag(self, closer=''):
        return '<{}{}{}>'.format(
            self.name,
            join(
                ' {}{}'.format(
                    key, '' if value is True else '={!r}'.format(value))
                for (key, value) in self.items()
                if value is not False and value is not None
            ),
            closer,
        )

    def empty_tag(self):
        return self.start_tag(' /')

    def end_tag(self):
        return '</{}>'.format(self.name)

    def __html__(self):
        return (self.empty_tag() if self.empty else
                join(self.start_tag(), *self.children, self.end_tag()))

    def __str__(self):
        return self.__html__()

    def __repr__(self):
        return 'Tag({}, {})'.format(self.name, dict.__repr__(self))

    def add_class(self, name):
        classes = self.get('class', '').split()
        if name not in classes:
            classes.append(name)
        self['class'] = ' '.join(classes)

    def remove_class(self, name):
        classes = self.get('class', '').split()
        self['class'] = [c for c in classes if c != name]

    def has_class(self, name):
        return any(c == name for c in self.get('class', '').split())


Html = Tag.new('html')
Head = Tag.new('head')
Body = Tag.new('body')
Meta = Tag.new('meta', empty=True)
Link = Tag.new('link', empty=True)
Style = Tag.new('style')
Script = Tag.new('script')
Title = Tag.new('title')()
Span = Tag.new('span')
Input = Tag.new('input', empty=True)
Button = Tag.new('button')
A = Tag.new('a')
Textarea = Tag.new('textarea')
Label = Tag.new('label')
Pre = Tag.new('pre')
Nav = Tag.new('nav')


class Div(Tag):
    name = 'div'

    def __init__(self, classes, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self['class'] = classes


class Form(Tag):
    name ='form'

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('method', 'post')
        kwargs.setdefault('action', '#')
        kwargs.setdefault('enctype', 'multipart/form-data')
        super().__init__(*args, **kwargs)


class RequestHandler(BaseHTTPRequestHandler):
    default_html = "&lt;h1 class=\"text-success\"&gt;Success&lt;/h1&gt;"
    default_css = ".text-success {\n  color: green;\n}"
    default_js = """$("h1").click(function () {
  alert("Clicked the header");
})"""
    libraries = {
        'JQuery 3.2.1': "https://code.jquery.com/jquery-3.2.1.min.js",
        'Popper.js 1.12.3': "https://cdnjs.cloudflare.com/ajax/libs/popper.js/"
                            "1.12.3/umd/popper.min.js",
        'Bootstrap.js 4.0.0-beta.2':
            "https://maxcdn.bootstrapcdn.com/bootstrap/"
            "4.0.0-beta.2/js/bootstrap.min.js",
        'Bootstrap.css 4.0.0-beta.2':
            "https://maxcdn.bootstrapcdn.com/bootstrap/"
            "4.0.0-beta.2/css/bootstrap.min.css",
    }

    @property
    def html(self):
        try:
            with open(self.name + '.html', 'r') as f:
                return f.read()
        except FileNotFoundError:
            return self.default_html

    @property
    def css(self):
        try:
            with open(self.name + '.css', 'r') as f:
                return f.read()
        except FileNotFoundError:
            return self.default_css

    @property
    def js(self):
        try:
            with open(self.name + '.js', 'r') as f:
                return f.read()
        except FileNotFoundError:
            return self.default_js

    def do_GET(self, do_data=True):
        the_doc = self.make_document('utf-8')
        self.send_head(the_doc)
        if do_data:
            self.wfile.write(the_doc)

    def do_HEAD(self):
        self.do_GET(do_data=False)

    def send_head(self, the_doc):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", len(the_doc))
        self.end_headers()

    def make_document(self, charset='utf-8', textarea_rows=20):
        libraries = self.libraries
        if hasattr(self, 'config'):
            libraries.update(self.config.items('libraries'))
        head = Head()(
            Meta({'charset': charset}),
            Meta({'name': 'viewport',
                  'content': 'width=device-width, initial-scale=1,'
                             ' shrink-to-fit=no'}),
            Title('Try Me'),

            *[Link({'rel': 'stylesheet', 'href': v})
                for v in libraries.values()
                if v.endswith('.css')],
            Style({'type': 'text/css'})("""
#preview {
    height: 30em;
    border: 1px solid rgb(206, 212, 218);
    border-radius: 0.25rem;
}
.form-group label {
    padding: 0.25rem 0.5rem;
    margin-bottom: 0;
    margin-left: 0.5rem;
    border: 1px solid rgb(206, 212, 218);
    border-bottom: none;
    border-top-left-radius: 0.25rem;
    border-top-right-radius: 0.25rem;
}
.form-check label {
    border: none;
}
.code-input {
    font-family: SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",
                 "Courier New",monospace;
}
            """),
        )
        javascript = join(
            *[Script({'src': v}) for v in libraries.values()
              if v.endswith('.js')],
            Script()(r"""
function sendToServer() {
    var data = new FormData($("form")[0]);
    var button = $("#submitButton");
    button.prop("disabled", true);
    $.ajax({
        url: '/',
        data: data,
        cache: false,
        contentType: false,
        timeout: 4000,
        processData: false,
        method: 'POST'
    })
    .always(function () {
        button.prop("disabled", false);
    })
    .done(function () {
        console.log("Saved");
    })
    .fail(function(jqXHR, textStatus, errorThrown) {
        var message = "Request failed: "
        if (textStatus=="error") {
            if (jqXHR.status==0) {
                message = message + "Unable to connect";
            } else {
                message = message + "[" + jqXHR.status + "] " + errorThrown;
            }
        } else {
            message = message + textStatus + " " + errorThrown;
        }
        console.error(message);
    });
}
function insertAtCursor(el, newText) {
  var start = el.prop("selectionStart")
  var end = el.prop("selectionEnd")
  var text = el.val()
  var before = text.substring(0, start)
  var after  = text.substring(end, text.length)
  el.val(before + newText + after)
  el[0].selectionStart = el[0].selectionEnd = start + newText.length
  el.focus()
}
var updateTimeoutId = 0;
function updateTryMe(force) {
    if (updateTimeoutId > 0) {
        clearTimeout(updateTimeoutId);
        updateTimeoutId = 0;
    }
    if (!force) {
        updateTimeoutId = setTimeout(updateTryMe, 500, true);
        return;
    };
    var iframe = document.createElement("iframe");
    iframe.setAttribute("frameborder", "0");
    iframe.setAttribute("id", "iframeResult");
    iframe.setAttribute("name", "iframeResult");
    var preview = document.getElementById("preview");
    preview.innerHTML = "";
    preview.appendChild(iframe);
    var iframe_window = (iframe.contentWindow) ? iframe.contentWindow :
        (iframe.contentDocument.document) ? iframe.contentDocument.document :
        iframe.contentDocument;
    var the_doc = iframe_window.document;
    the_doc.open();
    the_doc.write("<html><head>")
    $("input[name=libraries][value$=\".css\"]").each(function() {
        var jqt = $(this);
        if (jqt.prop("checked")) {
            the_doc.write("<link rel=\"stylesheet\" href=\"");
            the_doc.write(jqt.val());
            the_doc.write("\"><\/script>");
        }
    })
    the_doc.write("<style>")
    the_doc.write(document.getElementById("css-input").value);
    the_doc.write("<\/style>")
    the_doc.write("</head><body>")
    the_doc.write(document.getElementById("html-input").value);
    $("input[name=libraries][value$=\".js\"]").each(function() {
        var jqt = $(this);
        if (jqt.prop("checked")) {
            the_doc.write("<script src=\"");
            the_doc.write(jqt.val());
            the_doc.write("\"><\/script>");
        }
    })
    the_doc.write("<script>")
    the_doc.write(document.getElementById("js-input").value);
    the_doc.write("<\/script></body>");
    the_doc.close();
    if (the_doc.body && !the_doc.body.isContentEditable) {
        the_doc.body.contentEditable = true;
        the_doc.body.contentEditable = false;
    }
}
updateTryMe(true);
$("textarea").keydown(function (event) {
    if (event.which == 9) {
        event.preventDefault();
        insertAtCursor($(event.target), "  ");
        console.log("Tab");
    }
})
            """)
        )
        body = Body()(
            Div('container-fluid')(Div('row')(
                Div('col-12')(
                    Tag.new('h1')()('TryMe Code Preview Machine'),
                ),
                Div('col-md-6')(Form()(
                    Nav({
                        'class': 'nav nav-tabs',
                        'id': 'nav-tabs',
                        'role': 'tablist'})(
                        A({
                            'class': 'nav-item nav-link active',
                            'id': 'html-tab',
                            'data-toggle': 'tab',
                            'href': '#html-wrapper',
                            'role': 'tab',
                            'aria-controls': 'html-wrapper',
                            'aria-selected': 'true'})("HTML"),
                        A({
                            'class': 'nav-item nav-link',
                            'id': 'css-tab',
                            'data-toggle': 'tab',
                            'href': '#css-wrapper',
                            'role': 'tab',
                            'aria-controls': 'css-wrapper',
                            'aria-selected': 'true'})("CSS"),
                        A({
                            'class': 'nav-item nav-link',
                            'id': 'javascript-tab',
                            'data-toggle': 'tab',
                            'href': '#javascript-wrapper',
                            'role': 'tab',
                            'aria-controls': 'javascript-wrapper',
                            'aria-selected': 'true'})("Javascript"),
                        A({
                            'class': 'nav-item nav-link',
                            'id': 'libraries-tab',
                            'data-toggle': 'tab',
                            'href': '#libraries-wrapper',
                            'role': 'tab',
                            'aria-controls': 'libraries-wrapper',
                            'aria-selected': 'true'})("Libraries"),
                    ),
                    Div('tab-content', id="tabs")(
                        Div('form-group tab-pane fade show active',
                            id='html-wrapper',
                            role='tabpanel')(
                            Textarea({
                                'id': 'html-input',
                                'name': 'html',
                                'class': 'form-control code-input',
                                'oninput': 'updateTryMe();',
                                'rows': textarea_rows})(self.html),
                        ),
                        Div('form-group tab-pane fade',
                            id='css-wrapper',
                            role='tabpanel')(
                            Textarea({
                                'id': 'css-input',
                                'name': 'css',
                                'class': 'form-control code-input',
                                'oninput': 'updateTryMe();',
                                'rows': textarea_rows})(self.css),
                        ),
                        Div('form-group tab-pane fade',
                            id='javascript-wrapper',
                            role='tabpanel')(
                            Textarea({
                                'id': 'js-input',
                                'name': 'javascript',
                                'class': 'form-control code-input',
                                'oninput': 'updateTryMe();',
                                'rows': textarea_rows})(self.js),
                        ),
                        Div('form-group tab-pane fade',
                            id='libraries-wrapper',
                            role='tabpanel')(*[
                            Div('form-check')(
                                Label({'class': 'form-check-label'})(
                                    Input({
                                        'class': 'form-check-input',
                                        'type': 'checkbox',
                                        'name': 'libraries',
                                        'value': url,
                                        'checked': True}),
                                    name))
                            for name, url in libraries.items()
                        ]),
                    ),
                    Button({
                        'type': 'button',
                        'class': 'btn btn-primary',
                        'onclick': 'sendToServer()',
                        'id': 'submitButton',
                    })("Save"),
                )),
                Div('col-md-6')(
                    Label({'for': 'preview'})("Result"),
                    Div(None, id='preview'),
                ),
            )),
            javascript,
        )
        doc = '<!DOCTYPE html>\n' + str(
            Html()(head, body)
        )
        return str(doc).encode(charset)

    def do_POST(self):
        data = FieldStorage(self.rfile, environ=dict(
            REQUEST_METHOD='post',
            QUERY_STRING='',
        ), headers=self.headers)
        if 'html' in data:
            with open(self.name + '.html', 'w') as f:
                f.write(data['html'].value)
        if 'css' in data:
            with open(self.name + '.css', 'w') as f:
                f.write(data['css'].value)
        if 'javascript' in data:
            with open(self.name + '.js', 'w') as f:
                f.write(data['javascript'].value)
        the_data = json.dumps(dict(status='ok')).encode('utf-8')
        self.send_response(200)
        self.send_header("Content-Type", "text/json")
        self.send_header("Content-Length", len(the_data))
        self.end_headers()
        self.wfile.write(the_data)
        self.wfile.flush()

