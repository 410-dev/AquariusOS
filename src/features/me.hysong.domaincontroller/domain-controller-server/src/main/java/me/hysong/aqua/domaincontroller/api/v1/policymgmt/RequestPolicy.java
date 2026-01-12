package me.hysong.aqua.domaincontroller.api.v1.policymgmt;

import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import me.hysong.aqua.domaincontroller.ApplicationLogger;
import me.hysong.aqua.domaincontroller.util.ResponseErrorState;

import java.io.IOException;

@WebServlet(value = "/control/v1/policy/request")
public class RequestPolicy extends HttpServlet {

    /*

    정책 요청 API

     */

    private ApplicationLogger logger;

    @Override
    public void doGet(HttpServletRequest req, HttpServletResponse resp) throws ServletException, IOException {
        doPost(req, resp);
    }

    @Override
    public void doPost(HttpServletRequest req, HttpServletResponse resp) throws ServletException, IOException {
        try {

        } catch (Exception e) {
            e.printStackTrace();
            ResponseErrorState.responseErrorState(logger, 1, "Core error", resp);
        }
    }
}
