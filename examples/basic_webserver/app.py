from flask import Flask

app = Flask(__name__)


@app.route("/")
def default():
    return "Hello world.\n"


@app.route("/hello/<id>")
def hello(id=0):
    try:
        id = int(id)
        id += 1
    except ValueError:
        pass
    return f"{id}\n"


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80)
