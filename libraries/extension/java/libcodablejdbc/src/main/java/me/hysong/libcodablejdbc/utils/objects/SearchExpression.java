package me.hysong.libcodablejdbc.utils.objects;

import lombok.Getter;

@Getter
public class SearchExpression {
    private String column;
    private Object value;
    private boolean or;
    private boolean and;
    private boolean negate = false;
    private boolean startsWith = false;
    private boolean endsWith = false;
    private Object[] in = new Object[0];

    public SearchExpression column(String column) {
        this.column = column;
        return this;
    }

    public SearchExpression not() {
        this.negate = true;
        return this;
    }

    public SearchExpression startsWith(String value) {
        this.value = value;
        startsWith = true;
        return this;
    }

    public SearchExpression endsWith(String value) {
        this.value = value;
        endsWith = true;
        return this;
    }

    public SearchExpression contains(String value) {
        this.value = value;
        startsWith = true;
        endsWith = true;
        return this;
    }

    public SearchExpression is(Object value) {
        this.value = value;
        return this;
    }

    public SearchExpression isEqualTo(Object value) {
        this.value = value;
        return this;
    }

    public SearchExpression or() {
        this.or = true;
        this.and = false;
        return this;
    }

    public SearchExpression and() {
        this.and = true;
        this.or = false;
        return this;
    }

    public SearchExpression in(Object[] values) {
        this.in = values;
        return this;
    }
}
