from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import time

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        print('do_GET')
        print(self.path)
        print(os.environ.get("SIMCORE_NODE_BASEPATH", '/raw'))
        if self.path == os.environ.get("SIMCORE_NODE_BASEPATH", '/raw'):
            self.path = "/"
            super().do_GET()
        print ('no root')


def run(port=4000):
    server_address = ('127.0.0.1', port)
    server = HTTPServer(server_address, Handler)
    print('Starting server, use <Ctrl-C> to stop')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
    print(time.asctime(), 'Server Stops')

if __name__ == '__main__':
    run()