from flask import Flask

app = Flask(__name__)


@app.route("/")
def hello1():
    # returns 0
    return "0\n"

@app.route("/<arg>")
def hello(arg=0):
    # returns arg+1
    try:
        arg = int(arg)
        arg += 1
    except ValueError:
        pass
    return str(arg) + "\n"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80)

