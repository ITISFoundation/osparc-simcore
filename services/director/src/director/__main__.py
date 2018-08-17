#!/usr/bin/env python3

import connexion

def mainAioHttp():
    app = connexion.AioHttpApp(__name__, specification_dir='../../.openapi/v1/')    
    app.add_api('director_api.yaml', arguments={'title': 'Director API'})#, validate_responses=True)
    app.run(port=8001)


def main():
    app = connexion.App(__name__, specification_dir='../../.openapi/v1/')    
    app.add_api('director_api.yaml', arguments={'title': 'Director API'})#, validate_responses=True)
    app.run(port=8001)


if __name__ == '__main__':
    main()
