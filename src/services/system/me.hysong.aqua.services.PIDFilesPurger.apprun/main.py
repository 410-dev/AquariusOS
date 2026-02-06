
from oscore import libapplog as log

def main():
    log.info("This service is managed by systemd. Use 'systemctl' to manage it.")

if __name__ == "__main__":
    main()
