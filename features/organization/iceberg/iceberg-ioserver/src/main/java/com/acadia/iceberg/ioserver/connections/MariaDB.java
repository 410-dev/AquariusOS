package com.acadia.iceberg.ioserver.connections;

import com.acadia.iceberg.ioserver.Application;
import me.hysong.libcodablejdbc.utils.dbtemplates.MySQLTableServiceTemplate;

import java.sql.Connection;
import java.sql.SQLException;

public class MariaDB implements MySQLTableServiceTemplate {
    private static final java.util.concurrent.ConcurrentHashMap<String, javax.sql.DataSource> DATASOURCES = new java.util.concurrent.ConcurrentHashMap<>();
    private static final Object HOOK_LOCK = new Object();
    private static volatile boolean shutdownHookAdded = false;

    @Override
    public Connection getConnection(String database) throws SQLException {
        if (database == null || database.trim().isEmpty()) {
            throw new IllegalArgumentException("database is required");
        }
        try {
            javax.sql.DataSource ds = DATASOURCES.computeIfAbsent(database, db -> {
                try {
                    return createDataSource(db);
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            });
            addShutdownHookOnce();
            return ds.getConnection();
        } catch (RuntimeException e) {
            Throwable cause = e.getCause() != null ? e.getCause() : e;
            if (cause instanceof SQLException) throw (SQLException) cause;
            throw new SQLException("Failed to obtain connection for database: " + database, cause);
        }
    }

    private javax.sql.DataSource createDataSource(String db) throws Exception {
        String host = Application.getVariable("MARIADB_HOST");
        if (host == null || host.isEmpty()) host = "localhost";
        String port = Application.getVariable("MARIADB_PORT");
        if (port == null || port.isEmpty()) port = "3306";
        String user = Application.getVariable("MARIADB_USER");
        if (user == null || user.isEmpty()) user = "root";
        String pass = Application.getVariable("MARIADB_PASSWORD");
        if (pass == null) pass = "";
        int maxPool = 10;
        String maxPoolEnv = Application.getVariable("MARIADB_MAX_POOL");
        if (maxPoolEnv != null) {
            try { maxPool = Integer.parseInt(maxPoolEnv); } catch (NumberFormatException ignored) {}
        }
        String url = "jdbc:mariadb://" + host + ":" + port + "/" + db + "?characterEncoding=UTF-8&useSSL=false";

        try {
            Class<?> hikariConfigClass = Class.forName("com.zaxxer.hikari.HikariConfig");
            Object config = hikariConfigClass.getConstructor().newInstance();
            hikariConfigClass.getMethod("setJdbcUrl", String.class).invoke(config, url);
            hikariConfigClass.getMethod("setUsername", String.class).invoke(config, user);
            hikariConfigClass.getMethod("setPassword", String.class).invoke(config, pass);
            hikariConfigClass.getMethod("setMaximumPoolSize", int.class).invoke(config, maxPool);
            hikariConfigClass.getMethod("setMinimumIdle", int.class).invoke(config, Math.max(1, Math.min(2, maxPool)));
            hikariConfigClass.getMethod("setPoolName", String.class).invoke(config, "mariadb-pool-" + db);
            Class<?> hikariDSClass = Class.forName("com.zaxxer.hikari.HikariDataSource");
            java.lang.reflect.Constructor<?> ctor = hikariDSClass.getConstructor(hikariConfigClass);
            Object ds = ctor.newInstance(config);
            return (javax.sql.DataSource) ds;
        } catch (ClassNotFoundException cnf) {
            try {
                Class.forName("org.mariadb.jdbc.Driver");
            } catch (ClassNotFoundException e) {
                try { Class.forName("com.mysql.cj.jdbc.Driver"); } catch (Exception ignored) {}
            }
            String finalUser = user;
            String finalPass = pass;
            return new javax.sql.DataSource() {
                @Override public Connection getConnection() throws SQLException { return java.sql.DriverManager.getConnection(url, finalUser, finalPass); }
                @Override public Connection getConnection(String username, String password) throws SQLException { return java.sql.DriverManager.getConnection(url, username, password); }
                @Override public <T> T unwrap(Class<T> iface) throws SQLException { throw new SQLException("Not a wrapper"); }
                @Override public boolean isWrapperFor(Class<?> iface) throws SQLException { return false; }
                @Override public java.io.PrintWriter getLogWriter() throws SQLException { return java.sql.DriverManager.getLogWriter(); }
                @Override public void setLogWriter(java.io.PrintWriter out) throws SQLException { java.sql.DriverManager.setLogWriter(out); }
                @Override public void setLoginTimeout(int seconds) throws SQLException { java.sql.DriverManager.setLoginTimeout(seconds); }
                @Override public int getLoginTimeout() throws SQLException { return java.sql.DriverManager.getLoginTimeout(); }
                @Override public java.util.logging.Logger getParentLogger() { return java.util.logging.Logger.getLogger("global"); }
            };
        }
    }

    private void addShutdownHookOnce() {
        if (shutdownHookAdded) return;
        synchronized (HOOK_LOCK) {
            if (shutdownHookAdded) return;
            Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                for (javax.sql.DataSource ds : DATASOURCES.values()) {
                    try {
                        if (ds == null) continue;
                        try {
                            java.lang.reflect.Method close = ds.getClass().getMethod("close");
                            close.invoke(ds);
                        } catch (NoSuchMethodException ignored) {
                        }
                    } catch (Throwable ignored) {}
                }
            }));
            shutdownHookAdded = true;
        }
    }
}