package me.hysong.libcodablejdbc.utils.objects;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.Getter;
import me.hysong.libcodablejdbc.*;
import me.hysong.libcodablejdbc.utils.exceptions.InitializationViolationException;
import me.hysong.libcodablejdbc.utils.exceptions.JDBCReflectionGeneralException;
import me.hysong.libcodablejdbc.utils.interfaces.DatabaseTableService;
import me.hysong.libcodablejson.JsonCodable;

import java.io.IOException;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.math.BigDecimal;
import java.sql.*;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.*;

public abstract class DatabaseRecord implements RSCodable {
    private static final ObjectMapper objectMapper = new ObjectMapper();
    @Getter private boolean isPKInitialized = false;
    @Getter private final DatabaseTableService controller;

    public DatabaseRecord(DatabaseTableService controller) {
        this.controller = controller;
    }

    public int update(int privilege) throws JDBCReflectionGeneralException, SQLException, InitializationViolationException, IOException {
        return controller.update(privilege, this);
    }

    public int insert() throws JDBCReflectionGeneralException, SQLException, InitializationViolationException, IOException {
        return controller.insert(this);
    }

    public int delete() throws JDBCReflectionGeneralException, SQLException, InitializationViolationException, IOException {
        return controller.delete(this);
    }

    public LinkedHashMap<Object, DatabaseRecord> directSQL(String sql, Object[] params) throws JDBCReflectionGeneralException, SQLException, InitializationViolationException, IOException {
        return controller.executeQuery(
                getDatabase(),
                sql,
                params,
                (rs) -> {
                    LinkedHashMap<Object, DatabaseRecord> result = new LinkedHashMap<>();
                    Class<?> objectClass = this.getClass();
                    while (rs.next()) {
                        try {
                            DatabaseRecord newInstance = (DatabaseRecord) objectClass.getDeclaredConstructor().newInstance();
                            newInstance.objectifyCurrentRow(Integer.MAX_VALUE, rs);
                            result.put(newInstance.getPrimaryKeyValue(), newInstance);
                        } catch (NoSuchMethodException | InvocationTargetException | InstantiationException | IllegalAccessException e) {
                            throw new JDBCReflectionGeneralException("Expected a public, no-parameter constructor for class " + objectClass.getName(), e);
                        }
                    }
                    return result;
                }
        );
    }

    public LinkedHashMap<Object, DatabaseRecord> selectBy(int privilege, String[] columnNames, int offset, int limit) throws JDBCReflectionGeneralException, SQLException, InitializationViolationException, IOException {
        // Get values for the specified column names in current object
        LinkedHashMap<String, Object> allValues;
        try {
            allValues = getValues(privilege);
        } catch (IllegalAccessException e) {
            throw new JDBCReflectionGeneralException(e);
        }

        Object[] values = new Object[columnNames.length];
        for (int i = 0; i < columnNames.length; i++) {
            values[i] = allValues.get(columnNames[i]);
        }

        return controller.selectBy(privilege, this, offset, limit, columnNames, values);
    }

    public LinkedHashMap<Object, DatabaseRecord> selectBy(int privilege, String ... columnNames) throws JDBCReflectionGeneralException, SQLException, InitializationViolationException, IOException {
        return selectBy(privilege, columnNames, 0, -1);
    }

    public LinkedHashMap <Object, DatabaseRecord> selectAll(int privilege) throws JDBCReflectionGeneralException, SQLException, InitializationViolationException, IOException {
        return controller.selectAll(privilege, this);
    }

    public void select(int privilege) throws JDBCReflectionGeneralException, SQLException, InitializationViolationException, IOException, IllegalAccessException {
        LinkedHashMap<Object, DatabaseRecord> selected = selectAll(privilege);
        if (selected == null || selected.isEmpty()) {
            return;
        }
        Object firstIndex = selected.sequencedKeySet().getFirst();
        DatabaseRecord loaded = selected.get(firstIndex);

        for (Field field : loaded.getClass().getDeclaredFields()) {
            field.setAccessible(true);
            field.set(this, field.get(loaded));
        }
    }

