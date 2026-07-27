import sys

from streamlit.web import cli as streamlit_cli


def run_ui() -> None:
    sys.argv = ["streamlit", "run", "ui/streamlit_app.py"]
    streamlit_cli.main()


if __name__ == "__main__":
    run_ui()
