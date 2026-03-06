package com.acadia.iceberg.ioserver;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import java.util.HashMap;

public class AntiDDoSSys {

    private static final HashMap<String, Long> lastRequest = new HashMap<>();
    private static final HashMap<String, Long> requestCount = new HashMap<>();
    private static final ApplicationLogger logger = new ApplicationLogger("AntiDDoSSys");

    // Policies
    private static final HashMap<String, Object> policies = new HashMap<>();
    /*
    Policies:

    - RateLimit.Enabled: bool (Default: True)
    - RateLimit.TimeWindow: long (Default: 60000, Time window in milliseconds, e.g., 60000 for 1 minute)
    - RateLimit.MaxRequests: int (Default: 300, Maximum requests allowed in the time window)
    - RateLimit.GenerousMode.Enabled: bool (Default: False, If true, wait for several seconds and allow response instead of refusing)
    - RateLimit.GenerousMode.WaitDuration: long (Default: 0, Wait duration in milliseconds before allowing response. 0 means TimeWindow / MaxRequests * 2)

    - IntentionalLatency.Enabled: bool (Default: False)
    - IntentionalLatency.Duration: long (Default: 300, Latency duration in milliseconds)

    - DenialCodeOnBlock: int (Default: 429, HTTP status code to return when blocking)
    - DenialMessageOnBlock: string (Default: "Too Many Requests", Message to return when blocking)
     */

    public static boolean isRequestAllowed(HttpServletRequest req, HttpServletResponse res) {
        String clientIP = req.getRemoteAddr();
        long currentTime = System.currentTimeMillis();

        // Intentional Latency
        if (policies.getOrDefault("IntentionalLatency.Enabled", false).equals(true)) {
            long latencyDuration = (long) policies.getOrDefault("IntentionalLatency.Duration", 300L);
            try {
                Thread.sleep(latencyDuration);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }

        // Check if rate limiting is enabled
        if (policies.getOrDefault("RateLimit.Enabled", true).equals(true)) {
            long timeWindow = (long) policies.getOrDefault("RateLimit.TimeWindow", 60000L);
            int maxRequests = (int) policies.getOrDefault("RateLimit.MaxRequests", 1000);

            long lastTime = lastRequest.getOrDefault(clientIP, 0L);
            long count = requestCount.getOrDefault(clientIP, 0L);

            if (currentTime - lastTime <= timeWindow) {
                count++;
                if (count > maxRequests) {
                    try {
                        if (policies.getOrDefault("RateLimit.GenerousMode.Enabled", false).equals(true)) {
                            long waitDuration = (long) policies.getOrDefault("RateLimit.GenerousMode.WaitDuration", 0L);
                            if (waitDuration <= 0) {
                                waitDuration = (timeWindow / maxRequests) * 2;
                            }
                            Thread.sleep(waitDuration);
                            return true; // Allow the request after waiting
                        }
                        res.setStatus((int) policies.getOrDefault("DenialCodeOnBlock", 429));
                        res.getWriter().println(policies.getOrDefault("DenialMessageOnBlock", "Too Many Requests"));
                    } catch (Exception e) {
                        e.printStackTrace();
                    }
                    logger.warn("Blocked request from " + clientIP + " due to rate limiting. (" + count + " requests in " + timeWindow + " ms)");
                    return false;
                }
            } else {
                count = 1; // Reset count after time window
            }

            lastRequest.put(clientIP, currentTime);
            requestCount.put(clientIP, count);
        }

        return true; // Request is allowed
    }


    public static void applyPolicy(String policyString) {
        // Policy string looks like this:
        // "RateLimit.Enabled=true;RateLimit.TimeWindow=60000;RateLimit.MaxRequests=300;IntentionalLatency.Enabled=false;DenialCodeOnBlock=429;DenialMessageOnBlock=Too Many Requests"
        String[] policyItems = policyString.split(";");
        for (String item : policyItems) {
            String[] keyValue = item.split("=");
            if (keyValue.length != 2) continue;
            String key = keyValue[0].trim();
            String value = keyValue[1].trim();

            // Determine the type of the value
            if (value.equalsIgnoreCase("true") || value.equalsIgnoreCase("false")) {
                policies.put(key, Boolean.parseBoolean(value));
                logger.info("Applied policy: " + key + " = " + value + " (boolean)");
            } else {
                try {
                    long longValue = Long.parseLong(value);
                    policies.put(key, longValue);
                    logger.info("Applied policy: " + key + " = " + value + " (long)");
                } catch (NumberFormatException e1) {
                    try {
                        int intValue = Integer.parseInt(value);
                        policies.put(key, intValue);
                        logger.info("Applied policy: " + key + " = " + value + " (int)");
                    } catch (NumberFormatException e2) {
                        policies.put(key, value); // Treat as string
                        logger.info("Applied policy: " + key + " = " + value + " (string)");
                    }
                }
            }
        }
    }
}