    public String getDatabase() throws InitializationViolationException{
        if (!this.getClass().isAnnotationPresent(Database.class)) {
            throw new InitializationViolationException("Database is not configured using @Database(db=...) annotation.");
        }
        Database annotation = this.getClass().getAnnotation(Database.class);
        return annotation.db();
    }

    public String getTable() throws InitializationViolationException {
        if (!this.getClass().isAnnotationPresent(Database.class)) {
            throw new InitializationViolationException("Table is not configured using @Database(table=...) annotation.");
        }
        Database annotation = this.getClass().getAnnotation(Database.class);
        return annotation.table();
    }

    public String getPrimaryKeyColumnName() throws InitializationViolationException{
        if (!this.getClass().isAnnotationPresent(PrimaryKey.class)) {
            throw new InitializationViolationException("Primary key is not configured using @PrimaryKey annotation.");
        }
        PrimaryKey annotation = this.getClass().getAnnotation(PrimaryKey.class);
        return annotation.column();
    }


    public Object getPrimaryKeyValue() throws InitializationViolationException, JDBCReflectionGeneralException {
        if (!this.getClass().isAnnotationPresent(PrimaryKey.class)) {
            throw new InitializationViolationException("Primary key is not configured using @PrimaryKey annotation.");
        }
        PrimaryKey annotation = this.getClass().getAnnotation(PrimaryKey.class);
        try {
            Field f = this.getClass().getDeclaredField(annotation.column());
            f.setAccessible(true);
            return f.get(this);
        } catch (NoSuchFieldException | IllegalAccessException e) {
            throw new JDBCReflectionGeneralException(e);
        }
    }

    public void setPrimaryKeyValue(Object value) throws InitializationViolationException, JDBCReflectionGeneralException {
        if (isPKInitialized) {
            throw new InitializationViolationException("Primary key is already initialized.");
        }
        if (!this.getClass().isAnnotationPresent(PrimaryKey.class)) {
            throw new InitializationViolationException("Primary key is not configured using @PrimaryKey annotation.");
        }
        PrimaryKey annotation = this.getClass().getAnnotation(PrimaryKey.class);
        try {
            Field f = this.getClass().getDeclaredField(annotation.column());
            f.setAccessible(true);
            f.set(this, value);
            isPKInitialized = true;
        } catch (IllegalAccessException | NoSuchFieldException e) {
            throw new JDBCReflectionGeneralException(e);
        }
    }

    public boolean mayAccessByFieldSecurityPolicy(int privilegeLevel, boolean writeMode, Field field) {

        // 권한 체크 우선순위:
        // 1. allowedAccessLevels 속성
        // 2. minAccessLevel 속성

        // 만약 Integer.MAX_VALUE 가 들어온다면 무조건 허용
        if (privilegeLevel == Integer.MAX_VALUE) {
            return true;
        }

        // Column 어노테이션이 없다면 무조건 허용
        if (!field.isAnnotationPresent(Column.class)) {
            return true;
        } else {
            Column columnAnnotation = field.getAnnotation(Column.class);

            // 권한 레벨 검사
            int[] allowedAccessLevels = columnAnnotation.allowedAccessLevels();
            int minAccessLevel = columnAnnotation.minAccessLevel();

            // 쓰기/읽기 모드에 따른 별도 권한 설정이 있다면 그것을 우선
            if (writeMode) {

                int[] wAllowedAccessLevels = columnAnnotation.writeAllowedAccessLevels();
                int wMinAccessLevel = columnAnnotation.writeMinAccessLevel();

                // 쓰기 권한이 별도로 설정되어 있다면 그것을 우선
                if (wAllowedAccessLevels.length > 0) {
                    allowedAccessLevels = wAllowedAccessLevels;
                }
                if (wMinAccessLevel > 0) {
                    minAccessLevel = wMinAccessLevel;
                }

            } else {

                int[] rAllowedAccessLevels = columnAnnotation.readAllowedAccessLevels();
                int rMinAccessLevel = columnAnnotation.readMinAccessLevel();

                // 읽기 권한이 별도로 설정되어 있다면 그것을 우선
                if (rAllowedAccessLevels.length > 0) {
                    allowedAccessLevels = rAllowedAccessLevels;
                }
                if (rMinAccessLevel > 0) {
                    minAccessLevel = rMinAccessLevel;
                }
            }

            // allowedAccessLevels 가 설정되어 있다면 그것이 우선
            if (allowedAccessLevels.length > 0) {
                boolean isAllowed = false;
                for (int level : allowedAccessLevels) {
                    if (privilegeLevel == level) {
                        isAllowed = true;
                        break;
                    }
                }
                return isAllowed;

            // 그렇지 않다면 minAccessLevel 검사
            } else return privilegeLevel >= minAccessLevel;
        }
    }

