package com.acadia.iceberg.ioserver.connections;

import com.acadia.iceberg.ioserver.Application;
import me.hysong.libcodablejdbc.utils.dbtemplates.MySQLTableServiceTemplate;

import java.io.File;
import java.sql.Connection;
import java.sql.SQLException;

public class DuckDB implements MySQLTableServiceTemplate {

    // DuckDB는 파일 기반이므로 동일한 파일에 대해 여러 DataSource를 생성하는 것을 방지하기 위해 캐싱합니다.
    private static final java.util.concurrent.ConcurrentHashMap<String, javax.sql.DataSource> DATASOURCES = new java.util.concurrent.ConcurrentHashMap<>();
    private static final Object HOOK_LOCK = new Object();
    private static volatile boolean shutdownHookAdded = false;

    @Override
    public Connection getConnection(String database) throws SQLException {
        if (database == null || database.trim().isEmpty()) {
            // database 이름이 없으면 인메모리 DB로 간주하거나 에러를 낼 수 있으나,
            // 여기서는 파일명을 필수로 봅니다.
            throw new IllegalArgumentException("database name (filename) is required");
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
            throw new SQLException("Failed to obtain connection for DuckDB: " + database, cause);
        }
    }

    private javax.sql.DataSource createDataSource(String db) throws Exception {
        // 1. DuckDB 파일이 저장될 기본 경로 설정 (환경변수)
        String dbHome = Application.getVariable("DUCKDB_HOME");
        if (dbHome == null || dbHome.isEmpty()) {
            dbHome = "."; // 설정이 없으면 현재 실행 경로 사용
        }

        // 2. DB 파일 경로 구성
        // database 파라미터가 ":memory:"인 경우 인메모리 모드로 동작
        String url;
        if (":memory:".equalsIgnoreCase(db)) {
            url = "jdbc:duckdb:";
        } else {
            // 확장자 처리 (.duckdb가 없으면 붙여줌)
            String fileName = db.endsWith(".duckdb") ? db : db + ".duckdb";
            File dbFile = new File(dbHome, fileName);
            // DuckDB는 JDBC URL에 파일 절대 경로를 넣는 것이 안전합니다.
            url = "jdbc:duckdb:" + dbFile.getAbsolutePath();
        }

        // 3. 풀 사이즈 설정
        int maxPool = 10;
        String maxPoolEnv = Application.getVariable("DUCKDB_MAX_POOL");
        if (maxPoolEnv != null) {
            try { maxPool = Integer.parseInt(maxPoolEnv); } catch (NumberFormatException ignored) {}
        }

        // DuckDB는 기본적으로 User/Password가 필요 없으므로 빈 문자열 처리
        String user = "";
        String pass = "";

        try {
            // HikariCP 설정 (Reflection 사용 유지)
            Class<?> hikariConfigClass = Class.forName("com.zaxxer.hikari.HikariConfig");
            Object config = hikariConfigClass.getConstructor().newInstance();

            hikariConfigClass.getMethod("setJdbcUrl", String.class).invoke(config, url);
            // DuckDB Driver 클래스 명시 (필수는 아니지만 명시적 로딩 권장)
            hikariConfigClass.getMethod("setDriverClassName", String.class).invoke(config, "org.duckdb.DuckDBDriver");

            // Username/Password는 무의미하지만 Hikari 설정상 호출
            hikariConfigClass.getMethod("setUsername", String.class).invoke(config, user);
            hikariConfigClass.getMethod("setPassword", String.class).invoke(config, pass);

            hikariConfigClass.getMethod("setMaximumPoolSize", int.class).invoke(config, maxPool);
            // DuckDB는 Embedded라 연결 비용이 낮으므로 MinimumIdle을 적게 유지해도 됨
            hikariConfigClass.getMethod("setMinimumIdle", int.class).invoke(config, Math.max(1, Math.min(2, maxPool)));
            hikariConfigClass.getMethod("setPoolName", String.class).invoke(config, "duckdb-pool-" + db);

            Class<?> hikariDSClass = Class.forName("com.zaxxer.hikari.HikariDataSource");
            java.lang.reflect.Constructor<?> ctor = hikariDSClass.getConstructor(hikariConfigClass);
            Object ds = ctor.newInstance(config);
            return (javax.sql.DataSource) ds;

        } catch (ClassNotFoundException cnf) {
            // HikariCP가 없을 경우 Fallback (DriverManager 사용)
            try {
                Class.forName("org.duckdb.DuckDBDriver");
            } catch (ClassNotFoundException e) {
                throw new SQLException("DuckDB JDBC Driver not found. Please add 'org.duckdb:duckdb_jdbc' dependency.", e);
            }

            return new javax.sql.DataSource() {
                @Override public Connection getConnection() throws SQLException { return java.sql.DriverManager.getConnection(url); }
                @Override public Connection getConnection(String username, String password) throws SQLException { return java.sql.DriverManager.getConnection(url); }
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