package me.hysong.libcodablejdbc.utils.dbtemplates;

import me.hysong.libcodablejdbc.Automatic;
import me.hysong.libcodablejdbc.Column;
import me.hysong.libcodablejdbc.PseudoEnum;
import me.hysong.libcodablejdbc.utils.exceptions.InitializationViolationException;
import me.hysong.libcodablejdbc.utils.exceptions.JDBCReflectionGeneralException;
import me.hysong.libcodablejdbc.utils.interfaces.DatabaseTableService;
import me.hysong.libcodablejdbc.utils.interfaces.ResultSetProcessor;
import me.hysong.libcodablejdbc.utils.objects.DatabaseRecord;
import me.hysong.libcodablejdbc.utils.objects.SearchExpression;

import java.io.IOException;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.*;

/**
 * A template interface for SQLite database table services. It provides default
 * implementations for standard CRUD operations.
 */
public interface MySQLTableServiceTemplate extends DatabaseTableService {

    /**
     * Retrieves all columns for a single row identified by its primary key.
     *
     * @param object The object instance containing the primary key value.
     * @return A LinkedHashMap containing the retrieved row, mapped from its primary key to the object representation.
     * @throws InitializationViolationException If the object is not properly initialized.
     * @throws JDBCReflectionGeneralException   If a reflection-related error occurs.
     * @throws SQLException                  If a database access error occurs.
     * @throws IOException                   If an I/O error occurs.
     */
    default LinkedHashMap<Object, DatabaseRecord> selectAll(int privilege, DatabaseRecord object) throws InitializationViolationException, JDBCReflectionGeneralException, SQLException, IOException {
        String sql = "SELECT * FROM " + object.getTable() + " WHERE " + object.getPrimaryKeyColumnName() + " = ?;";
        Object[] params = new Object[]{object.getPrimaryKeyValue()};
        return executeQuery(object.getDatabase(), sql, params, rs -> getObjectDatabaseElementLinkedHashMap(privilege, rs, object));
    }

    /**
     * Processes a ResultSet to create a map of DatabaseElement objects.
     *
     * @param rs     The ResultSet from the database query.
     * @param object The blueprint object used for creating new instances.
     * @return A LinkedHashMap of objects populated from the ResultSet.
     * @throws SQLException                  If a database access error occurs.
     * @throws InitializationViolationException If the object cannot be initialized.
     * @throws JDBCReflectionGeneralException   If a reflection error occurs during object instantiation.
     */
    private LinkedHashMap<Object, DatabaseRecord> getObjectDatabaseElementLinkedHashMap(int privilege, ResultSet rs, DatabaseRecord object) throws SQLException, InitializationViolationException, JDBCReflectionGeneralException {
        LinkedHashMap<Object, DatabaseRecord> result = new LinkedHashMap<>();
        Class<?> objectClass = object.getClass();
        while (rs.next()) {
            try {
                DatabaseRecord newInstance = (DatabaseRecord) objectClass.getDeclaredConstructor().newInstance();
                newInstance.objectifyCurrentRow(privilege, rs);
                result.put(newInstance.getPrimaryKeyValue(), newInstance);
            } catch (NoSuchMethodException | InvocationTargetException | InstantiationException | IllegalAccessException e) {
                throw new JDBCReflectionGeneralException("Expected a public, no-parameter constructor for class " + objectClass.getName(), e);
            }
        }
        return result;
    }

    /**
     * Executes a SQL query that is expected to return a result set.
     *
     * @param database           The name of the database to connect to.
     * @param sql                The SQL query to execute.
     * @param params             The parameters to be set in the PreparedStatement.
     * @param resultSetProcessor A lambda function to process the ResultSet.
     * @param <T>                The return type of the result set processor.
     * @return The result from the resultSetProcessor.
     * @throws SQLException If a database access error occurs.
     */
    default <T> T executeQuery(String database, String sql, Object[] params, ResultSetProcessor<T> resultSetProcessor) throws SQLException, JDBCReflectionGeneralException, InitializationViolationException {
        Connection connection = getConnection(database);
        try (PreparedStatement preparedStatement = connection.prepareStatement(sql)) {
            DatabaseRecord.setObjects(preparedStatement, params);
            try (ResultSet rs = preparedStatement.executeQuery()) {
                return resultSetProcessor.process(rs);
            }
        }
    }