    public LinkedHashMap<String, String> getColumns() {
        return getColumns(0);
    }

    public LinkedHashMap<String, String> getColumns(int privilegeLevel) {
        LinkedHashMap<String, String> columns = new LinkedHashMap<>();
        for (Field field : this.getClass().getDeclaredFields()) {

            // Mapping element 가 아니라면 무시
            if (!RSCodableUtil.isMarkedMappingElement(field)) {
                continue;
            }

            // 접근 가능하도록 설정
            field.setAccessible(true);

            // 권한 체크
            if (!mayAccessByFieldSecurityPolicy(privilegeLevel, false, field)) {
                continue;
            }

            // CompositionObject 타입이라면 재귀적으로 분해
            if (field.getType().isAssignableFrom(CompositionObject.class)) {
                CompositionObject compositionObject;
                try {
                    compositionObject = (CompositionObject) field.get(this);
                } catch (IllegalAccessException e) {
                    throw new RuntimeException(e);
                }
                compositionObject.setPrefix(field.getName());
                HashMap<String, Object> keys = compositionObject.decompose();
                for (String key : keys.keySet()) {
                    columns.put(key, keys.get(key).getClass().getName());
                }
            } else {
                columns.put(RSCodableUtil.getFieldNameInDB(field), field.getType().getName());
            }
        }
        return columns;
    }

    public ArrayList<String> getColumnNames() {
        return getColumnNames(0);
    }

    public ArrayList<String> getColumnNames(int privilegeLevel) {
        ArrayList<String> columnNames = new ArrayList<>();
        for (Field field : this.getClass().getDeclaredFields()) {

            // Mapping element 가 아니라면 무시
            if (!RSCodableUtil.isMarkedMappingElement(field)) {
                continue;
            }

            // 접근 가능하도록 설정
            field.setAccessible(true);

            // 권한 검사
            if (!mayAccessByFieldSecurityPolicy(privilegeLevel, false, field)) {
                continue;
            }

            // CompositionObject 타입이라면 재귀적으로 분해
            if (field.getType().isAssignableFrom(CompositionObject.class)) {
                CompositionObject compositionObject;
                try {
                    compositionObject = (CompositionObject) field.get(this);
                } catch (IllegalAccessException e) {
                    throw new RuntimeException(e);
                }
                compositionObject.setPrefix(field.getName());
                String[] keys = compositionObject.compositionKeys();
                Collections.addAll(columnNames, keys);
                continue;
            }
            columnNames.add(RSCodableUtil.getFieldNameInDB(field));
        }
        return columnNames;
    }

    public LinkedHashMap<String, Object> getValues() throws IllegalAccessException {
        return getValues(0);
    }

