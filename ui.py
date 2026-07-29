import subprocess


def run_ui() -> None:
    subprocess.run(["npm", "--prefix", "frontend", "run", "dev"], check=True)


if __name__ == "__main__":
    run_ui()
