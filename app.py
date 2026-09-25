import os
import secrets
import hashlib
import base64

from flask import Flask, redirect, request, session

app = Flask(__name__)

# Clave para proteger las sesiones de la aplicación
app.secret_key = os.environ.get("FLASK_SECRET_KEY")

# Credenciales de Mercado Libre
ML_CLIENT_ID = os.environ.get("ML_CLIENT_ID")
ML_CLIENT_SECRET = os.environ.get("ML_CLIENT_SECRET")

# URL de nuestra aplicación
REDIRECT_URI = "https://mercado-ofertas.onrender.com/oauth/mercadolibre/callback"


@app.route("/")
def home():
    return """
    <h1>Mercado Ofertas</h1>
    <p>Servidor funcionando correctamente.</p>
    <p><a href="/login/mercadolibre">Conectar con Mercado Libre</a></p>
    """


@app.route("/health")
def health():
    return "OK"


@app.route("/login/mercadolibre")
def login_mercadolibre():
    # Generamos un state para proteger el inicio de sesión
    state = secrets.token_urlsafe(32)

    # Generamos el código secreto de PKCE
    code_verifier = secrets.token_urlsafe(64)

    # Creamos el code_challenge a partir del verifier
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

    # Guardamos estos valores temporalmente en la sesión
    session["oauth_state"] = state
    session["code_verifier"] = code_verifier

    # URL de autorización de Mercado Libre
    authorization_url = (
        "https://auth.mercadolibre.com.mx/authorization"
        f"?response_type=code"
        f"&client_id={ML_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state={state}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )

    return redirect(authorization_url)


@app.route("/oauth/mercadolibre/callback")
def mercadolibre_callback():
    # Revisamos si Mercado Libre devolvió un error
    error = request.args.get("error")

    if error:
        return f"""
        <h2>Error de autorización</h2>
        <p>{error}</p>
        """, 400

    # Obtenemos el código enviado por Mercado Libre
    code = request.args.get("code")

    # Verificamos el state
    state = request.args.get("state")

    if not code:
        return "No se recibió código de autorización.", 400

    if not state or state != session.get("oauth_state"):
        return "Error de seguridad: state inválido.", 400

    # Recuperamos el verifier utilizado en PKCE
    code_verifier = session.get("code_verifier")

    if not code_verifier:
        return "No se encontró el code_verifier de PKCE.", 400

    return f"""
    <h2>¡Autorización recibida!</h2>
    <p>Mercado Libre nos entregó correctamente el código OAuth.</p>
    <p>La siguiente etapa será intercambiar este código por el token de acceso.</p>
    """


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
