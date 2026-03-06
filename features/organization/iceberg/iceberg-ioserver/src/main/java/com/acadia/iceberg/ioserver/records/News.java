package com.acadia.iceberg.ioserver.records;

import com.acadia.iceberg.ioserver.connections.CoreDatabaseFactory;
import me.hysong.libcodablejdbc.*;
import me.hysong.libcodablejdbc.Record;
import me.hysong.libcodablejdbc.utils.objects.DatabaseRecord;
import me.hysong.libcodablejson.Codable;
import me.hysong.libcodablejson.JsonCodable;

import java.util.ArrayList;

@Codable
@Record
@PrimaryKey(column = "id")
@Database(db = "iceberg", table = "news")
public class News extends DatabaseRecord implements JsonCodable {

    // 전처리 된 데이터
    private String uniqueId;
    private String topicTags;
    private String summary;
    private Long timeOfScrape;
    private Long timeOfFirstPartyPost;
    @ForeignKeyList(type = Person.class, reference = "id", assignTo = "peopleInvolved") private ArrayList<Integer> peopleInvolvedIds;
    @NotColumn private ArrayList<Person> peopleInvolved;
    private ArrayList<String> peopleNameCache;

    // Blob 데이터
    private ArrayList<String> fileIds;

    // 전처리 전 데이터
    private String rawHeadline;
    private String rawContent;
    private String newsSourceId;
    private String sourceURL;

    public News() {
        super(CoreDatabaseFactory.getConnection());
    }
}
