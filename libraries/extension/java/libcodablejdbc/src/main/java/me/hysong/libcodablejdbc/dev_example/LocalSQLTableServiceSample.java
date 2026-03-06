package me.hysong.libcodablejdbc.dev_example;

import me.hysong.libcodablejdbc.utils.dbtemplates.MySQLTableServiceTemplate;

import java.sql.*;

public class LocalSQLTableServiceSample implements MySQLTableServiceTemplate {

    private static Connection con;

    public LocalSQLTableServiceSample() {
        // This construction is called very frequently so DO NOT make connection here
    }

    @Override
    public Connection getConnection(String database) throws SQLException {
        String url = "jdbc:mariadb://localhost:3306/" + database;
        String user = "test";
        String passwd = "testpasswd";
        if (con == null || con.isClosed()) {
            try {
                Class.forName("org.mariadb.jdbc.Driver");
                con = DriverManager.getConnection(url, user, passwd);
            } catch (ClassNotFoundException e) {
                e.printStackTrace();
            }
        }
        return con;
    }
}
