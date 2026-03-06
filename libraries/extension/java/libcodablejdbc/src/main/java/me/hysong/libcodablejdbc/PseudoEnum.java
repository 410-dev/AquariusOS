package me.hysong.libcodablejdbc;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

@Retention(RetentionPolicy.RUNTIME)
@Target({ElementType.FIELD})
public @interface PseudoEnum {
    String[] accepts() default {};
    boolean nullable() default true;
    boolean noStrict() default false;
}