    public LinkedHashMap<String, Object> getValues(int privilegeLevel) throws IllegalAccessException {
        LinkedHashMap<String, Object> values = new LinkedHashMap<>();
        for (Field field : this.getClass().getDeclaredFields()) {

            // Mapping element 가 아니라면 무시
            if (!RSCodableUtil.isMarkedMappingElement(field)) {
                continue;
            }

            // 접근 가능하도록 설정
            field.setAccessible(true);

            // 권한 검사
            if (!mayAccessByFieldSecurityPolicy(privilegeLevel, false, field)) {
                continue;
            }

            // CompositionObject 타입이라면 재귀적으로 분해
            if (field.getType().isAssignableFrom(CompositionObject.class)) {
                CompositionObject compositionObject = (CompositionObject) field.get(this);
                compositionObject.setPrefix(field.getName());
                HashMap<String, Object> decomposed = compositionObject.decompose();
                for (String key : decomposed.keySet()) {
                    values.put(key, decomposed.get(key));
                }
                continue;
            }
            values.put(RSCodableUtil.getFieldNameInDB(field), field.get(this));
        }
        return values;
    }

    public static PreparedStatement setObjects(PreparedStatement preparedStatement, Object... parameters) {
        try {
            for (int i = 0; i < parameters.length; i++) {
                int parameterIndex = i + 1;
                Object param = parameters[i];
                if (param == null) {
                    preparedStatement.setNull(parameterIndex, Types.NULL);
                } else if (param instanceof String s) {
                    preparedStatement.setString(parameterIndex, s);
                } else if (param instanceof Integer integer) {
                    preparedStatement.setInt(parameterIndex, integer);
                } else if (param instanceof Long l) {
                    preparedStatement.setLong(parameterIndex, l);
                } else if (param instanceof Double v) {
                    preparedStatement.setDouble(parameterIndex, v);
                } else if (param instanceof BigDecimal bigDecimal) {
                    preparedStatement.setBigDecimal(parameterIndex, bigDecimal);
                } else if (param instanceof Boolean b) {
                    preparedStatement.setBoolean(parameterIndex, b);
                } else if (param instanceof LocalDate localDate) {
                    preparedStatement.setObject(parameterIndex, localDate);
                } else if (param instanceof LocalDateTime localDateTime) {
                    preparedStatement.setObject(parameterIndex, localDateTime);
                } else if (param instanceof Timestamp timestamp) {
                    preparedStatement.setTimestamp(parameterIndex, timestamp);
                } else if (param instanceof java.sql.Date date) {
                    preparedStatement.setDate(parameterIndex, date);
                } else if (param instanceof List || param instanceof Map) {
                    try {
                        String jsonString = objectMapper.writeValueAsString(param);
                        preparedStatement.setString(parameterIndex, jsonString);
                    } catch (Exception e) {
                        throw new RuntimeException("Failed to serialize object to JSON for PreparedStatement", e);
                    }
                } else if (param.getClass().isAssignableFrom(JsonCodable.class)) {
                    String jsonString = ((JsonCodable) param).toJsonString();
                    preparedStatement.setString(parameterIndex, jsonString);
                } else if (param.getClass().isAssignableFrom(CompositionObject.class)) {
                    try {
                        LinkedHashMap<String, Object> decomposed = ((CompositionObject) param).decompose();
                        String jsonString = objectMapper.writeValueAsString(decomposed);
                        preparedStatement.setString(parameterIndex, jsonString);
                    } catch (Exception e) {
                        throw new RuntimeException("Failed to serialize CompositionObject to JSON for PreparedStatement", e);
                    }
                } else {
                    preparedStatement.setObject(parameterIndex, param);
                }
            }
        } catch (SQLException e) {
            throw new RuntimeException("Failed to set PreparedStatement parameters", e);
        }
        return preparedStatement;
    }

    public boolean buildTable() {
        try {
            return buildTable(false);
        } catch (Exception e) {
            e.printStackTrace();
            return false;
        }
    }

