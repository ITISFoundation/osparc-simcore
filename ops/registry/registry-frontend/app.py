from flask import Flask, render_template

from requests import Session, RequestException
import json
import os
from werkzeug.routing import BaseConverter

app = Flask(__name__)

class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]

app.url_map.converters['regex'] = RegexConverter

@app.route("/")
def index():
    r = registry_request('_catalog')
    j = r.json()

    return frontend_template('index.html', images=j['repositories'])

@app.route('/image/<path:image>')
def image(image):
    r = registry_request(image + '/tags/list')
    j = r.json()

    kwargs = {
        'tags': j['tags'],
        'image': image,
        'registry': os.environ['REGISTRY_URL'],
    }

    return frontend_template('image.html', **kwargs)

@app.route('/image/<path:image>/tag/<tag>')
def manifest(image, tag):
    r = registry_request(image + '/manifests/' + tag)
    j = r.json()
    
    labels = json.loads(j["history"][0]["v1Compatibility"])["container_config"]["Labels"]
    kwargs = {
        'tag': tag,
        'image': image,
        'layers': len(j['fsLayers']),
        'labels': labels
        }

    return frontend_template('tag.html', **kwargs)

def frontend_template(template, **kwargs):
    '''
    Wrapper function around the flask render_template function
    to always set the frontend_url for the view.
    '''
    return render_template(template, frontend_url=FRONTEND_URL, **kwargs)


def registry_request(path, method="GET"):
    api_url = os.environ['REGISTRY_URL'] + '/v2/' + path

    try:
        #r = s.get(api_url, verify=False) #getattr(s, method.lower())(api_url)
        r = getattr(s, method.lower())(api_url)
        if r.status_code == 401:
            raise Exception('Return Code was 401, Authentication required / not successful!')
        else:
            return r
    except RequestException as e:
        raise Exception("Problem during docker registry connection")

if __name__ == "__main__":
    s = Session()

    # get authentication state or set default value
    REGISTRY_AUTH = os.environ.get('REGISTRY_AUTH',False)

    # get base_url or set default value
    FRONTEND_URL = os.getenv('FRONTEND_URL','/')
    if not FRONTEND_URL.endswith('/'):
        FRONTEND_URL = FRONTEND_URL + "/"

    if REGISTRY_AUTH == "True" or REGISTRY_AUTH == "true":
        s.auth = (os.environ['REGISTRY_USER'], os.environ['REGISTRY_PW'])

    print("Registry URL: " + os.environ['REGISTRY_URL'])
    print("Frontend URL: " + FRONTEND_URL)

    app.run(host='0.0.0.0', debug=False, port=5001, threaded=True)
