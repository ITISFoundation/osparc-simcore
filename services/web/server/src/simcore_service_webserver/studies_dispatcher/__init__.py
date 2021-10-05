"""
    This app module dispatches pre-configure or on-the-fly studies to user from a link request
    that is redirected to the front-end which customizes its view

    - Table services_consume_filetypes defines a map between a service (key,version,input_port) and a filetype
    - Exposes viewers resource in API (handlers_rest.py)
    - Entrypoint that dispatches a study to download & view a file (handlers_redirects.py)
        - finds default viewer
        - get or create user
        - get or create project with file-picker(download-link)+viewer
        - redirect to main page (passing study information to the front-end in the fragment)

"""
# TODO: move here all studies_access.py
