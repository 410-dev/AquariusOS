package me.hysong.libcodablejdbc.utils.interfaces;

import me.hysong.libcodablejdbc.utils.exceptions.InitializationViolationException;
import me.hysong.libcodablejdbc.utils.exceptions.JDBCReflectionGeneralException;
import me.hysong.libcodablejdbc.utils.objects.DatabaseRecord;
import me.hysong.libcodablejdbc.utils.objects.SearchExpression;

import java.io.IOException;
import java.sql.Connection;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.LinkedHashMap;

public interface DatabaseTableService {
    Connection getConnection(String database) throws SQLException;
    
    <T> T executeQuery(String database, String sql, Object[] params, ResultSetProcessor<T> resultSetProcessor) throws SQLException, IOException, JDBCReflectionGeneralException, InitializationViolationException;

    int executeUpdate(String database, String sql, Object[] params) throws SQLException, IOException;

    LinkedHashMap<Object, DatabaseRecord> selectAll(int privilege, DatabaseRecord object) throws InitializationViolationException, JDBCReflectionGeneralException, SQLException, IOException;

    LinkedHashMap<Object, DatabaseRecord> selectBy(int privilege, DatabaseRecord blueprint, int offset, int limit, String[] columnNames, Object[] values) throws IOException, SQLException, InitializationViolationException, JDBCReflectionGeneralException;

    LinkedHashMap<Object, DatabaseRecord> searchBy(int privilege, DatabaseRecord blueprint, int offset, int limit, SearchExpression[] expressions) throws IOException, SQLException, InitializationViolationException, JDBCReflectionGeneralException;

    int update(int privilege, DatabaseRecord object) throws InitializationViolationException, JDBCReflectionGeneralException, SQLException, IOException;

    int insert(DatabaseRecord object) throws InitializationViolationException, JDBCReflectionGeneralException, SQLException, IOException;

    int delete(DatabaseRecord object) throws InitializationViolationException, JDBCReflectionGeneralException, SQLException, IOException;
}