    public boolean buildTable(boolean useThrow) throws SQLException {
        // Get @Database annotation
        if (!this.getClass().isAnnotationPresent(Database.class)) {
            throw new RuntimeException("Database is not configured using @Database(db=...) annotation.");
        }
        Database dbAnnotation = this.getClass().getAnnotation(Database.class);
        String dbName = dbAnnotation.db();
        String tableName = dbAnnotation.table();
        String query = "CREATE TABLE IF NOT EXISTS " + dbName + "." + tableName + " (";
        ArrayList<String> columnDefs = new ArrayList<>();
        for (Field field : this.getClass().getDeclaredFields()) {
            if (!RSCodableUtil.isMarkedMappingElement(field)) {
                continue;
            }
            String columnName = RSCodableUtil.getFieldNameInDB(field);
            String sqlType = RSCodableUtil.mapJavaTypeToSQLType(field.getType());
            String columnDef = columnName + " " + sqlType;
            if (this.getClass().isAnnotationPresent(PrimaryKey.class)) {
                PrimaryKey pkAnnotation = this.getClass().getAnnotation(PrimaryKey.class);
                if (pkAnnotation.column().equals(columnName)) {
                    columnDef += " PRIMARY KEY";
                }
            }
            if (field.isAnnotationPresent(Automatic.class)) {
                columnDef += " AUTO_INCREMENT";
            }
            columnDefs.add(columnDef);
        }

        query += String.join(", ", columnDefs) + ");";
        try (Connection conn = controller.getConnection(dbName); Statement stmt = conn.createStatement()) {
            stmt.executeUpdate(query);
            return true;
        } catch (SQLException e) {
            if (useThrow) {
                throw e;
            } else {
                return false;
            }
        }
    }

