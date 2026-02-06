plugins {
    id("java")
    id("application")
}

group = "me.hysong"
version = "1.0"

repositories {
    mavenCentral()
}

dependencies {
    testImplementation(platform("org.junit:junit-bom:5.10.0"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    compileOnly("org.projectlombok:lombok:1.18.36")
    annotationProcessor("org.projectlombok:lombok:1.18.36")
    testCompileOnly("org.projectlombok:lombok:1.18.36")
    testAnnotationProcessor("org.projectlombok:lombok:1.18.36")
}

application {
    mainClass = "me.hysong.aqua.AdministrationControlEditor"
}

tasks.test {
    useJUnitPlatform()
}

tasks.jar {
    archiveBaseName.set(project.name)
    archiveVersion.set("")
    archiveClassifier.set("")

    destinationDirectory.set(file("./"))

    manifest {
        attributes(
            "Main-Class" to "me.hysong.aqua.AdministrationControlEditor",
            "Implementation-Title" to project.name,
            "Implementation-Version" to project.version
        )
    }
}

tasks.named("build") {
    dependsOn(tasks.named("jar"))
}