    /**
     * Executes a SQL statement like INSERT, UPDATE, or DELETE.
     *
     * @param database The name of the database to connect to.
     * @param sql      The SQL statement to execute.
     * @param params   The parameters to be set in the PreparedStatement.
     * @return The number of rows affected.
     * @throws SQLException If a database access error occurs.
     */
    default int executeUpdate(String database, String sql, Object[] params) throws SQLException {
        Connection connection = getConnection(database);
        try (PreparedStatement preparedStatement = connection.prepareStatement(sql)) {
            DatabaseRecord.setObjects(preparedStatement, params);
            return preparedStatement.executeUpdate();
        }
    }

    /**
     * Selects records based on specified columns and values with pagination.
     *
     * @param blueprint    An object instance to define the table and database.
     * @param offset       The number of rows to skip.
     * @param limit        The maximum number of rows to return.
     * @param columnNames  The names of the columns to filter by.
     * @param values       The corresponding values for the filter columns.
     * @return A LinkedHashMap of populated objects.
     * @throws IOException                   If an I/O error occurs.
     * @throws SQLException                  If a database access error occurs.
     * @throws InitializationViolationException If an object cannot be initialized.
     * @throws JDBCReflectionGeneralException   If a reflection error occurs.
     */
    default LinkedHashMap<Object, DatabaseRecord> selectBy(int privilege, DatabaseRecord blueprint, int offset, int limit, String[] columnNames, Object[] values) throws IOException, SQLException, InitializationViolationException, JDBCReflectionGeneralException {
        StringBuilder sb = new StringBuilder("SELECT * FROM ");
        sb.append(blueprint.getTable()).append(" WHERE ");
        for (int i = 0; i < columnNames.length; i++) {
            if (!blueprint.getColumnNames(privilege).contains(columnNames[i])) {
                throw new IllegalArgumentException("Column " + columnNames[i] + " not found in table " + blueprint.getTable());
            }

            sb.append(columnNames[i]).append(" = ?");
            if (i < columnNames.length - 1) {
                sb.append(" AND ");
            }
        }

        if (limit > 0) sb.append(" LIMIT ?");
        if (offset > 0) sb.append(" OFFSET ?");
        sb.append(";");

        // The 'values' array might need to be expanded to include limit and offset
        Object[] queryParams = new Object[values.length + (limit > 0 ? 1 : 0) + (offset > 0 ? 1 : 0)];
        System.arraycopy(values, 0, queryParams, 0, values.length);
        int currentIndex = values.length;
        if (limit > 0) queryParams[currentIndex++] = limit;
        if (offset > 0) queryParams[currentIndex] = offset;


        return executeQuery(blueprint.getDatabase(), sb.toString(), queryParams, rs -> getObjectDatabaseElementLinkedHashMap(privilege, rs, blueprint));
    }

    default LinkedHashMap<Object, DatabaseRecord> selectBy(DatabaseRecord blueprint, int offset, int limit, String[] columnNames, Object[] values) throws IOException, SQLException, InitializationViolationException, JDBCReflectionGeneralException {
        return selectBy(0, blueprint, offset, limit, columnNames, values);
    }

