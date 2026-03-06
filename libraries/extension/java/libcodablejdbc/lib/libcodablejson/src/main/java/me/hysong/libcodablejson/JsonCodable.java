package me.hysong.libcodablejson;

import com.google.gson.JsonElement;

public interface JsonCodable {
    default JsonElement toJson() {
        return JsonCodableUtil.toJson(this);
    }

    default void fromJson(JsonElement json) {
        JsonCodableUtil.fromJson(this, json);
    }

    default String toJsonString() {
        return JsonCodableUtil.toJsonString(this, false);
    }

    default String toIndentedJsonString() {
        return JsonCodableUtil.toJsonString(this, true);
    }
}
