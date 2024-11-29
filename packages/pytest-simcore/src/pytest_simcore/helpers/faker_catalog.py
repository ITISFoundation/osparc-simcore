def create_service_out(**overrides):
    # FIXME: should change when schema changes

    obj = {
        "name": "Fast Counter",
        "key": "simcore/service/dynanic/itis/sim4life"
        if overrides.get("type") == "dynamic"
        else "simcore/services/comp/itis/sleeper",
        "version": "1.0.0",
        "integration-version": "1.0.0",
        "type": "computational",
        "authors": [
            {
                "name": "Jim Knopf",
                "email": ["sun@sense.eight", "deleen@minbar.bab"],
                "affiliation": ["Sense8", "Babylon 5"],
            }
        ],
        "contact": "lab@net.flix",
        "inputs": {},
        "outputs": {},
        "owner": "user@example.com",
    }
    obj.update(**overrides)
    return obj


def create_service_out2(**overrides):
    #
    # Creates fake from here
    #
    # https://github.com/ITISFoundation/osparc-simcore/blob/master/services/catalog/src/simcore_service_catalog/models/schemas/services.py
    #
    # docker exec -it $(docker ps --filter="ancestor=local/catalog:development" -q)
    # put file in https://json-schema-faker.js.org/ and get fake output
    #

    DATA = {
        "name": "officia",
        "description": "sunt elit",
        "key": "simcore/services/dynamic/xO/WAn/1-/$meZpaVN)/t_&[Q0/TC7Wn#y'j/MilxW/kTtV_{<F",
        "version": "0.0.0",
        "type": "computational",
        "authors": [
            {
                "name": "irure laboris ex exercitation",
                "email": "3jCW9@KdsZCtqqURNgCJ.bn",
                "affiliation": "nostrud Duis dolore",
            },
            {
                "name": "ullamco adipisicing velit sunt Lorem",
                "email": "OSPEwKt@PWDAIufLUmgPPaNpUgivIUIMwEojFWNJ.qu",
            },
        ],
        "contact": "12FRI8dt1hS4@VaLSgDRJdyzRtvYcWFcbqsKRvtXi.qi",
        "inputs": {
            "oA9": {
                "displayOrder": -83647350.74100702,
                "label": "adipisicing sed",
                "description": "laborum in dolore ea deserunt",
                "type": "string",
                "fileToKeyMap": {"&xYc81m,{&": "Ie2SAqQqh"},
                "defaultValue": -29416679.73848383,
                "widget": {"type": "TextArea", "details": {"minHeight": -14138808}},
            }
        },
        "outputs": {
            "OLXR": {
                "displayOrder": -68393947.53353347,
                "label": "laboris aliquip",
                "description": "reprehenderit sunt nulla",
                "type": "number",
                "fileToKeyMap": {"j7wU3": "Ifa"},
                "defaultValue": -57292227,
            }
        },
        "thumbnail": "http://scFYyPyIlEFRivBZIZTqAFWauwderNVkX.jjr,wtX2Hj2KZf1lC3F2yq2vosadBG4I",
        "classifiers": ["ea irure Ut pariatur"],
        "access_rights": {},
        "integration-version": "1526.59.0-0.0.517ayb.23722OKdq5RLi.4091348c4UqKa.0",
        "badges": [
            {
                "name": "adipisicing",
                "image": "https://mXWOWeylgvOAxTU.arhnzn0RgN55v9ltuJ4OTztaKBbGXKvJLH4gUFL4ZMLg-yKopOCm054L7tFZE+35GmMwn",
                "url": "https://zKeaDjANqRLYhEDPuQJCrn.mqpMGG5yfnc-dlXFRxItUySirFFvjFqwnJg8KukL-w1FJ76chxdHvabth0",
            },
            {
                "name": "ea fugiat pariatur",
                "image": "http://BDevIdASnFQPcUQs.lofeYJhA7cn-cwLQQwXc,9ptL.wirwhBJCe98dj7SCnP9pL",
                "url": "http://KcsWcmbWIWFYWelDDJ.dvlRknYVxXpHZTuvZooj.tgY04n2YL0.rilEhBMsIHBh",
            },
            {
                "name": "eiusmod fugiat exercitation",
                "image": "http://K.qapA7IIkOHlX0r1DY0ZEmQZehikHITu2+fVxnXLNKQTWDlxdGPSKAFhoOjx7OKe6",
                "url": "https://kjGGg.yavhqu85ZYTi,cojg2bXQAj,9x54IaYF+RniIQorwjskRBlzq",
            },
            {
                "name": "qui dolor sunt labore velit",
                "image": "http://YhCmELIaUk.bpndbcc-3NEJsPwDdNj.nhrq0U0zhDtu",
                "url": "https://AdBxHsXBCyZScmEOADtCgEw.txhkaWCiVJq.npdxB3La2Ni5baUgkCifnViYXOlb2ih",
            },
            {
                "name": "dolor deserunt",
                "image": "https://GYhHYZxSLqjkWXCPKVDykuYcelJYvhA.ruqgso4AyjjJpLSP0XYV7",
                "url": "https://LNGFjXLg.jflcoxnllceYw",
            },
        ],
        "owner": "HVLfSurF@Vq.bqfz",
    }

    DATA.update(**overrides)
    return DATA
