package me.hysong.libcodablejson;

import java.util.HashMap;

@Codable
public class JsonCodableExampleTestClass implements JsonCodable {
    private String name;
    private String description;
    private int age;
    private boolean isCool;
    private JsonCodableExampleTestClass self;
    private HashMap<String, String> map = new HashMap<>();

    public static void main(String[] args) {
        JsonCodableExampleTestClass test = new JsonCodableExampleTestClass();
        test.name = "Test";
        test.description = "This is a test";
        test.age = 20;
        test.isCool = true;
        test.map.put("key", "value");

        JsonCodableExampleTestClass self = new JsonCodableExampleTestClass();
        self.name = "Self";
        self.description = "This is a self test";
        self.age = 21;
        self.isCool = false;
        self.self = test;


        System.out.println(self.toJsonString());

        test = new JsonCodableExampleTestClass();
        test.fromJson(self.toJson());

        System.out.println(test.toJsonString());
    }
}
