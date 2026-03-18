# flask_app.py
import os
import logging
import time
from flask import Flask, render_template, send_from_directory

# Setup basic logging.
logging.basicConfig(level=logging.DEBUG)

def create_app():
    # Import blueprints.
    from _Game import game_bp
    from _Billing_Routes import billing_bp
    from _Auth import auth_bp
    from _Blog_Functions import Blog_Functions

    app = Flask(__name__)

    # Secure application keys.
    app.secret_key = os.environ['APP_SEC']
    app.config["SHOP_KEY"] = os.environ.get('SHOP_KEY')

    # Register all blueprints.
    app.register_blueprint(auth_bp, url_prefix='/auth')
    # FIX: Removed url_prefix so the external gateway can hit the /final route at the root level.
    app.register_blueprint(billing_bp)
    app.register_blueprint(game_bp)

    @app.route('/favicon.ico')
    def favicon():
        # Log favicon request.
        app.logger.info("Route hit: /favicon.ico")
        return send_from_directory(
            os.path.join(app.root_path, 'static', 'icons'),
            'favicon.ico',
            mimetype='image/vnd.microsoft.icon'
        )

    @app.route('/blog')
    def blog():
        # Log blog request.
        app.logger.info("Route hit: /blog")

        # Initialize blog service.
        blog_functions = Blog_Functions()
        blog_functions.create_blog_entry()

        # Fetch data.
        blog_data = blog_functions.get_blog_data()

        # Format timestamps.
        for entry in blog_data:
            entry['timestamp'] = time.strftime('%Y-%m-%d %H:%M', time.localtime(entry.get('unix_timestamp', 0)))
            entry['formatted_hashtags'] = ' '.join(entry.get('hashtags', []))

        return render_template('blog.html', blog_data=blog_data)

    @app.route('/virtual_gamepad')
    def virtual_gamepad():
        return render_template('virtual_gamepad.html')

    return app

app = create_app()

if __name__ == '__main__':
    # Run development server.
    app.run(debug=True)