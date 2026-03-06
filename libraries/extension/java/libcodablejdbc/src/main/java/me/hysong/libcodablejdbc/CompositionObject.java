package me.hysong.libcodablejdbc;

import lombok.Getter;
import lombok.Setter;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;

public abstract class CompositionObject {
    @Getter @Setter private String prefix;
    public abstract LinkedHashMap<String, Object> decompose();
    public abstract void compose(LinkedHashMap<String, Object> fromMap);
    public abstract String[] compositionKeys();
}
