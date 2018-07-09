"""
    Main entry-point for computational backend
"""

from .comp_backend_subscribe import subscribe



def setup_computational_backend(app):
    # subscribe to rabbit upon startup
    app.on_startup.append(subscribe)
