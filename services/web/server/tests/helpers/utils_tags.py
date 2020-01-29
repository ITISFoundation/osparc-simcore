import json


def get_test_tags():
    with open('data/test_tags_data.json') as fp:
        return json.load(fp).get('added_tags')
