package com.acadia.iceberg.ioserver.records;

import com.acadia.iceberg.ioserver.connections.CoreDatabaseFactory;
import me.hysong.libcodablejdbc.*;
import me.hysong.libcodablejdbc.Record;
import me.hysong.libcodablejdbc.utils.interfaces.DatabaseTableService;
import me.hysong.libcodablejdbc.utils.objects.DatabaseRecord;
import me.hysong.libcodablejson.Codable;
import me.hysong.libcodablejson.JsonCodable;

import java.util.ArrayList;
import java.util.HashMap;

@Codable
@Record
@PrimaryKey(column = "id")
@Database(db = "iceberg", table = "people")
public class Person extends DatabaseRecord implements JsonCodable {

    private String fullName;
    private String firstName;
    private String middleName;
    private String lastName;
    private String serializedName;
    private ArrayList<String> multilingualName;
    private ArrayList<String> picturePaths;
    private ArrayList<String> tags;
    private HashMap<String, Double> impactVectors;

    public Person() {
        super(CoreDatabaseFactory.getConnection());
    }
}
