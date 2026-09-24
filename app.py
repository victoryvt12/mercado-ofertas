from flask import Flask, request

app = Flask(__name__)


@app.route("/")
def home():
    return "Mercado Ofertas - servidor funcionando"


@app.route("/health")
def health():
    return "OK"


@app.route("/oauth/mercadolibre/callback")
def mercadolibre_callback():
    code = request.args.get("code")
    error = request.args.get("error")

    if error:
        return f"Error de autorización: {error}", 400

    if not code:
        return "No se recibió código de autorización.", 400

    return "Autorización recibida correctamente."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
