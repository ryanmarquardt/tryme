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
Ul = Tag.new('ul')
Li = Tag.new('li')
Option = Tag.new('option')


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


class Select(Tag):
    name = 'select'

    def __init__(self, *args, **kwargs):
        options = kwargs.pop('options', None)
        selected =kwargs.pop('selected', None)
        super().__init__(*args, **kwargs)
        if options:
            for value, display in options:
                self.children.append(
                    Option({
                        'value': value,
                        'selected': value == selected,
                    })(display))


class Library:
    def __init__(self, name, section):
        self.data = section
        self.name = name

    @property
    def versions(self):
        if not self.data.get('versions'):
            self.data['versions'] = 'current'
        return self.data['versions'].split()

    @property
    def current_version(self):
        if not self.data.get('enabled'):
            self.data['enabled'] = self.versions[0]
        return self.data['enabled']

    @classmethod
    def from_section(cls, config, section):
        return cls(section, config[section])

    def templates(self):
        yield from self.data.get('css', '').split()
        yield from self.data.get('js', '').split()

    def css(self):
        version = self.data.get('enabled', '') or self.versions[0]
        return (
            template.format(version=version)
            for template in self.data.get('css', '').split())

    def js(self):
        version = self.data.get('enabled', '') or self.versions[0]
        return (
            template.format(version=version)
            for template in self.data.get('js', '').split())


