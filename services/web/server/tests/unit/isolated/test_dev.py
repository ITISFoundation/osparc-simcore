# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import random
import re
from collections import defaultdict
from copy import deepcopy
from typing import DefaultDict, List, Set

import pytest
from pydantic import BaseModel, Field

pytestmark = pytest.mark.skip(reason="Sandbox for development")


####################################################################################################################
# NOTES


#
# To check times pytest --pdb -vv --durations=0  tests/unit/isolated/test_classifiers.py
#

# - every group define it's own classifiers: get_group_classifier
# - definition of classifiers is outsource to an external entity (e.g. github/gitlab/K-Core) that has a strict/consensual curation workflow in place
# So far
# - github/gitlab approach produces a bundle file with a static list of classifiers
#   - CONS:
#        - if large size, it will not fit the tree!?
#        - static. cannot change except if access to db
# - scicrunch approach provides an API to validate
#
#


# osparc-classifiers
#
# - A user from osparc selects a study/service and wants to add a classifier
# - a list of "official" classifier displays and can select one of them (already in the tree)
# - or propose a new one by introducing its RRID
#    - RRID (research resource [RR] curated and defined in K-Core: https://scicrunch.org/api/1/resource/fields/view/SCR_014398 )
#    -
# - if classifier is valid (API check or cache check)
#     add to validated classifier's cache
# - classifiers tree
#  is defined per group (get_group_classifier)
#     - thye
#       all classifiers in cache, based on some rules (e.g. usage, etc) are used to automaticaly update existing classifiers
#

#
#  Branches defined in osparc-framework
#  Leafs are RRID's from scicrunch
#  Where leafs go is suggested by users
#  Both saved in db
#
#

####################################################################################################################


GROUP_CLASSIFIER_SAMPLE = {
    "build_date": "2020-12-14T18:10:00Z",
    "classifiers": {
        "Programming Language::Python": {
            "classifier": "RRID:SCR_008394",
            "display_name": "Python",
            "short_description": "Python Programming Language",
        },
        "Programming Language::Octave": {
            "classifier": "RRID:SCR_014398",
            "display_name": "GNU Octave",
        },
        "Jupyter Notebook": {
            "classifier": "RRID:SCR_018315",
            "display_name": "Jupyter Notebook",
        },
    },
}


SPLIT_STRIP_PATTERN = r"[^:\s][^:]*[^:\s]*"


# model used to load from db??
class BasicClassifier(BaseModel):
    """ Default/minimal model for a classifier """

    classifier: str = Field(
        ..., description="Classifier hierarchical classifier", regex=r"[^:]+"
    )
    display_name: str

    # TODO: normalize classifier??
    def split(self) -> List[str]:
        parts = re.findall(SPLIT_STRIP_PATTERN, self.classifier)
        return parts


class KCoreClassifier(BasicClassifier):
    # If curated by K-Core
    rrid: str = Field(
        ...,
        description="Research Resource Identifier as defined in https://scicrunch.org/resources",
        regex=r"^SRC_\d+$",
    )


####################################################################################################################


def list_folders_paths(tree) -> List[str]:
    paths = []

    def _traverse(d, path=""):
        for k, v in d.items():
            if isinstance(v, dict):
                _traverse(v, f"{path}/{k}")
            else:
                paths.append(f"{path}/{k}".strip("/"))

    _traverse(tree)
    return paths


# def create_valid_classifiers_tree():
def test_it():
    # builds a tree view with a selection of classifiers
    #  - needs a criteria to decide what to include

    # K-core provides
    curated_tags = "foo, bar, baz, qux, quux, corge, grault, garply, waldo, fred, plugh, xyzzy, thud".split(
        ", "
    )

    # osparc organziation provides some classifiers (a skeleton of folder) to place some tags
    tree_skeleton = {
        "Type of Study": {
            "Data Analysis": [],
            "Data Processing": [],
        },
        "Type of Service": {"Computational": []},
    }
    folder_paths: List[str] = list_folders_paths(tree_skeleton)

    # user drags&drop tags (curated documents) into one or more folders
    tag2folders: DefaultDict[str, Set[str]] = defaultdict(set)
    for tag in curated_tags:
        tag2folders[tag].add(random.choice(folder_paths))

    # build a tree with tag
    print("tree-skeleton", json.dumps(tree_skeleton, indent=2))
    tree_view = deepcopy(tree_skeleton)

    # add tag in tree
    for tag in tag2folders.keys():
        for folder_path in tag2folders[tag]:
            # get leaf
            leaf = tree_view
            for p in folder_path.split("/"):
                leaf = leaf[p]
            assert isinstance(leaf, List)  # leaf is always a list
            leaf.append(tag)

    # classifiers in tree ARE VALID (no need for extra validation)
    print("osparc-tree-view", json.dumps(tree_view, indent=2))

    alphabetical_tree = dict.fromkeys(sorted(tag[0].upper() for tag in curated_tags))
    for key in alphabetical_tree:
        alphabetical_tree[key] = list()

    for tag in curated_tags:
        key = tag[0].upper()
        alphabetical_tree[key].append(tag)

    print("alphabetical-tree-view", json.dumps(alphabetical_tree, indent=2))


def test_classifier_model():
    classifier = BasicClassifier(classifier="a: b: cc 23", display_name="A B C")

    assert classifier.split() == ["a", "b", "cc 23"]

    classifier = BasicClassifier(
        classifier="a: b: cc 23", display_name="A B C", rrid="SRC_1234"
    )

    assert classifier.split() == ["a", "b", "cc 23"]
