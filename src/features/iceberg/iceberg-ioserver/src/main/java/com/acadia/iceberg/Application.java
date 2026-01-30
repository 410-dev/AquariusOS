package com.acadia.iceberg;

import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import me.hysong.libcodablejdbc.utils.objects.DatabaseRecord;
import org.eclipse.jetty.ee10.servlet.ServletContextHandler;
import org.eclipse.jetty.server.Server;
import org.reflections.Reflections;

import java.io.BufferedReader;
import java.io.FileReader;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Set;

public class Application {

    private static final HashMap<String, String> variableTable = new HashMap<>();

    public static String getVariable(String key) {
        return getVariable(key, null);
    }

    public static String getVariable(String key, String defaultV) {
        return variableTable.getOrDefault(key, defaultV);
    }

    public static void main(String[] args) throws Exception {

        // 시작 방식

        // java -jar server.jar --build-tables
        // java -jar server.jar
        // java -jar server.jar --apis=v1,v2 --port=9090
        // java -jar server.jar --ddospolicy=<policy_string> // Refer to AntiDDoSSys for policy string format
        // java -jar server.jar --variables=<path>

        // Credentials table 이 주어졌을 경우 Applications.credentialsTable 에 로드
        if (Arrays.stream(args).anyMatch(arg -> arg.startsWith("--variables="))) {
            String credPathArg = Arrays.stream(args).filter(arg -> arg.startsWith("--variables")).findFirst().orElse("");
            String credPart = credPathArg.substring("--variables".length()).trim();
            if (credPart.startsWith("=")) {
                credPart = credPart.substring(1).trim();
            }
            try (FileReader fr = new FileReader(credPart); BufferedReader br = new BufferedReader(fr)) {
                boolean nextHide = false;
                System.out.println("Assigning variables from " + credPart);
                while (true) {
                    String line = br.readLine();
                    if (line == null) break;
                    if (line.strip().equals("#HIDE")) {
                        nextHide = true;
                        continue;
                    }
                    String[] compose = line.split("=");
                    Application.variableTable.put(compose[0], compose[1]);
                    System.out.print(compose[0] + " = ");
                    if (nextHide) {
                        System.out.println("*value hidden*");
                        nextHide = false;
                        continue;
                    }
                    System.out.println(compose[1]);
                }
                System.out.println("Variables assignment completed.");
            }
        }

        // 테이블 생성 모드
        if (Arrays.stream(args).anyMatch(arg -> arg.equalsIgnoreCase("--build-tables"))) {
            buildTables();
            return;
        }

        // 일반 서버 모드
        int port = 8080; // 기본 포트
        if (Arrays.stream(args).anyMatch(arg -> arg.startsWith("--port"))) {
            String portArg = Arrays.stream(args).filter(arg -> arg.startsWith("--port")).findFirst().orElse("");
            String portPart = portArg.substring("--port".length()).trim();
            if (portPart.startsWith("=")) {
                portPart = portPart.substring(1).trim();
            }
            try {
                port = Integer.parseInt(portPart);
            } catch (NumberFormatException e) {
                System.err.println("Invalid port number specified. Using default port 8080.");
            }
        }
        System.out.println("Server starting in port " + port);
        Server server = new Server(port);
        ServletContextHandler handler = new ServletContextHandler(ServletContextHandler.SESSIONS);
        handler.setContextPath("/");

        // DDOS 방지 정책 설정
        if (Arrays.stream(args).anyMatch(arg -> arg.startsWith("--ddospolicy"))) {
            String ddosArg = Arrays.stream(args).filter(arg -> arg.startsWith("--ddospolicy")).findFirst().orElse("");
            String policyPart = ddosArg.substring("--ddospolicy".length()).trim();
            if (policyPart.startsWith("=")) {
                policyPart = policyPart.substring(1).trim();
            }
            String policyName = policyPart;
            AntiDDoSSys.applyPolicy(policyName);
        }

        // 서블릿 자동 추가
        String[] enabledAPIVersions;
        if (Arrays.stream(args).anyMatch(arg -> arg.startsWith("--apis"))) {
            String apiArg = Arrays.stream(args).filter(arg -> arg.startsWith("--apis")).findFirst().orElse("");
            String versionsPart = apiArg.substring("--apis".length()).trim();
            if (versionsPart.startsWith("=")) {
                versionsPart = versionsPart.substring(1).trim();
            }
            String[] versions = versionsPart.split(",");
            ArrayList<String> versionList = new ArrayList<>();
            for (String version : versions) {
                versionList.add(version.trim());
            }
            enabledAPIVersions = versionList.toArray(new String[0]);

            System.out.println("Enabled API Versions: " + String.join(", ", enabledAPIVersions));
        } else {
            enabledAPIVersions = new String[]{"v1"}; // 기본값
        }

        // Servlet package: me.hysong.aqua.domaincontroller.api.{version}
        // me.hysong.aqua.domaincontroller.api.WebServlet 애노테이션을 찾은 후 그 위치에 자동 매핑
        for (String version : enabledAPIVersions) {
            Set<Class<?>> servletClasses = new Reflections("me.hysong.aqua.domaincontroller.api." + version).getTypesAnnotatedWith(WebServlet.class);
            for (Class<?> servletClass : servletClasses) {
                if (!HttpServlet.class.isAssignableFrom(servletClass)) {
                    System.err.println("Class " + servletClass.getName() + " is annotated with @WebServlet but does not extend HttpServlet.");
                    continue;
                }
                WebServlet mapping = servletClass.getAnnotation(WebServlet.class);
                String[] path = mapping.value();
                for (String p : path) {
                    handler.addServlet((Class<? extends HttpServlet>) servletClass, p);
                    System.out.println("Mapped servlet: " + servletClass.getName() + " to path: " + p);
                }
            }
        }


        // 서버 시작
        server.setHandler(handler);
        server.start();
        server.join();

    }

    private static void buildTables() throws Exception {

        // Enumerate all class under me.hysong.aqua.domaincontroller.records
        // Then, call buildTable() method of each class
        Set<Class<? extends DatabaseRecord>> classes = new Reflections("me.hysong.aqua.domaincontroller.records").getSubTypesOf(DatabaseRecord.class);
        // Iterate through the classes and add them to recordClasses
        for (Class<? extends DatabaseRecord> cls : classes) {
            System.out.println("Building table for class: " + cls.getName());
            DatabaseRecord record = cls.getDeclaredConstructor().newInstance();
            try {
                record.buildTable(true);
                System.out.println("Table built for class: " + cls.getName());
            } catch (Exception e) {
                e.printStackTrace();
                System.err.println("Failed to build table for class: " + cls.getName());
                break;
            }
        }
    }
}
