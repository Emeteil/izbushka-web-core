default: run

# -- Python environment --

venv := ".venv"
python := if os_family() == "windows" { venv / "Scripts" / "python.exe" } else { venv / "bin" / "python" }
system_python := if os_family() == "windows" { "python" } else { "python3" }

# create .venv (if missing) and install requirements
setup:
    @{{system_python}} -m venv {{venv}}
    @"{{python}}" -m pip install -q -q --upgrade pip
    @"{{python}}" -m pip install -q -q -r requirements.txt flake8

# same flake8 config as the CI workflow
lint: setup
    "{{python}}" -m flake8 . --max-line-length=120 --exclude=__pycache__,.git,com_link_rt,{{venv}}

run: setup
    "{{python}}" main.py

# full first-time install: submodules, .env, admin user in the database
install:
    git submodule update --init --recursive
    bash install.sh

clean:
    {{system_python}} -c "import shutil; shutil.rmtree('{{venv}}', ignore_errors=True)"
