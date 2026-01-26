package com.acadia.iceberg.ioserver.connections;

import me.hysong.libcodablejdbc.utils.interfaces.DatabaseTableService;

public class CoreDatabaseFactory {

    public static DatabaseTableService getConnection() {
        return new DuckDB();
    }

}
