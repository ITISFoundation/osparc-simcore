


def get_server(servers, url):
    # Development server: http://{host}:{port}/{basePath}
    for server in servers:
        if server.url == url:
            return server
    raise ValueError("Cannot find server %s" % url)
