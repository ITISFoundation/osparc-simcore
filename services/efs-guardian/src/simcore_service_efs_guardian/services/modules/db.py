from fastapi import FastAPI


def get_database_engine(app: FastAPI):
    return app.state.engine
