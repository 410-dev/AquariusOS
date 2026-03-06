package me.hysong.libcodablejdbc.dev_example;

import lombok.Getter;
import me.hysong.libcodablejdbc.Database;
import me.hysong.libcodablejdbc.PrimaryKey;
import me.hysong.libcodablejdbc.Column;
import me.hysong.libcodablejdbc.Record;
import me.hysong.libcodablejdbc.utils.objects.DatabaseRecord;

@Getter
@Record // This applies @Column at all fields with its name. Name mapping will prioritize @Column(mapTo=xxx).
@Database(db="unitable", table="users")
@PrimaryKey(column="email") // Explicitly specify
public class ExampleUser extends DatabaseRecord {

    /*
    Database example
    - id  : Integer, AUTO_INCREMENT          (Automatically mapped)
    - name: Text                             (Manually mapped with realName field using @Column annotation)
    - email: Text, PK                        (Automatically mapped)
    - age: Integer                           (Automatically mapped)
     */

    private int id = -1;
    @Column(mapTo = "name") private String realName = "John Appleseed";
    private String email = "john@apple.com";
    private String password = "";
    private int age = 23;

    public ExampleUser() {
        super(new LocalSQLTableServiceSample()); // .update() .select() etc... functions will use this controller
    }

    public String toString() {
        return "User(id=" + id + ", name=" + realName + ", email=" + email + ", password=" + password + ", age=" + age + ")";
    }

    public static void main(String[] args) throws Exception {
        String email = "admin@default.com";
        ExampleUser o = new ExampleUser();
        o.setPrimaryKeyValue(email);   // .select() will use PK to search
        o.select(0);                    // Load result to object
        System.out.println(o);
    }
}


