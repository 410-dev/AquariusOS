# libcodablejdbc

libcodablejdbc is a lightweight, annotation-driven JDBC ORM (Object-Relational Mapping) library for Java. It simplifies database interactions by mapping Java objects directly to database tables, managing SQL generation, and handling complex relationships like foreign keys and JSON serialization transparently.

### Example
```java
@Encodable                                      // Json encodable
@Record                                         // This class is a database table, and this object is a record
@Database(db = "my-service", table = "users")   // Database connection
@PrimaryKey(column="id")                        // Primary key of this table
@Accessors(chain = true)                        // Project Lombok's annotation to enable method chaining
public class User extends DatabaseRecord implements JsonCodable {

    @Automatic private int id;          // Auto Increment
    private String email;               // PK
    private String password;
    private String fullName;

    @Column(mapTo = "name")
    private String userDisplayName;     // Force mapping to column 'name'

    public User() {
        super(new MyDatabaseProvider());
    }

    
    public static void main(String[] args) throws Exception {
        // Example of inserting new object to database
        new User().setEmail("user@example.com").setDisplayName("John Smith").insert();

        // Example of searching the object from database
        LinkedHashMap<Object, DatabaseRecord> results = new User().setPrimaryKeyValue(3).select(0); // Search by id = 3
        // or
        LinkedHashMap<Object, DatabaseRecord> results = new User().setEmail("user@example.com").selectBy(0, "email"); // Search by email
    }
}
```
## Features

* **Annotation-Driven Mapping**: Configuration via `@Database`, `@Record`, `@Column`, and `@PrimaryKey`.
* **Automated CRUD**: Built-in support for `SELECT`, `INSERT`, `UPDATE`, and `DELETE` operations.
* **Relationship Management**: Automatic handling of Foreign Keys (`@ForeignKey`) and lists of references (`@ForeignKeyList`) with "Deep Fetch" capabilities.
* **Granular Access Control**: Built-in privilege system to restrict read/write access to specific columns based on user levels.
* **Fluent Search API**: Programmatic query construction using `SearchExpression`.
* **JSON Support**: Automatically serializes/deserializes `List`, `Map`, and custom `JsonCodable` objects to/from JSON strings in the database.
* **Composition Objects**: Support for flattening complex objects into multiple columns using `CompositionObject`.

## Requirements

* **Java**: JDK 25 (as configured in `build.gradle.kts`)
* **Build System**: Gradle
* **Database**: Supports SQL databases (tested with MariaDB/MySQL via `MySQLTableServiceTemplate`).

## Installation

Clone the repository and build using Gradle:

```bash
git clone https://github.com/your-username/libcodablejdbc.git --recurse-submodules
cd libcodablejdbc
./gradlew build
```

## Getting Started

### 1. Implement the Database Service

You need to tell the library how to connect to your database by implementing the `MySQLTableServiceTemplate` (or `DatabaseTableService`) interface.

#### Basic Implementation (Development)
For simple testing, you can use `DriverManager` directly:

```java
import me.hysong.libcodablejdbc.utils.dbtemplates.MySQLTableServiceTemplate;
import java.sql.*;

public class MyTableService implements MySQLTableServiceTemplate {
    private static Connection con;

    @Override
    public Connection getConnection(String database) throws SQLException {
        String url = "jdbc:mariadb://localhost:3306/" + database;
        if (con == null || con.isClosed()) {
            con = DriverManager.getConnection(url, "root", "password");
        }
        return con;
    }
}
```

#### Production Implementation (HikariCP)
For production environments, it is **highly recommended** to use a connection pool like [HikariCP](https://github.com/brettwooldridge/HikariCP) to manage database connections efficiently.

### 2. Define a Model (Record)

Create a class extending `DatabaseRecord`. Use annotations to map the class to a table and its fields to columns.

```java
import lombok.Getter;
import lombok.Setter;
import me.hysong.libcodablejdbc.*;
import me.hysong.libcodablejdbc.utils.objects.DatabaseRecord;

@Getter
@Setter
@Record
@Database(db = "my_app_db", table = "users")
@PrimaryKey(column = "email")
public class User extends DatabaseRecord {

    @Automatic // Auto-increment column
    private int id = -1;

    @Column(mapTo = "full_name") // Map to a specific column name
    private String name;

    @Column // Automatically maps to "email"
    private String email;
    
    // Access control: Only strictly privileged users (level 0) can read/write this
    @Column(minAccessLevel = 0) 
    private String password;

    private int age;

    // Required: Constructor calling super with your TableService
    public User() {
        super(new ProductionTableService());
    }
}
```

### 3. Perform Database Operations

```java
public class Main {
    public static void main(String[] args) throws Exception {
        
        // --- Insert ---
        User newUser = new User();
        newUser.setEmail("john@example.com");
        newUser.setName("John Doe");
        newUser.setAge(25);
        newUser.insert();

        // --- Select (by Primary Key) ---
        User user = new User();
        user.setPrimaryKeyValue("john@example.com");
        user.select(0); // 0 is the privilege level
        System.out.println("Fetched: " + user.getName());

        // --- Update ---
        user.setAge(26);
        user.update(0);

        // --- Search ---
        SearchExpression[] search = {
            new SearchExpression().column("age").is(26),
            new SearchExpression().column("name").contains("John").and()
        };
        
        var results = user.searchBy(0, user, 0, 10, search);
        
        // --- Delete ---
        user.delete();
    }
}
```

## Annotation Reference

| Annotation | Target | Description |
| :--- | :--- | :--- |
| `@Record` | Class | Marks the class as a database record. |
| `@Database` | Class | Specifies the database name (`db`) and table name (`table`). |
| `@PrimaryKey` | Class | Defines which column is the Primary Key. |
| `@Column` | Field | Configures column mapping, including `mapTo` (name), `minAccessLevel` (security), and read/write permissions. |
| `@Automatic` | Field | Marks a field as `AUTO_INCREMENT` or DB-generated. Excluded from `INSERT` statements. |
| `@NotColumn` | Field | Explicitly excludes a field from being mapped to the database. |
| `@ForeignKey` | Field | Links a field to another `DatabaseRecord`. Supports `alwaysFetch` and `assignTo` for auto-retrieval. |
| `@ForeignKeyList`| Field | Links a list of IDs to a list of `DatabaseRecord` objects. |
| `@PseudoEnum` | Field | Enforces strict string validation against an `accepts` list. |

## Advanced Features

### Deep Fetching (Foreign Keys)
If you have a relationship defined via `@ForeignKey` or `@ForeignKeyList`, you can automatically retrieve the related objects.

```java
// Recursively fetch related objects up to 2 levels deep
user.deepFetch(privilegeLevel, 2);
```

### Composition Objects
You can flatten complex objects into the parent table using `CompositionObject`.

1. Extend `CompositionObject`.
2. Implement `decompose()` (Object -> Map) and `compose()` (Map -> Object).
3. The library will store fields as `prefix_fieldName` in the parent table.

## Project Structure

* `src/main/java/me/hysong/libcodablejdbc` - Core library source.
* `.../utils/objects/DatabaseRecord.java` - The base class for all entities.
* `.../utils/dbtemplates/MySQLTableServiceTemplate.java` - Default MySQL/MariaDB implementation.
* `.../dev_example/` - Example code demonstrating usage.
