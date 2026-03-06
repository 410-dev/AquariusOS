package me.hysong.libcodablejdbc.utils.exceptions;

public class JDBCReflectionGeneralException extends Exception {
    public JDBCReflectionGeneralException(String message) {
        super(message);
    }

    public JDBCReflectionGeneralException(Exception e) {
        super(e);
    }

    public JDBCReflectionGeneralException(String s, ReflectiveOperationException e) {
        super(s, e);
    }
}
