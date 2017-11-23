#!/usr/bin/env python3

from http.server import HTTPServer
from configparser import ConfigParser
from . import RequestHandler

import argparse


parser = argparse.ArgumentParser()
parser.add_argument('name')
parser.add_argument('address', nargs='?', default='localhost')
parser.add_argument('port', nargs='?', default=8001, type=int)

args = parser.parse_args()

RequestHandler.name = args.name
RequestHandler.config = ConfigParser()
RequestHandler.config.read(args.name + '-libs.ini')

# RequestHandler.make_document(RequestHandler)

httpd = HTTPServer((args.address, args.port), RequestHandler)
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    pass
