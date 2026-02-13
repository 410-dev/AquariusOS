package me.hysong.aqua.domaincontroller;

import java.util.UUID;

public class ApplicationLogger {

    private String sessionId;

    public ApplicationLogger() {
        this.sessionId = UUID.randomUUID().toString();
    }

    public ApplicationLogger(String sessionId) {
        this.sessionId = sessionId;
    }

    public void info(String message) {
        // TODO: Implement a proper logging mechanism
        // -> Class name
        // -> Method name
        // -> Timestamp
        // -> Log level
        System.out.println("[INFO] [" + sessionId + "] " + message);
    }

    public void error(String message) {
        // TODO: Implement a proper logging mechanism
        System.err.println("[ERROR] [" + sessionId + "] " + message);
    }

    public void warn(String message) {
        // TODO: Implement a proper logging mechanism
        System.out.println("[WARN] [" + sessionId + "] " + message);
    }

    public void debug(String message) {
        System.out.println("[DEBUG] [" + sessionId + "] " + message);
    }
}
