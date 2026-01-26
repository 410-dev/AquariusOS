
plugins {
    id("java")
    id("application") // to declare main class
    id("com.gradleup.shadow") version "9.3.1" // fat jar
    id("war") // WAR packaging
}

group = "me.hysong.aqua"
version = "1.0-SNAPSHOT"

repositories {
    mavenCentral()
}

dependencies {
    // Unit testing
    testImplementation(platform("org.junit:junit-bom:5.10.0"))
    testImplementation("org.junit.jupiter:junit-jupiter")

    // Proprietary libraries
    implementationFirstAvailable("../../../libraries/extension/java/libcodablejson/libcodablejson.jar", "../../../libraries/extension/java/libcodablejson.jar")
    implementationFirstAvailable("../../../libraries/extension/java/libcodablejdbc/libcodablejdbc.jar", "../../../libraries/extension/java/libcodablejdbc.jar")

    // JSON + Database
    implementation("com.google.code.gson:gson:2.12.1")
    implementation("org.mariadb.jdbc:mariadb-java-client:3.4.1")

    // Lombok
    compileOnly("org.projectlombok:lombok:1.18.42")
    annotationProcessor("org.projectlombok:lombok:1.18.42")
    testCompileOnly("org.projectlombok:lombok:1.18.42")
    testAnnotationProcessor("org.projectlombok:lombok:1.18.42")

    // Jetty (only needed for runnable JAR)
    implementation("org.eclipse.jetty:jetty-server:12.1.1")
    implementation("org.eclipse.jetty.ee10:jetty-ee10-webapp:12.1.1")
    implementation("org.eclipse.jetty.ee10:jetty-ee10-servlet:12.1.1")

    // Reflections
    implementation("org.reflections:reflections:0.10.2")

    // https://mvnrepository.com/artifact/com.zaxxer/HikariCP
    implementation("com.zaxxer:HikariCP:7.0.2")

    // Servlet API (provided by Tomcat when deploying WAR)
    compileOnly("jakarta.servlet:jakarta.servlet-api:6.1.0")
}

application {
    // Your entry point for Jetty runnable JAR
    mainClass.set("me.hysong.aqua.domaincontroller.Application")
}

tasks.test {
    useJUnitPlatform()
}

// Configure shadowJar (fat JAR with embedded Jetty)
tasks.shadowJar {
    manifest {
        attributes(
            "Implementation-Title" to project.name,
            "Implementation-Version" to project.version,
            "Main-Class" to application.mainClass.get()
        )
    }
    archiveFileName.set("server.local.jar")
    archiveClassifier.set("")
    destinationDirectory.set(file("./"))
    mergeServiceFiles()
}

fun DependencyHandlerScope.implementationFirstAvailable(vararg paths: String) {
    val foundFile = paths
        .map { project.file(it) }
        .firstOrNull { it.exists() }
    if (foundFile != null) {
        add("implementation", files(foundFile))
        logger.lifecycle("Dependency resolved: ${foundFile.path}")
    } else {
        logger.warn("Warning: No valid jar found for candidates: ${paths.contentToString()}")
    }
}

// Default build will produce both JAR and WAR
tasks.named("build") {
    dependsOn(tasks.named("shadowJar"))
}
