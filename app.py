from flask import Flask, render_template, request, redirect, url_for, session
import os

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "chave_teste_123")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ProfSafe24@VIP")

@app.route("/login_central", methods=["GET", "POST"])
def login_central():
    if request.method == "POST":
        senha = request.form.get("senha")
        usuario = request.form.get("usuario")

        if senha == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/central")
        else:
            return render_template("login_central.html", erro="Senha incorreta")

    return render_template("login_central.html")
