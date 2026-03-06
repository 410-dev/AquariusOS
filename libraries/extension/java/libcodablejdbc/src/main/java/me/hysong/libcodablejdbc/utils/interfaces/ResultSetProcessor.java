package me.hysong.libcodablejdbc.utils.interfaces;

import me.hysong.libcodablejdbc.utils.exceptions.InitializationViolationException;
import me.hysong.libcodablejdbc.utils.exceptions.JDBCReflectionGeneralException;

import java.sql.ResultSet;
import java.sql.SQLException;

@FunctionalInterface
public interface ResultSetProcessor<T> {
    T process(ResultSet rs) throws SQLException, JDBCReflectionGeneralException, InitializationViolationException;
}
