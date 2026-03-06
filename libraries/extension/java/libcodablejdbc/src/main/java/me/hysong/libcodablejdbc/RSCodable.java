package me.hysong.libcodablejdbc;

import com.google.gson.JsonParser;
//import me.hysong.libcodablejdbc.utils.objects.DbPtr;
import me.hysong.libcodablejdbc.utils.exceptions.InitializationViolationException;
import me.hysong.libcodablejdbc.utils.exceptions.JDBCReflectionGeneralException;
import me.hysong.libcodablejdbc.utils.exceptions.PseudoEnumValueNotPresentException;
import me.hysong.libcodablejdbc.utils.interfaces.DatabaseTableService;
import me.hysong.libcodablejdbc.utils.objects.DatabaseRecord;
import me.hysong.libcodablejdbc.utils.objects.SearchExpression;
import me.hysong.libcodablejson.JsonCodable;

import java.io.IOException;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.math.BigDecimal;
import java.sql.*;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.*;

public interface RSCodable {

    default void objectifyCurrentRow(int privilege, ResultSet rs) {
        Field[] fields = this.getClass().getDeclaredFields();

        for (Field field : fields) {
            if (!RSCodableUtil.isMarkedMappingElement(field)) {
                continue;
            }

            final String columnName = RSCodableUtil.getFieldNameInDB(field);
            final Class<?> fieldType = field.getType();

            try {
                // Skip if the column doesn't exist in the ResultSet
                rs.findColumn(columnName);
            } catch (SQLException missing) {
                // Column not present in this query — skip gracefully
                continue;
            }

            try {
                field.setAccessible(true);
                Object value = null;

                // --- Type-targeted extraction (NULL-safe where relevant) ---
                if (fieldType == String.class) {
                    value = rs.getString(columnName);

                } else if (fieldType == int.class || fieldType == Integer.class) {
                    int v = rs.getInt(columnName);
                    value = rs.wasNull() ? (fieldType.isPrimitive() ? 0 : null) : v;

                } else if (fieldType == long.class || fieldType == Long.class) {
                    long v = rs.getLong(columnName);
                    value = rs.wasNull() ? (fieldType.isPrimitive() ? 0L : null) : v;

                } else if (fieldType == short.class || fieldType == Short.class) {
                    short v = rs.getShort(columnName);
                    value = rs.wasNull() ? (fieldType.isPrimitive() ? (short)0 : null) : v;

                } else if (fieldType == byte.class || fieldType == Byte.class) {
                    byte v = rs.getByte(columnName);
                    value = rs.wasNull() ? (fieldType.isPrimitive() ? (byte)0 : null) : v;

                } else if (fieldType == double.class || fieldType == Double.class) {
                    double v = rs.getDouble(columnName);
                    value = rs.wasNull() ? (fieldType.isPrimitive() ? 0d : null) : v;

                } else if (fieldType == float.class || fieldType == Float.class) {
                    float v = rs.getFloat(columnName);
                    value = rs.wasNull() ? (fieldType.isPrimitive() ? 0f : null) : v;

                } else if (fieldType == boolean.class || fieldType == Boolean.class) {
                    boolean v = rs.getBoolean(columnName);
                    value = rs.wasNull() ? (fieldType.isPrimitive() ? false : null) : v;

                } else if (fieldType == byte[].class) {
                    value = rs.getBytes(columnName);

                } else if (fieldType == int[].class || fieldType == Integer[].class) {
                    Array sqlArray = rs.getArray(columnName);
                    if (sqlArray != null) {
                        Object arr = sqlArray.getArray();
                        if (arr instanceof int[]) {
                            value = arr;
                        } else if (arr instanceof Integer[]) {
                            value = arr;
                        } else if (arr instanceof Object[]) {
                            Object[] objArr = (Object[]) arr;
                            Integer[] intArr = new Integer[objArr.length];
                            for (int i = 0; i < objArr.length; i++) {
                                intArr[i] = (objArr[i] != null) ? ((Number) objArr[i]).intValue() : null;
                            }
                            value = intArr;
                        }
                    }
                } else if (fieldType == long[].class || fieldType == Long[].class) {
                    Array sqlArray = rs.getArray(columnName);
                    if (sqlArray != null) {
                        Object arr = sqlArray.getArray();
                        if (arr instanceof long[]) {
                            value = arr;
                        } else if (arr instanceof Long[]) {
                            value = arr;
                        } else if (arr instanceof Object[]) {
                            Object[] objArr = (Object[]) arr;
                            Long[] longArr = new Long[objArr.length];
                            for (int i = 0; i < objArr.length; i++) {
                                longArr[i] = (objArr[i] != null) ? ((Number) objArr[i]).longValue() : null;
                            }
                            value = longArr;
                        }
                    }
                } else if (fieldType == short[].class || fieldType == Short[].class) {
                    Array sqlArray = rs.getArray(columnName);
                    if (sqlArray != null) {
                        Object arr = sqlArray.getArray();
                        if (arr instanceof short[]) {
                            value = arr;
                        } else if (arr instanceof Short[]) {
                            value = arr;
                        } else if (arr instanceof Object[]) {
                            Object[] objArr = (Object[]) arr;
                            Short[] shortArr = new Short[objArr.length];
                            for (int i = 0; i < objArr.length; i++) {
                                shortArr[i] = (objArr[i] != null) ? ((Number) objArr[i]).shortValue() : null;
                            }
                            value = shortArr;
                        }
                    }
                } else if (fieldType == double[].class || fieldType == Double[].class) {
                    Array sqlArray = rs.getArray(columnName);
                    if (sqlArray != null) {
                        Object arr = sqlArray.getArray();
                        if (arr instanceof double[]) {
                            value = arr;
                        } else if (arr instanceof Double[]) {
                            value = arr;
                        } else if (arr instanceof Object[]) {
                            Object[] objArr = (Object[]) arr;
                            Double[] doubleArr = new Double[objArr.length];
                            for (int i = 0; i < objArr.length; i++) {
                                doubleArr[i] = (objArr[i] != null) ? ((Number) objArr[i]).doubleValue() : null;
                            }
                            value = doubleArr;
                        }
                    }
                } else if (fieldType == float[].class || fieldType == Float[].class) {
                    Array sqlArray = rs.getArray(columnName);
                    if (sqlArray != null) {
                        Object arr = sqlArray.getArray();
                        if (arr instanceof float[]) {
                            value = arr;
                        } else if (arr instanceof Float[]) {
                            value = arr;
                        } else if (arr instanceof Object[]) {
                            Object[] objArr = (Object[]) arr;
                            Float[] floatArr = new Float[objArr.length];
                            for (int i = 0; i < objArr.length; i++) {
                                floatArr[i] = (objArr[i] != null) ? ((Number) objArr[i]).floatValue() : null;
                            }
                            value = floatArr;
                        }
                    }

                } else if (fieldType == char.class || fieldType == Character.class) {
                    String s = rs.getString(columnName);
                    if (s != null && !s.isEmpty()) {
                        value = s.charAt(0);
                    } else {
                        value = fieldType.isPrimitive() ? '\u0000' : null;
                    }

                } else if (fieldType == boolean[].class || fieldType == Boolean[].class) {
                    Array sqlArray = rs.getArray(columnName);
                    if (sqlArray != null) {
                        Object arr = sqlArray.getArray();
                        if (arr instanceof boolean[]) {
                            value = arr;
                        } else if (arr instanceof Boolean[]) {
                            value = arr;
                        } else if (arr instanceof Object[]) {
                            Object[] objArr = (Object[]) arr;
                            Boolean[] boolArr = new Boolean[objArr.length];
                            for (int i = 0; i < objArr.length; i++) {
                                boolArr[i] = (objArr[i] != null) ? (Boolean) objArr[i] : null;
                            }
                            value = boolArr;
                        }
                    }
                } else if (fieldType == java.math.BigDecimal.class) {
                    value = rs.getBigDecimal(columnName);

                } else if (fieldType == java.math.BigInteger.class) {
                    String s = rs.getString(columnName);
                    value = (s == null) ? null : new java.math.BigInteger(s);

                } else if (fieldType == java.util.Date.class) {
                    java.sql.Timestamp ts = rs.getTimestamp(columnName);
                    value = (ts == null) ? null : new java.util.Date(ts.getTime());

                } else if (fieldType == java.sql.Date.class) {
                    value = rs.getDate(columnName);

                } else if (fieldType == java.sql.Time.class) {
                    value = rs.getTime(columnName);

                } else if (fieldType == java.sql.Timestamp.class) {
                    value = rs.getTimestamp(columnName);

                } else if (fieldType == java.time.LocalDate.class) {
                    java.sql.Date d = rs.getDate(columnName);
                    value = (d == null) ? null : d.toLocalDate();

                } else if (fieldType == java.time.LocalTime.class) {
                    java.sql.Time t = rs.getTime(columnName);
                    value = (t == null) ? null : t.toLocalTime();

                } else if (fieldType == java.time.LocalDateTime.class) {
                    java.sql.Timestamp ts = rs.getTimestamp(columnName);
                    value = (ts == null) ? null : ts.toLocalDateTime();

                } else if (fieldType == java.time.OffsetDateTime.class) {
                    // Best effort: try JDBC 4.2 typed getObject; fallback to ISO-8601 text
                    try {
                        value = rs.getObject(columnName, java.time.OffsetDateTime.class);
                    } catch (Throwable ignore) {
                        String s = rs.getString(columnName);
                        value = (s == null) ? null : java.time.OffsetDateTime.parse(s);
                    }

                } else if (fieldType == java.util.UUID.class) {
                    try {
                        value = rs.getObject(columnName, java.util.UUID.class);
                    } catch (Throwable ignore) {
                        String s = rs.getString(columnName);
                        value = (s == null) ? null : java.util.UUID.fromString(s);
                    }

                } else if (field.isAnnotationPresent(PseudoEnum.class)) {
                    PseudoEnum enumValue = field.getAnnotation(PseudoEnum.class);
                    String[] accepts = enumValue.accepts();
                    String valueNow = null;
                    try {
                        valueNow = rs.getString(columnName);
                    } catch (Throwable e) {
                        e.printStackTrace();
                    }
                    if (valueNow == null) {
                        if (!enumValue.nullable()) {
                            throw new NullPointerException("Non-nullable field has null value returned.");
                        } else {
                            continue;
                        }
                    } else if (Arrays.asList(accepts).contains(valueNow) || enumValue.noStrict()) {
                        value = valueNow;
                    } else {
                        throw new PseudoEnumValueNotPresentException("Value '" + valueNow + "' is not in " + Arrays.toString(accepts));
                    }

                } else if (fieldType.isEnum()) {
                    // Prefer string name; if null, try ordinal
                    String name = rs.getString(columnName);
                    if (name != null) {
                        value = Enum.valueOf((Class<? extends Enum>) fieldType.asSubclass(Enum.class), name);
                    } else {
                        int ord = rs.getInt(columnName);
                        if (!rs.wasNull()) {
                            Object[] constants = fieldType.getEnumConstants();
                            if (ord >= 0 && ord < constants.length) {
                                value = constants[ord];
                            }
                        }
                    }
                } else if (fieldType.isAssignableFrom(CompositionObject.class)) {
                    // Composition Object
                    try {
                        CompositionObject co = (CompositionObject) fieldType.getConstructor().newInstance();
                        String prefix = field.getName() + "_";
                        String[] keys = co.compositionKeys();
                        LinkedHashMap<String, Object> map = new LinkedHashMap<>();
                        for (String key : keys) {
                            Object v = rs.getObject(prefix + key);
                            map.put(key, v);
                        }
                        co.setPrefix(prefix);
                        co.compose(map);
                        value = co;
                    } catch (Throwable e) {
                        e.printStackTrace();
                    }

//                } else if (fieldType == DbPtr.class) {
//                    // Database Pointer. Keep the pointer only.


                } else if (fieldType.isAssignableFrom(JsonCodable.class)) {
                    // Decode back to java object
                    try {
                        String rawJson = rs.getString(columnName);
                        JsonCodable jc = (JsonCodable) (fieldType.getConstructor().newInstance());
                        jc.fromJson(JsonParser.parseString(rawJson));

                    } catch (Throwable ignore) {
                        String s = rs.getString(columnName);
                        value = (s == null) ? null : java.util.UUID.fromString(s);
                    }
                } else {
                    // Last resort: JDBC 4.2 typed getObject; if unsupported, plain getObject
                    try {
                        value = rs.getObject(columnName, fieldType);
                    } catch (Throwable ignore) {
                        value = rs.getObject(columnName);
                    }
                }

                // If field has @ForeignKey annotation, fetch it if it is specified
                if (field.isAnnotationPresent(ForeignKey.class)) {
                    ForeignKey fk = field.getAnnotation(ForeignKey.class);
                    if (fk.alwaysFetch() && value != null && fk.assignTo() != null && !fk.assignTo().isEmpty()) {
                        try {
                            // Fetch the referenced record
                            Class<? extends DatabaseRecord> fkType = fk.type();
                            String referenceColumn = fk.reference();

                            // Build search expressions
                            SearchExpression[] expressions = new SearchExpression[1];
                            expressions[0] = new SearchExpression()
                                    .column(referenceColumn)
                                    .isEqualTo(value);

                            // Execute search
                            DatabaseRecord referencedRecord = fk.type().getDeclaredConstructor(DatabaseTableService.class).newInstance(((DatabaseRecord) this).getController());
                            LinkedHashMap<Object, DatabaseRecord> result = ((DatabaseRecord) this).getController().searchBy(privilege, referencedRecord, 0, 1, expressions);
                            if (result != null && !result.isEmpty()) {
                                DatabaseRecord fetchedRecord = result.values().iterator().next();
                                // Assign to the specified field
                                Field assignField = this.getClass().getDeclaredField(fk.assignTo());
                                assignField.setAccessible(true);
                                assignField.set(this, fetchedRecord);
                            }

                        // Fetch failure should not block main assignment
                        } catch (Exception e) {
                            e.printStackTrace();
                        }
                    }
                } else if (field.isAnnotationPresent(ForeignKeyList.class)) {
                    ForeignKeyList fkl = field.getAnnotation(ForeignKeyList.class);
                    if (fkl.alwaysFetch() && value != null && fkl.assignTo() != null && !fkl.assignTo().isEmpty()) {
                        try {
                            // Fetch the referenced records
                            Class<? extends DatabaseRecord> fkType = fkl.type();
                            String referenceColumn = fkl.reference(); // usually "id"
                            String assignToFieldName = fkl.assignTo();

                            // Expect the value to be an array of IDs
                            ArrayList<Object> idList = new ArrayList<>();
                            switch (value) {
                                case Object[] objects -> idList = new ArrayList<>(Arrays.asList(objects));
                                case int[] ints -> {
                                    for (int id : ints) {
                                        idList.add(id);
                                    }
                                }
                                case long[] longs -> {
                                    for (long id : longs) {
                                        idList.add(id);
                                    }
                                }
                                default ->
                                        throw new IllegalArgumentException("ForeignKeyList field value is not an array type.");
                            }

                            // Fetch all records matching any of the IDs
                            for (Object id : idList) {
                                SearchExpression[] expressions = new SearchExpression[1];
                                expressions[0] = new SearchExpression()
                                        .column(referenceColumn)
                                        .isEqualTo(id);

                                // Execute search
                                DatabaseRecord referencedRecord = fkl.type().getDeclaredConstructor(DatabaseTableService.class).newInstance(((DatabaseRecord) this).getController());
                                LinkedHashMap<Object, DatabaseRecord> result = ((DatabaseRecord) this).getController().searchBy(privilege, referencedRecord, 0, 1, expressions);
                                if (result != null && !result.isEmpty()) {
                                    DatabaseRecord fetchedRecord = result.values().iterator().next();
                                    // Assign to the specified field
                                    Field assignField = this.getClass().getDeclaredField(fkl.assignTo());
                                    assignField.setAccessible(true);

                                    // If the target field is a collection, add to it
                                    Object currentCollection = assignField.get(this);
                                    if (currentCollection == null) {
                                        if (assignField.getType() == ArrayList.class) {
                                            currentCollection = new ArrayList<>();
                                            assignField.set(this, currentCollection);
                                        } else {
                                            throw new IllegalArgumentException("ForeignKeyList assignTo field is not an ArrayList.");
                                        }
                                    }
                                    try {
                                        if (currentCollection instanceof ArrayList list) {
                                            list.add(fetchedRecord);
                                        } else {
                                            throw new IllegalArgumentException("ForeignKeyList assignTo field is not an ArrayList.");
                                        }
                                    } catch (Exception e) {
                                        throw new IllegalArgumentException("ForeignKeyList assignTo field seems not an ArrayList.", e);
                                    }
                                }
                            }

                        // Fetch failure should not block main assignment
                        } catch (Exception e) {
                            e.printStackTrace();
                        }
                    }
                }

                // Assign if not null OR field is primitive (needs a default already handled)
                if (value != null || fieldType.isPrimitive()) {
                    field.set(this, value);
                }

            } catch (SQLException e) {
                throw new RuntimeException("Failed to read column '" + columnName + "' from ResultSet", e);
            } catch (IllegalAccessException | IllegalArgumentException e) {
                throw new RuntimeException("Failed to set field '" + field.getName() + "' on " + this.getClass().getName(), e);
            }
        }
    }


}
