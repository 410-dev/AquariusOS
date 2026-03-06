package me.hysong.libcodablejdbc;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

@Retention(RetentionPolicy.RUNTIME)
@Target({ElementType.FIELD})
public @interface Column {
    String mapTo() default "";
    int minAccessLevel() default 0;
    int[] allowedAccessLevels() default {};
    int readMinAccessLevel() default 0;
    int[] readAllowedAccessLevels() default {};
    int writeMinAccessLevel() default 0;
    int[] writeAllowedAccessLevels() default {};
}