class RequestHandler(BaseHTTPRequestHandler):
    default_html = "&lt;h1 class=\"text-success\"&gt;Success&lt;/h1&gt;"
    default_css = ".text-success {\n  color: green;\n}"
    default_js = "$('h1').click(function () {\n  alert('Clicked header');\n})"
    default_libraries = [
        dict(
            name='Jquery',
            js='https://code.jquery.com/jquery-{version}.min.js',
            versions='3.2.1',
        ),
        dict(
            name='Popper',
            js='https://cdnjs.cloudflare.com/ajax/libs/popper.js/'
               '{version}/umd/popper.min.js',
            versions='1.12.3',
        ),
        dict(
            name='Bootstrap',
            css="https://maxcdn.bootstrapcdn.com/bootstrap/"
                "{version}/css/bootstrap.min.css",
            js="https://maxcdn.bootstrapcdn.com/bootstrap/"
                "{version}/js/bootstrap.min.js",
            versions="4.0.0-beta.2",
        ),
    ]

    def __init__(self, *args, **kwargs):
        self.config =  ConfigParser()
        self.config.read(self.name + '-libs.ini')
        if not self.config.sections():
            for lib in self.default_libraries:
                self.config.add_section(lib['name'])
                section = self.config[lib['name']]
                if 'js' in lib:
                    section['js'] = lib['js']
                if 'css' in lib:
                    section['css'] = lib['css']
                if 'versions' in lib:
                    section['versions'] = lib['versions']
                else:
                    section['versions'] = 'current'
            with open(self.name + '-libs.ini', 'w') as f:
                self.config.write(f)
        super().__init__(*args, **kwargs)

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

    @property
    def libraries(self):
        return (Library.from_section(self.config, section)
                for section in self.config.sections())

    def do_GET(self, do_data=True):
        if self.path == '/':
            the_doc = self.make_document('utf-8')
            mime_type = "text/html"
        elif self.path == '/tryme.js':
            the_doc = r"""
function consoleOverride(method, handler) {
    var console = window.console;
    if (console) {
        var original = console[method];
        console[method] = function () {
            if (!handler.apply(console, arguments)) {
                if (original.apply) {
                    // Do this for normal browsers
                    original.apply(console, arguments);
                } else {
                    // Do this for IE
                    var message = Array.prototype.slice.apply(arguments).join(' ');
                    original(message);
                }
            }
        }
    }
}
$(".js-console-wrapper").css("position", "static");
function jsConsoleAppend(cls) {
    return function () {
        $("#js-console").append(
            "<li class=\"" + cls + "\">" +
            Array.from(arguments).join(', ') +
            "<\/li>"
        );
    }
}
consoleOverride('log', jsConsoleAppend("js-console-log"));
consoleOverride('warn', jsConsoleAppend("js-console-warn"));
consoleOverride('error', jsConsoleAppend("js-console-error"));
""".encode('utf-8')
            mime_type = 'text/javascript'
        elif self.path == '/tryme.css':
            the_doc = r"""
#js-console-wrapper {
    position: fixed;
    width: 100%;
    top: 67%;
    height: 33%;
    overflow-x: hidden;
    overflow-y: scroll;
}
.js-console-warn {
    background-color: yellow;
}
.js-console-error {
    background-color: red;
}
#js-console-wrapper {
    border-top: 1px solid black;
}
#js-console-header,
.js-console-log,
.js-console-warn,
.js-console-error {
    border-bottom: 1px solid black;
}
#js-console {
    list-style: none;
    padding-left: 0;
}
""".encode('utf-8')
            mime_type = 'text/css'
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_head(the_doc, mime_type)
        if do_data:
            self.wfile.write(the_doc)
            self.wfile.flush()

    def do_HEAD(self):
        self.do_GET(do_data=False)

    def send_head(self, the_doc, mime_type):
        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", len(the_doc))
        self.end_headers()

    def make_document(self, charset='utf-8', textarea_rows=20):
        head = Head()(
            Meta({'charset': charset}),
            Meta({'name': 'viewport',
                  'content': 'width=device-width, initial-scale=1,'
                             ' shrink-to-fit=no'}),
            Title('Try Me'),

            *[Link({'rel': 'stylesheet', 'href': url})
                for lib in self.libraries
                for url in lib.css()],
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
    font-size: 80%;
    line-height: 1.25;
}
iframe {
    width: 100%;
    height: 100%;
}
            """),
        )
        javascript = join(
            *[Script({'src': url})
                for lib in self.libraries
                for url in lib.js()],
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
        updateTimeoutId = setTimeout(updateTryMe, 1000, true);
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
    the_doc.write("<link rel=\"stylesheet\" href=\"/tryme.css\">");
    $("[data-template$=\".css\"]").each(function() {
        var version = $(this).closest(".list-group-item").find("select").val();
        var url = $(this).attr("data-template");
        if (version) {
            url = url.replace("{version}", version);
            the_doc.write("<link rel=\"stylesheet\" href=\"");
            the_doc.write(
                $(this).attr("data-template").replace('{version}', version));
            the_doc.write("\">");
        }
        $(this).text(url);
    })
    the_doc.write("<style>")
    the_doc.write(document.getElementById("css-input").value);
    the_doc.write("<\/style>")
    the_doc.write("</head><body>")
    the_doc.write("<div id=\"js-console-wrapper\">");
    the_doc.write("<div id=\"js-console-header\">");
    the_doc.write("Javascript Console Output");
    the_doc.write("<\/div><ul id=\"js-console\"><\/ul><\/div>")
    the_doc.write(document.getElementById("html-input").value);
    $("[data-template$=\".js\"]").each(function() {
        var version = $(this).closest(".list-group-item").find("select").val();
        var url = $(this).attr("data-template");
        if (version) {
            url = url.replace("{version}", version);
            the_doc.write("<script src=\"");
            the_doc.write(
                $(this).attr("data-template").replace('{version}', version));
            the_doc.write("\"><\/script>");
        }
        $(this).text(url);
    });
    the_doc.write("<script src=\"/tryme.js\"><\/script>");
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
                            role='tabpanel')(self.library_wrapper_contents()),
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

    def library_wrapper_contents(self):
        return Ul({'class': 'list-group'})(*[
            Li({'class': 'list-group-item'})(
                Div('d-flex w-100 justify-content-between')(
                    Tag.new('h5')({'class': 'mb-1'})(lib.name),
                    Span()(
                        'Use Version: ',
                        Select({
                            'class': 'custom-select',
                            'onchange': 'updateTryMe(true);',
                        },
                            options=[('', '-- Disabled --')] + [
                                (version, version) for version in lib.versions],
                            selected=lib.current_version,
                    )),
                ),
                *[
                    Div(None, {'data-template': template})(
                        template.format(version=lib.current_version))
                    for template in lib.templates()
                ],
            ) for lib in self.libraries
        ])

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
        with open(self.name + '-libs.ini', 'w') as f:
            self.config.write(f)
        the_data = json.dumps(dict(status='ok')).encode('utf-8')
        self.send_response(200)
        self.send_header("Content-Type", "text/json")
        self.send_header("Content-Length", len(the_data))
        self.end_headers()
        self.wfile.write(the_data)
        self.wfile.flush()
