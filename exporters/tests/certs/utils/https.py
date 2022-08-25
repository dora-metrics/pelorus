from http.server import BaseHTTPRequestHandler, HTTPServer
from ssl import SSLContext


class _ResponseHandler(BaseHTTPRequestHandler):
    """
    Returns a 204 for every GET.
    """

    def do_GET(self):
        self.send_response(204, "NO CONTENT")
        self.end_headers()


def make_server(ssl_context: SSLContext):
    """
    Make an HTTPS server serving on localhost on an ephemeral port.
    """
    server = HTTPServer(("127.0.0.1", 0), _ResponseHandler)
    server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
    return server
