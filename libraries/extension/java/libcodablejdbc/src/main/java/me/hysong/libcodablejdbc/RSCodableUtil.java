package me.hysong.libcodablejdbc;

import java.lang.annotation.Annotation;
import java.lang.reflect.Field;

public class RSCodableUtil {
    public static boolean isMarkedMappingElement(Field f) {
        return (f.getDeclaringClass().isAnnotationPresent(Record.class) && !f.isAnnotationPresent(NotColumn.class))
                || f.isAnnotationPresent(Column.class);
    }

    public static String getFieldNameInDB(Field f) {
        if (f.isAnnotationPresent(Column.class)) {
            Column column = f.getAnnotation(Column.class);
            return column.mapTo().isEmpty() ? f.getName() : column.mapTo();
        }else if (f.getDeclaringClass().isAnnotationPresent(Record.class) && !f.isAnnotationPresent(NotColumn.class)) {
            return f.getName();
        }
        return null;
    }

    public static String mapJavaTypeToSQLType(Class<?> type) {
        if (type == int.class || type == Integer.class || type == boolean.class || type == Boolean.class) {
            return "INTEGER";
        } else if (type == long.class || type == Long.class) {
            return "BIGINT";
        } else if (type == float.class || type == Float.class) {
            return "FLOAT";
        } else if (type == double.class || type == Double.class) {
            return "DOUBLE";
        } else if (type == String.class) {
            return "TEXT";
        } else if (type == byte[].class) {
            return "BLOB";
        } else if (java.util.List.class.isAssignableFrom(type) || java.util.Map.class.isAssignableFrom(type)) {
            return "TEXT"; // Store lists and maps as JSON text
        } else {
            return "TEXT"; // Default to TEXT for other unknown types
        }
    }
}
