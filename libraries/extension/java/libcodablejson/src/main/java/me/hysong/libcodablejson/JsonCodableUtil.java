package me.hysong.libcodablejson;

import com.google.gson.*;
import com.google.gson.reflect.TypeToken;

import java.lang.reflect.Field;
import java.util.List;
import java.util.Map;

public class JsonCodableUtil {
    public static final Gson gson = new Gson();

    public static JsonElement toJson(Object obj) {
        JsonObject jsonObject = new JsonObject();
        Class<?> clazz = obj.getClass();

        for (Field field : clazz.getDeclaredFields()) {
            field.setAccessible(true);
            if (!shouldProcessField(field)) {
                continue;
            }
            try {
                Object value = field.get(obj);
                String fieldName = getFieldName(field);
                boolean nullable = isNullable(field);

                if (value == null && !nullable) {
                    throw new JsonCodableException("Non-nullable field '" + field.getName() + "' is null during encoding");
                }

                addToJsonObject(jsonObject, fieldName, value);
            } catch (IllegalAccessException e) {
                throw new JsonCodableException("Error accessing field: " + field.getName());
            }
        }

        return jsonObject;
    }

    public static void fromJson(Object obj, JsonElement json) {
        JsonObject jsonObject = json.getAsJsonObject();
        Class<?> clazz = obj.getClass();

        for (Field field : clazz.getDeclaredFields()) {
            field.setAccessible(true);
            if (!shouldProcessField(field)) {
                continue;
            }
            try {
                String fieldName = getFieldName(field);
                boolean nullable = isNullable(field);

                if (!jsonObject.has(fieldName) || jsonObject.get(fieldName).isJsonNull()) {
                    if (!nullable) {
                        throw new JsonCodableException("Non-nullable field '" + field.getName() + "' is null or undefined in JSON");
                    }
                    continue;
                }

                Object value = getValueFromJsonElement(jsonObject.get(fieldName), field.getType());
                field.set(obj, value);
            } catch (IllegalAccessException e) {
                throw new JsonCodableException("Error accessing field: " + field.getName());
            }
        }
    }

    // Helper method to decide whether to process a field.
    private static boolean shouldProcessField(Field field) {
        return field.getDeclaringClass().isAnnotationPresent(Codable.class)
                || field.getDeclaringClass().isAnnotationPresent(Encodable.class)
                || field.getDeclaringClass().isAnnotationPresent(Decodable.class)
                || field.isAnnotationPresent(Codable.class)
                || field.isAnnotationPresent(Encodable.class)
                || field.isAnnotationPresent(Decodable.class);
    }

    // Modified to return the field name based on the field annotation or default to the field's name.
    private static String getFieldName(Field field) {
        if (field.isAnnotationPresent(Codable.class)) {
            String mapTo = field.getAnnotation(Codable.class).mapTo();
            if (!mapTo.isEmpty()) {
                return mapTo;
            }
        } else if (field.isAnnotationPresent(Encodable.class)) {
            String mapTo = field.getAnnotation(Encodable.class).mapTo();
            if (!mapTo.isEmpty()) {
                return mapTo;
            }
        } else if (field.isAnnotationPresent(Decodable.class)) {
            String mapTo = field.getAnnotation(Decodable.class).mapTo();
            if (!mapTo.isEmpty()) {
                return mapTo;
            }
        } else if (field.getDeclaringClass().isAnnotationPresent(Codable.class)) {
            // Class-level @Codable: use the field's name by default.
            return field.getName();
        }
        return field.getName();
    }

    // Modified to decide nullability based on field annotation or default behavior.
    private static boolean isNullable(Field field) {
        if (field.isAnnotationPresent(Codable.class)) {
            return field.getAnnotation(Codable.class).nullable();
        } else if (field.isAnnotationPresent(Encodable.class)) {
            return field.getAnnotation(Encodable.class).nullable();
        } else if (field.isAnnotationPresent(Decodable.class)) {
            return field.getAnnotation(Decodable.class).nullable();
        } else if (field.getDeclaringClass().isAnnotationPresent(Codable.class)) {
            // Default behavior for class-level annotation (adjust as needed).
            return true;
        }
        return true;
    }

    private static void addToJsonObject(JsonObject jsonObject, String fieldName, Object value) {
        if (value instanceof JsonCodable) {
            jsonObject.add(fieldName, ((JsonCodable) value).toJson());
        } else if (value instanceof List) {
            JsonArray jsonArray = new JsonArray();
            for (Object item : (List<?>) value) {
                jsonArray.add(gson.toJsonTree(item));
            }
            jsonObject.add(fieldName, jsonArray);
        } else if (value instanceof Map) {
            JsonObject mapObject = new JsonObject();
            for (Map.Entry<?, ?> entry : ((Map<?, ?>) value).entrySet()) {
                mapObject.add(entry.getKey().toString(), gson.toJsonTree(entry.getValue()));
            }
            jsonObject.add(fieldName, mapObject);
        } else {
            jsonObject.add(fieldName, gson.toJsonTree(value));
        }
    }

    private static Object getValueFromJsonElement(JsonElement element, Class<?> type) {
        if (JsonCodable.class.isAssignableFrom(type)) {
            try {
                JsonCodable instance = (JsonCodable) type.getDeclaredConstructor().newInstance();
                instance.fromJson(element);
                return instance;
            } catch (Exception e) {
                throw new JsonCodableException("Error creating instance of " + type.getName());
            }
        } else if (List.class.isAssignableFrom(type)) {
            return gson.fromJson(element, new TypeToken<List<?>>(){}.getType());
        } else if (Map.class.isAssignableFrom(type)) {
            return gson.fromJson(element, new TypeToken<Map<?, ?>>(){}.getType());
        } else {
            return gson.fromJson(element, type);
        }
    }

    public static String toJsonString(Object obj, boolean enableIndent) {
        JsonElement jsonElement = toJson(obj);
        if (!enableIndent) {
            return gson.toJson(jsonElement);
        } else {
            Gson prettyGson = new GsonBuilder().setPrettyPrinting().create();
            return prettyGson.toJson(jsonElement);
        }
    }
}
