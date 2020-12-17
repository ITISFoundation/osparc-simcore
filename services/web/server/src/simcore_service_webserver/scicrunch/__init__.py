"""
   Submodule to interact with K-Core's https://scicrunch.org service
    - client to validate and get info about RRIDs via scicrunch's API (scicrunch_api)
    - keeps validated RRIDs in pg-database (scicrunch_db)
    - define models for all interfaces: scicrunch API, postgres DB and webserver API (scicrunch_models)

   NOTE: should have no dependencies with other modules in this service

   Initial design: https://github.com/ITISFoundation/osparc-simcore/pull/2045
"""
