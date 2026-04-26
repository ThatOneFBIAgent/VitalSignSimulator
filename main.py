"""
VitalSign Pro — High-Fidelity Patient Monitor Replica
Entry point.
"""
from monitor import Monitor


def main():
    monitor = Monitor()
    monitor.run()


if __name__ == "__main__":
    main()
