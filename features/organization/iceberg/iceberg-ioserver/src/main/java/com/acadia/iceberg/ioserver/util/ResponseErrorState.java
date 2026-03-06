package com.acadia.iceberg.ioserver.util;

import com.acadia.iceberg.ioserver.ApplicationLogger;
import com.google.gson.JsonObject;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;

public class ResponseErrorState {
    public static void responseErrorState(ApplicationLogger logger, int stateCode, String errorMessage, HttpServletResponse response) {
        JsonObject responseJson = new JsonObject();
        responseJson.addProperty("status", stateCode);
        responseJson.addProperty("error", errorMessage);
        try {
            logger.error("Error " + stateCode + ": " + errorMessage);
            response.getWriter().println(responseJson);
        } catch (IOException e) {
            logger.error("Failed to write error response: " + e.getMessage());
        }
    }
}

