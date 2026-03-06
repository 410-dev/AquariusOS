package me.hysong.libcodablejdbc;

import me.hysong.libcodablejdbc.utils.objects.DatabaseRecord;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

@Retention(RetentionPolicy.RUNTIME)
@Target({ElementType.FIELD})
public @interface ForeignKey {
    Class<? extends DatabaseRecord> type();
    String reference();
    boolean alwaysFetch() default false;
    String assignTo() default "";
}
