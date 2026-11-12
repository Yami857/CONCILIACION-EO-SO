"""Punto de entrada WSGI del Conciliador EO / SO."""

from app import create_app

app = create_app()


if __name__ == "__main__":
    # Servidor local de desarrollo en 127.0.0.1:5000, sin modo debug.
    app.run(host="127.0.0.1", port=5000, debug=False)
