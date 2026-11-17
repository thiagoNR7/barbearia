from app import create_app

app = create_app()

if __name__ == "__main__":
    # Desenvolvimento: python run.py  ->  http://127.0.0.1:5000
    # Produção (Render): gunicorn run:app
    app.run(debug=True)
