
plugins {
    id("java")
    id("application") // to declare main class
    id("com.gradleup.shadow") version "9.3.1" // fat jar
    id("war") // WAR packaging
}

group = "com.aqua.oscore"
version = "1.0"

repositories {
    mavenCentral()
}

dependencies {
    // Unit testing
    testImplementation(platform("org.junit:junit-bom:5.10.0"))
    testImplementation("org.junit.jupiter:junit-jupiter")

}

application {
    // Your entry point for Jetty runnable JAR
    mainClass.set("com.aqua.oscore.Application")
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
    archiveFileName.set("libreg.jar")
    archiveClassifier.set("")
    destinationDirectory.set(file("./"))
    mergeServiceFiles()
}


// Default build will produce both JAR and WAR
tasks.named("build") {
    dependsOn(tasks.named("shadowJar"))
}