    default LinkedHashMap<Object, DatabaseRecord> searchBy(int privilege, DatabaseRecord blueprint, int offset, int limit, SearchExpression[] expressions) throws IOException, SQLException, InitializationViolationException, JDBCReflectionGeneralException {
        StringBuilder sb = new StringBuilder("SELECT * FROM ");
        sb.append(blueprint.getTable()).append(" WHERE ");
        for (int i = 0; i < expressions.length; i++) {

            if (!blueprint.getColumnNames(privilege).contains(expressions[i].getColumn())) {
                throw new IllegalArgumentException("Column " + expressions[i].getColumn() + " not found in table " + blueprint.getTable());
            }

            sb.append(expressions[i].getColumn());

            // IN 절 처리
            if (expressions[i].getIn().length > 0) {
                sb.append(expressions[i].isNegate() ? " NOT IN (" : " IN (");
                for (int j = 0; j < expressions[i].getIn().length; j++) {
                    sb.append("?");
                    if (j < expressions[i].getIn().length - 1) {
                        sb.append(", ");
                    }
                }
                sb.append(")");

            // IN 이 아닌 경우 처리
            // ex: =, !=, LIKE 등
            } else {

                if (expressions[i].isStartsWith() || expressions[i].isEndsWith()) {
                    sb.append(" LIKE ");
                } else {
                    if (expressions[i].isNegate()) {
                        sb.append(" != ");
                    } else {
                        sb.append(" = ");
                    }
                }

                if (expressions[i].isEndsWith()) {
                    sb.append("%");
                }
                sb.append("?");
                if (expressions[i].isStartsWith()) {
                    sb.append("%");
                }
            }

            if (i < expressions.length - 1) {
                if (expressions[i + 1].isAnd()) {
                    sb.append(" AND ");
                } else if (expressions[i + 1].isOr()) {
                    sb.append(" OR ");
                } else {
                    throw new SQLException("Chained SearchExpression must have any of AND or OR set to true using .or() or .and() function.");
                }
            }
        }

        if (limit > 0) sb.append(" LIMIT ?");
        if (offset > 0) sb.append(" OFFSET ?");
        sb.append(";");

//        // The 'values' array might need to be expanded to include limit and offset
//        Object[] queryParams = new Object[expressions.length + (limit > 0 ? 1 : 0) + (offset > 0 ? 1 : 0)];
//        for (int i = 0; i < expressions.length; i++) {
//            queryParams[i] = expressions[i].getValue();
//        }
//        int currentIndex = expressions.length;
//        if (limit > 0) queryParams[currentIndex++] = limit;
//        if (offset > 0) queryParams[currentIndex] = offset;
        ArrayList<Object> paramList = new ArrayList<>();

        for (SearchExpression exp : expressions) {
            // If it is an IN clause, add each element individually
            if (exp.getIn() != null && exp.getIn().length > 0) {
                Collections.addAll(paramList, exp.getIn());
            }
            // Otherwise, add the single value
            else {
                paramList.add(exp.getValue());
            }
        }

        // Add Limit and Offset if they exist
        if (limit > 0) paramList.add(limit);
        if (offset > 0) paramList.add(offset);

        // Convert back to Object[] for executeQuery
        Object[] queryParams = paramList.toArray();

        return executeQuery(blueprint.getDatabase(), sb.toString(), queryParams, rs -> getObjectDatabaseElementLinkedHashMap(privilege, rs, blueprint));
    }

    default LinkedHashMap<Object, DatabaseRecord> searchBy(DatabaseRecord blueprint, int offset, int limit, SearchExpression[] expressions) throws IOException, SQLException, InitializationViolationException, JDBCReflectionGeneralException {
        return searchBy(0, blueprint, offset, limit, expressions);
    }

    /**
     * Updates an existing record in the database.
     *
     * @param object The object containing the updated data and primary key.
     * @return The number of rows affected.
     * @throws InitializationViolationException If the object is not properly initialized.
     * @throws JDBCReflectionGeneralException   If a reflection error occurs.
     * @throws SQLException                  If a database access error occurs.
     * @throws IOException                   If an I/O error occurs.
     */
    default int update(int privilege, DatabaseRecord object) throws InitializationViolationException, JDBCReflectionGeneralException, SQLException, IOException {
        StringBuilder sb = new StringBuilder();
        sb.append("UPDATE ").append(object.getTable()).append(" SET ");

        LinkedHashMap<String, Object> values;
        try {
            values = object.getValues(Integer.MAX_VALUE);
        } catch (IllegalAccessException e) {
            throw new JDBCReflectionGeneralException(e);
        }

//        Object[] params = new Object[values.size() + 1];
        ArrayList<Object> params = new ArrayList<>();
        int i = 0;
        for (String key : values.keySet()) {
            try {
                // 권한 체크
                Field annotationChk = object.getClass().getDeclaredField(key);
                if (object.mayAccessByFieldSecurityPolicy(privilege, true, annotationChk)) {
                    continue;
                }

                // PseudoEnum 체크
                if (object.getClass().getDeclaredField(key).isAnnotationPresent(PseudoEnum.class)) {
                    PseudoEnum enumValue = object.getClass().getDeclaredField(key).getAnnotation(PseudoEnum.class);
                    if (!Arrays.asList(enumValue.accepts()).contains((String) values.get(key))) {
                        throw new RuntimeException("Pseudo enum does not accept value: " + values.get(key));
                    }
                    if (!enumValue.nullable() && values.get(key) == null) {
                        throw new RuntimeException("Pseudo enum does not allow null but got null for: " + key);
                    }
                }
            } catch (NoSuchFieldException | SecurityException e) {
                e.printStackTrace();
            }
            if (i > 0) sb.append(", ");
            sb.append(key).append(" = ?");
//            params[i++] = values.get(key);
            params.add(values.get(key));
            i++;
        }

        sb.append(" WHERE ").append(object.getPrimaryKeyColumnName()).append(" = ?;");
//        params[i] = object.getPrimaryKeyValue();
        params.add(object.getPrimaryKeyValue());

        return executeUpdate(object.getDatabase(), sb.toString(), params.toArray());
    }

