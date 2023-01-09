from .web_application import create_app

# Singleton app needed for uvicorn's web_server
the_app = create_app()
