package com.acadia.iceberg.ioserver.api.v1;

import com.acadia.iceberg.ioserver.ApplicationLogger;
import com.acadia.iceberg.ioserver.util.ResponseErrorState;
import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import java.io.IOException;

@WebServlet(value = "/iceberg/api/v1/add")
public class Add extends HttpServlet {

    ApplicationLogger logger;


    @Override
    public void doGet(HttpServletRequest request, HttpServletResponse response) throws ServletException {
        doPost(request, response);
    }

    @Override
    public void doPost(HttpServletRequest request, HttpServletResponse response) throws ServletException {
        logger = new ApplicationLogger();

        try {



        } catch (Exception e) {
            e.printStackTrace();
            ResponseErrorState.responseErrorState(logger, 99, e.toString(), response);
        }
    }

}
