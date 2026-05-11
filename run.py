from app import create_app

app = create_app()

if __name__ == "__main__":
    settings = app.extensions["settings"]
    oauth_service = app.extensions["oauth_service"]

    print("FEISHU_REDIRECT_URI =", settings.redirect_uri)
    print("OAuth auth URL =", oauth_service.build_auth_url())

    app.run(host=settings.host, port=settings.port, debug=settings.debug)
