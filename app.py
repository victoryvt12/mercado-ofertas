import os
import secrets
import hashlib
import base64
import requests

from flask import Flask, redirect, request, session

app = Flask(__name__)

app.secret_key = os.environ.get("FLASK_SECRET_KEY")

ML_CLIENT_ID = os.environ.get("ML_CLIENT_ID")
ML_CLIENT_SECRET = os.environ.get("ML_CLIENT_SECRET")

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

    state = secrets.token_urlsafe(32)

    code_verifier = secrets.token_urlsafe(64)

    digest = hashlib.sha256(
        code_verifier.encode("utf-8")
    ).digest()

    code_challenge = base64.urlsafe_b64encode(
        digest
    ).decode("utf-8").rstrip("=")

    session["oauth_state"] = state
    session["code_verifier"] = code_verifier

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

    error = request.args.get("error")

    if error:
        return f"""
        <h2>Error de autorización</h2>
        <p>{error}</p>
        """, 400

    code = request.args.get("code")
    state = request.args.get("state")

    if not code:
        return "No se recibió código de autorización.", 400

    if not state or state != session.get("oauth_state"):
        return "Error de seguridad: state inválido.", 400

    code_verifier = session.get("code_verifier")

    if not code_verifier:
        return "No se encontró el code_verifier de PKCE.", 400

    # Intercambio del código por tokens
    token_response = requests.post(
        "https://api.mercadolibre.com/oauth/token",
        headers={
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded"
        },
        data={
            "grant_type": "authorization_code",
            "client_id": ML_CLIENT_ID,
            "client_secret": ML_CLIENT_SECRET,
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier
        },
        timeout=30
    )

    if token_response.status_code != 200:
        return f"""
        <h2>Error al obtener el Access Token</h2>
        <p>Código HTTP: {token_response.status_code}</p>
        <p>Mercado Libre rechazó el intercambio.</p>
        """, 400

    token_data = token_response.json()

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    user_id = token_data.get("user_id")

    if not access_token:
        return "Mercado Libre no devolvió un Access Token.", 400

    # Guardamos temporalmente los tokens en la sesión.
    # NO los mostramos en pantalla ni en los logs.
    session["access_token"] = access_token
    session["refresh_token"] = refresh_token
    session["ml_user_id"] = user_id

    return f"""
    <h2>¡Mercado Libre conectado correctamente! 🎉</h2>

    <p>Access Token obtenido correctamente.</p>

    <p><strong>User ID:</strong> {user_id}</p>

    <p>
    La siguiente etapa será guardar de forma segura el token
    y utilizarlo para consultar la API de Mercado Libre.
    </p>
    """


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
