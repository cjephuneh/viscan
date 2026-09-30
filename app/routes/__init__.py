from app.routes.ai_routes import blp as ai_blp
from app.routes.assessment_routes import blp as assessment_blp
from app.routes.facility_routes import blp as facility_blp
from app.routes.health_routes import blp as health_blp
from app.routes.image_routes import blp as image_blp
from app.routes.language_routes import blp as language_blp
from app.routes.maps_routes import blp as maps_blp
from app.routes.notification_routes import blp as notification_blp
from app.routes.screening_routes import blp as screening_blp
from app.routes.voice_routes import blp as voice_blp


def register_blueprints(api, app) -> None:
    # Health stays on a plain Flask blueprint for a simple {"status","database"} payload.
    app.register_blueprint(health_blp)

    api.register_blueprint(facility_blp)
    api.register_blueprint(screening_blp)
    api.register_blueprint(image_blp)
    api.register_blueprint(ai_blp)
    api.register_blueprint(assessment_blp)
    api.register_blueprint(maps_blp)
    api.register_blueprint(notification_blp)
    api.register_blueprint(language_blp)
    api.register_blueprint(voice_blp)
