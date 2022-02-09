from http.server import BaseHTTPRequestHandler, HTTPServer

response_file_bytes = b""
response_file_txt = ""


class ResponseHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.log_message(
            f"Got request, returning {response_file_txt} "
            f"(as bytes {response_file_bytes})"
        )
        self.send_response(200, "PELORUS IS COOL")
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(response_file_bytes)))
        self.end_headers()

        self.wfile.write(response_file_bytes)


def main():
    global response_file_txt, response_file_bytes
    with open("response.txt", "br") as f:
        response_file_bytes = f.read()
    response_file_txt = response_file_bytes.decode("utf-8")
    print(
        f"Loaded response.txt with contents {response_file_txt} "
        f"(as bytes {response_file_bytes})"
    )
    server = HTTPServer(("", 8080), ResponseHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