    /**
     * Inserts a new record into the database.
     *
     * @param object The object to insert.
     * @return The number of rows affected.
     * @throws InitializationViolationException If the object is not properly initialized.
     * @throws JDBCReflectionGeneralException   If a reflection error occurs.
     * @throws SQLException                  If a database access error occurs.
     * @throws IOException                   If an I/O error occurs.
     */
    default int insert(DatabaseRecord object) throws InitializationViolationException, JDBCReflectionGeneralException, SQLException, IOException {
        StringBuilder columnNames = new StringBuilder();
        StringBuilder valuePlaceholders = new StringBuilder();

        LinkedHashMap<String, Object> values;
        try {
            values = object.getValues(Integer.MAX_VALUE);
        } catch (IllegalAccessException e) {
            throw new JDBCReflectionGeneralException(e);
        }

        Object[] paramValues = new Object[values.size()];
        int i = 0;
        for (String key : values.keySet()) {
            try {
                Field annotationChk = object.getClass().getDeclaredField(key);
                if (annotationChk.isAnnotationPresent(Automatic.class)) {
                    continue;
                }
                if (object.getClass().getDeclaredField(key).isAnnotationPresent(PseudoEnum.class)) {
                    PseudoEnum enumValue = object.getClass().getDeclaredField(key).getAnnotation(PseudoEnum.class);
                    if (!Arrays.asList(enumValue.accepts()).contains((String) values.get(key))) {
                        throw new RuntimeException("Pseudo enum does not accept value: " + values.get(key));
                    }
                    if (!enumValue.nullable() && values.get(key) == null) {
                        throw new RuntimeException("Pseudo enum does not allow null but got null for: " + key);
                    }
                }
            } catch (NoSuchFieldException | SecurityException e) {
                throw new RuntimeException(e);
            }

            if (i > 0) {
                columnNames.append(", ");
                valuePlaceholders.append(", ");
            }
            columnNames.append(key);
            valuePlaceholders.append("?");
            paramValues[i++] = values.get(key);
        }

        String sql = "INSERT INTO " + object.getTable() + " (" + columnNames + ") VALUES (" + valuePlaceholders + ");";

        return executeUpdate(object.getDatabase(), sql, paramValues);
    }

    /**
     * Deletes a record from the database based on its primary key.
     *
     * @param object The object containing the primary key of the record to delete.
     * @return The number of rows affected.
     * @throws InitializationViolationException If the object is not properly initialized.
     * @throws JDBCReflectionGeneralException   If a reflection error occurs.
     * @throws SQLException                  If a database access error occurs.
     * @throws IOException                   If an I/O error occurs.
     */
    default int delete(DatabaseRecord object) throws InitializationViolationException, JDBCReflectionGeneralException, SQLException, IOException {
        String sql = "DELETE FROM " + object.getTable() + " WHERE " + object.getPrimaryKeyColumnName() + " = ?;";
        Object[] params = new Object[]{object.getPrimaryKeyValue()};
        return executeUpdate(object.getDatabase(), sql, params);
    }

}