    public void deepFetch(int privilege, int depth) {
         // Iterate through fields with @ForeignKey or @ForeignKeyList annotation
        for (Field field : this.getClass().getDeclaredFields()) {
            if (field.isAnnotationPresent(ForeignKeyList.class)) {
//                ForeignKeyList fkListAnnotation = field.getAnnotation(ForeignKeyList.class);
//                Class<? extends DatabaseRecord> foreignClass = fkListAnnotation.type();
//                String foreignKeyColumn = fkListAnnotation.reference();
//                String assignTo = fkListAnnotation.assignTo();
//
//                // Current field is expected to have ArrayList<?> type which is list of foreign keys
//                field.setAccessible(true);
//                try {
//                    Object foreignKeyListObj = field.get(this);
//                    if (!(foreignKeyListObj instanceof ArrayList<?> foreignKeyList)) {
//                        continue; // Skip if not an ArrayList
//                    }
//
//                    // Prepare to collect fetched foreign records
//                    ArrayList<DatabaseRecord> fetchedRecords = new ArrayList<>();
//
//                    // For each foreign key, fetch the corresponding record
//                    for (Object foreignKeyValue : foreignKeyList) {
//                        DatabaseRecord foreignRecordInstance = foreignClass.getDeclaredConstructor(DatabaseTableService.class)
//                                .newInstance(this.controller);
//
//                        // Set the foreign key value to the appropriate field
//                        Field foreignField = foreignClass.getDeclaredField(foreignKeyColumn);
//                        foreignField.setAccessible(true);
//                        foreignField.set(foreignRecordInstance, foreignKeyValue);
//                        // Fetch the full foreign record
//                        foreignRecordInstance.select(privilege);
//                        // If depth > 1, recursively deep fetch
//                        if (depth > 1) {
//                            foreignRecordInstance.deepFetch(privilege, depth - 1);
//                        }
//                        fetchedRecords.add(foreignRecordInstance);
//                    }
//                    // Assign fetched records to the designated field
//                    if (!assignTo.isEmpty()) {
//                        Field assignField = this.getClass().getDeclaredField(assignTo);
//                        assignField.setAccessible(true);
//                    }
//                } catch (Exception e) {
//                    throw new RuntimeException(e);
//                }
                ForeignKeyList fkListAnnotation = field.getAnnotation(ForeignKeyList.class);
                Class<? extends DatabaseRecord> foreignClass = fkListAnnotation.type();
                String foreignKeyColumn = fkListAnnotation.reference();
                String assignTo = fkListAnnotation.assignTo();

                field.setAccessible(true);
                try {
                    Object foreignKeyListObj = field.get(this);
                    if (!(foreignKeyListObj instanceof ArrayList<?> foreignKeyList) || foreignKeyList.isEmpty()) {
                        continue;
                    }

                    // 1. Prepare the Search Expressions (Batching)
                    // detailed: Construct "WHERE foreignKeyColumn IN (?,?,?)"
                    SearchExpression[] expressions = new SearchExpression[1];
                    expressions[0] = new SearchExpression()
                            .column(foreignKeyColumn)
                            .in(foreignKeyList.toArray());

                    // 2. Execute ONE Query for all items
                    DatabaseRecord blueprint = foreignClass.getDeclaredConstructor().newInstance();

                    // Pass -1 (or 0) as limit to ensure we fetch all matches
                    LinkedHashMap<Object, DatabaseRecord> results = this.controller.searchBy(
                            privilege,
                            blueprint,
                            0,
                            -1,
                            expressions
                    );

                    ArrayList<DatabaseRecord> fetchedRecords = new ArrayList<>(results.values());

                    // 3. Handle Recursive Deep Fetch
                    if (depth > 1) {
                        for (DatabaseRecord rec : fetchedRecords) {
                            rec.deepFetch(privilege, depth - 1);
                        }
                    }

                    // 4. Assign to the target field
                    if (!assignTo.isEmpty()) {
                        Field assignField = this.getClass().getDeclaredField(assignTo);
                        assignField.setAccessible(true);

                        // Overwrite the list with the fully fetched collection
                        // (Assuming target field is ArrayList as per original code constraints)
                        assignField.set(this, fetchedRecords);
                    }

                } catch (Exception e) {
                    throw new RuntimeException("Failed during optimized deepFetch", e);
                }

            } else if (field.isAnnotationPresent(ForeignKey.class)) {
                ForeignKey fkAnnotation = field.getAnnotation(ForeignKey.class);
                Class<? extends DatabaseRecord> foreignClass = fkAnnotation.type();
                String foreignKeyColumn = fkAnnotation.reference();
                String assignTo = fkAnnotation.assignTo();

                // Current field is expected to have the foreign key value
                field.setAccessible(true);
                try {
                    Object foreignKeyValue = field.get(this);
                    if (foreignKeyValue == null) {
                        continue; // Skip if foreign key value is null
                    }

                    // Create an instance of the foreign record
                    DatabaseRecord foreignRecordInstance = foreignClass.getDeclaredConstructor(DatabaseTableService.class)
                            .newInstance(this.controller);

                    // Set the foreign key value to the appropriate field
                    Field foreignField = foreignClass.getDeclaredField(foreignKeyColumn);
                    foreignField.setAccessible(true);
                    foreignField.set(foreignRecordInstance, foreignKeyValue);
                    // Fetch the full foreign record
                    foreignRecordInstance.select(privilege);
                    // If depth > 1, recursively deep fetch
                    if (depth > 1) {
                        foreignRecordInstance.deepFetch(privilege, depth - 1);
                    }
                    // Assign fetched record to the designated field
                    if (!assignTo.isEmpty()) {
                        Field assignField = this.getClass().getDeclaredField(assignTo);
                        assignField.setAccessible(true);
                        assignField.set(this, foreignRecordInstance);
                    }
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            }
        }
    }

    public void deepFetch(int privilege) {
        deepFetch(privilege, 1);
    }

}
