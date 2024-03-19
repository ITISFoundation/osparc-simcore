#!/bin/env python

def main():
    applications = [{
        'application': 'osparc',
        'replaces': [{
            'search_text': 'replace_me_og_title',
            'replace_text': 'oSPARC'
        }, {
            'search_text': 'replace_me_og_description',
            'replace_text': ''
        }, {
            'search_text': 'replace_me_og_image',
            'replace_text': '../resource/osparc/favicon-osparc.png'
        }]
    }, {
        'application': 's4l',
        'replaces': [{
            'search_text': 'replace_me_og_title',
            'replace_text': 'Sim4Life'
        }, {
            'search_text': 'replace_me_og_description',
            'replace_text': 'my s4l description'
        }, {
            'search_text': 'replace_me_og_image',
            'replace_text': '../resource/osparc/favicon-s4l.png'
        }]
    }, {
        'application': 's4lacad',
        'replaces': [{
            'search_text': 'replace_me_og_title',
            'replace_text': 'Sim4Life Science'
        }, {
            'search_text': 'replace_me_og_description',
            'replace_text': 'my s4l description'
        }, {
            'search_text': 'replace_me_og_image',
            'replace_text': '../resource/osparc/favicon-s4l.png'
        }]
    }, {
        'application': 's4llite',
        'replaces': [{
            'search_text': 'replace_me_og_title',
            'replace_text': 'S4L Lite'
        }, {
            'search_text': 'replace_me_og_description',
            'replace_text': 'my osparc description'
        }, {
            'search_text': 'replace_me_og_image',
            'replace_text': '../resource/osparc/favicon-osparc.png'
        }]
    }, {
        'application': 'tis',
        'replaces': [{
            'search_text': 'replace_me_og_title',
            'replace_text': "TI Plan - IT'IS"
        }, {
            'search_text': 'replace_me_og_description',
            'replace_text': 'my osparc description'
        }, {
            'search_text': 'replace_me_og_image',
            'replace_text': '../resource/osparc/favicon-osparc.png'
        }]
    }]

    for i in applications:
        application = i.get('application')
        path = './source-output/'+application+'/index.html'
        with open(path, 'r') as file:
            print(f"Updating {application}'s index.html")
            data = file.read()
            replaces = i.get('replaces')
            for j in replaces:
                search_text = j.get('search_text')
                replace_text = j.get('replace_text')
                data = data.replace(search_text, replace_text) 

        with open(path, 'w') as file: 
            file.write(data)


if __name__ == '__main__':
    main()
