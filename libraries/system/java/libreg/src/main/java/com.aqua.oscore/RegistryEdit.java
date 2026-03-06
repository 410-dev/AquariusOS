package com.aqua.oscore;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.nio.file.attribute.*;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import java.util.stream.Stream;

public class RegistryEdit {

    // ----------------------------
    // Hive configuration
    // ----------------------------
    private static final String DEFAULT_LOCAL_PATH = ".local/aqua/registry";

    // Using LinkedHashMap to maintain order if necessary, though Map.of is static
    private static final Map<String, String> HIVE_MAP_DEFAULTS = new HashMap<>();
    static {
        HIVE_MAP_DEFAULTS.put("HKEY_LOCAL_MACHINE", "/opt/aqua/registry");
        HIVE_MAP_DEFAULTS.put("HKEY_CURRENT_USER", "$HOME/" + DEFAULT_LOCAL_PATH);
        HIVE_MAP_DEFAULTS.put("HKEY_VOLATILE_MEMORY", "/opt/aqua/vfs/registry");
        HIVE_MAP_DEFAULTS.put("HKEY_LOCAL_MACHINE_NOINST", "/var/noinstfs/aqua/root.d/registry");
    }

    private static final Map<String, String> HIVE_SHORT_MAP = Map.of(
            "HKLM", "HKEY_LOCAL_MACHINE",
            "HKCU", "HKEY_CURRENT_USER",
            "HKVM", "HKEY_VOLATILE_MEMORY",
            "HKNS", "HKEY_LOCAL_MACHINE_NOINST"
    );

    // Priority order: Earlier entries override later ones
    private static final List<String> PRIORITY = List.of("HKVM", "HKCU", "HKLM", "HKNS");

    private static final List<String> TYPES_AVAILABLE = List.of(
            "dword", "qword", "bool", "str", "list", "hex", "float", "double"
    );

    // ----------------------------
    // Internal Helpers
    // ----------------------------

    private static String canonicalHiveName(String name) {
        if (name == null || name.isBlank()) return null;
        name = name.trim();
        if (HIVE_MAP_DEFAULTS.containsKey(name)) return name;
        if (HIVE_SHORT_MAP.containsKey(name)) return HIVE_SHORT_MAP.get(name);
        return null;
    }

    /**
     * Expands environment variables and $HOME/~.
     */
    private static Map<String, String> expandHivePaths(Map<String, String> hiveMap) {
        Map<String, String> out = new HashMap<>();
        Map<String, String> source = (hiveMap != null) ? hiveMap : HIVE_MAP_DEFAULTS;

        String userHome = System.getProperty("user.home");

        for (Map.Entry<String, String> entry : source.entrySet()) {
            String path = entry.getValue();

            // Handle $HOME and ~
            if (path.contains("$HOME")) {
                path = path.replace("$HOME", userHome);
            }
            if (path.startsWith("~")) {
                path = userHome + path.substring(1);
            }

            // Simple env var expansion (Java doesn't have native expandvars like Python)
            // We'll use a regex to look for $VAR or ${VAR}
            Pattern envPattern = Pattern.compile("\\$\\{?([A-Za-z0-9_]+)\\}?");
            Matcher matcher = envPattern.matcher(path);
            StringBuilder sb = new StringBuilder();
            while (matcher.find()) {
                String varName = matcher.group(1);
                String value = System.getenv(varName);
                if (value == null) value = ""; // or keep original? Python expands to empty usually
                matcher.appendReplacement(sb, Matcher.quoteReplacement(value));
            }
            matcher.appendTail(sb);
            path = sb.toString();

            // Normalize path (abspath)
            out.put(entry.getKey(), Paths.get(path).toAbsolutePath().normalize().toString());
        }
        return out;
    }

    private static class HiveSplit {
        String canonicalHive;
        String relativePath;

        HiveSplit(String hive, String rel) {
            this.canonicalHive = hive;
            this.relativePath = rel;
        }
    }

    private static HiveSplit splitHiveAndRel(String registryPath) {
        // remove leading slash
        String p = registryPath.startsWith("/") ? registryPath.substring(1) : registryPath;
        String[] parts = p.split("/", 2);
        String cand = parts[0];
        String canon = canonicalHiveName(cand);

        if (canon != null) {
            String rel = (parts.length > 1) ? parts[1] : "";
            return new HiveSplit(canon, rel);
        }
        return new HiveSplit(null, p);
    }

    private static List<String> valueFileCandidates(String baseNoExt) {
        return TYPES_AVAILABLE.stream()
                .map(t -> baseNoExt + "." + t + ".rv")
                .collect(Collectors.toList());
    }

    private static String detectValueFile(String baseNoExt) {
        for (String f : valueFileCandidates(baseNoExt)) {
            if (Files.isRegularFile(Paths.get(f))) {
                return f;
            }
        }
        return null;
    }

    private static Object readValueFile(String pathStr) {
        Path path = Paths.get(pathStr);
        String data;
        try {
            data = Files.readString(path, StandardCharsets.UTF_8).trim();
        } catch (IOException e) {
            return null;
        }

        if (pathStr.endsWith(".dword.rv") || pathStr.endsWith(".qword.rv")) {
            try { return Long.parseLong(data); } catch (NumberFormatException e) { return 0; }
        }
        if (pathStr.endsWith(".float.rv") || pathStr.endsWith(".double.rv")) {
            try { return Double.parseDouble(data); } catch (NumberFormatException e) { return 0.0; }
        }
        if (pathStr.endsWith(".hex.rv")) {
            try { return Integer.parseInt(data, 16); } catch (NumberFormatException e) { return 0; }
        }
        if (pathStr.endsWith(".list.rv")) {
            String sentinel = UUID.randomUUID().toString().replace("-", "");
            String temp = data.replace("\\,", sentinel);
            String[] items = temp.split(",");
            List<String> list = new ArrayList<>();
            for (String item : items) {
                list.add(item.strip().replace(sentinel, ","));
            }
            return list;
        }
        if (pathStr.endsWith(".bool.rv")) {
            String lower = data.toLowerCase();
            return List.of("1", "true", "yes", "on").contains(lower);
        }
        if (pathStr.endsWith(".str.rv")) {
            return data;
        }
        return data;
    }

    private static void ensureDir(String pathStr) throws IOException {
        Files.createDirectories(Paths.get(pathStr));
    }

    private static List<String> priorityHives() {
        List<String> result = new ArrayList<>();
        for (String shortName : PRIORITY) {
            String canon = canonicalHiveName(shortName);
            if (canon == null) canon = canonicalHiveName(shortName.toUpperCase());
            if (canon != null) {
                result.add(canon);
            }
        }
        return result;
    }

    // ----------------------------
    // Public API
    // ----------------------------

    /**
     * Reads a key or value.
     */
    public static Object read(String registryPath, Object defaultValue, Map<String, String> hiveMap) {
        Map<String, String> expandedMap = expandHivePaths(hiveMap);
        HiveSplit split = splitHiveAndRel(registryPath);

        // Case 1: Explicit Hive
        if (split.canonicalHive != null) {
            String root = expandedMap.get(split.canonicalHive);
            if (root == null) return defaultValue;

            Path base = Paths.get(root, split.relativePath);

            if (Files.isDirectory(base)) {
                Map<String, String> listing = new HashMap<>();
                try (Stream<Path> stream = Files.list(base)) {
                    stream.forEach(path -> {
                        String fname = path.getFileName().toString();
                        if (Files.isRegularFile(path) && fname.endsWith(".rv")) {
                            // Extract name and type
                            // filename format: name.type.rv
                            String[] parts = fname.split("\\.");
                            if (parts.length >= 3) {
                                String name = fname.substring(0, fname.lastIndexOf(".", fname.lastIndexOf(".") - 1));
                                String type = parts[parts.length - 2];
                                listing.put(name, type);
                            }
                        } else if (Files.isDirectory(path)) {
                            listing.put(fname, "key");
                        }
                    });
                } catch (IOException e) {
                    // ignore
                }
                return listing;
            }

            String cand = detectValueFile(base.toString());
            if (cand != null) return readValueFile(cand);
            return defaultValue;
        }

        // Case 2: No hive specified (Priority Search)
        Map<String, String> mergedListing = new HashMap<>();
        List<String> candidates = new ArrayList<>();

        for (String hive : priorityHives()) {
            String root = expandedMap.get(hive);
            if (root == null) continue;
            candidates.add(Paths.get(root, split.relativePath).toString());
        }

        boolean anyDir = candidates.stream().anyMatch(p -> Files.isDirectory(Paths.get(p)));

        if (anyDir) {
            for (String baseStr : candidates) {
                Path base = Paths.get(baseStr);
                if (!Files.isDirectory(base)) continue;

                try (Stream<Path> stream = Files.list(base)) {
                    stream.forEach(path -> {
                        String fname = path.getFileName().toString();
                        if (Files.isRegularFile(path) && fname.endsWith(".rv")) {
                            String[] parts = fname.split("\\.");
                            if (parts.length >= 3) {
                                String name = fname.substring(0, fname.lastIndexOf(".", fname.lastIndexOf(".") - 1));
                                String type = parts[parts.length - 2];
                                // Priority: first hit wins (since we iterate high priority to low in candidates?)
                                // Wait, the Python code iterates priority hives first.
                                // In python: `if name not in merged_listing: merged_listing[name] = type`
                                if (!mergedListing.containsKey(name)) {
                                    mergedListing.put(name, type);
                                }
                            }
                        } else if (Files.isDirectory(path)) {
                            if (!mergedListing.containsKey(fname)) {
                                mergedListing.put(fname, "key");
                            }
                        }
                    });
                } catch (IOException e) { /* ignore */ }
            }
            return mergedListing;
        }

        // Value read search
        for (String base : candidates) {
            String cand = detectValueFile(base);
            if (cand != null) return readValueFile(cand);
        }

        return defaultValue;
    }

    /**
     * Write a value.
     */
    public static void write(String asUser, String registryPath, Object value, Map<String, String> hiveMap, String typeDef) throws IOException {
        Map<String, String> expandedMap = expandHivePaths(hiveMap);
        HiveSplit split = splitHiveAndRel(registryPath);

        String targetHive = (split.canonicalHive != null) ? split.canonicalHive : "HKEY_CURRENT_USER";

        // Ensure HKCU is defined
        if (!expandedMap.containsKey(targetHive) && targetHive.equals("HKEY_CURRENT_USER")) {
            // Should verify against expanded map, but logical fallback isn't provided in python beyond error
        }

        String root = expandedMap.get(targetHive);
        if (root == null) {
            throw new RuntimeException("Hive '" + targetHive + "' has no valid root path.");
        }

        Path baseNoExt = Paths.get(root, split.relativePath);
        Path dirPath = baseNoExt.getParent();
        ensureDir(dirPath.toString());

        // Ownership logic
        UserPrincipal owner = null;
        GroupPrincipal group = null;

        if ("HKEY_CURRENT_USER".equals(targetHive) && asUser != null) {
            // Attempt to resolve user UID/GID logic like Python
            // Python uses `pwd.getpwnam(os.path.basename(user_home))`
            // We'll try to look up by the passed username
            try {
                UserPrincipalLookupService lookupService = FileSystems.getDefault().getUserPrincipalLookupService();
                owner = lookupService.lookupPrincipalByName(asUser);
                // Getting the default group for a user is not standard in Java NIO.
                // We will try to set owner, but group might remain default of the process.
            } catch (IOException e) {
                System.err.println("Warning: Could not lookup user '" + asUser + "'. Ownership might be incorrect.");
            }
        }

        // Apply ownership to directories (recursive chown equivalent for created path parts)
        if ("HKEY_CURRENT_USER".equals(targetHive) && owner != null) {
            // Python logic: walks down from root to target dir
            // We can just attempt to set owner on the target directory for now
            // Note: In strict POSIX, chown requires root privileges.
            try {
                Path relative = Paths.get(root).relativize(dirPath);
                Path current = Paths.get(root);
                for (Path part : relative) {
                    current = current.resolve(part);
                    try {
                        Files.setOwner(current, owner);
                    } catch (FileSystemException | SecurityException e) {
                        // Ignore permission errors as per Python script
                    }
                }
            } catch (Exception e) {
                // Ignore
            }
        }

        // Determine file path and data
        String filePath;
        String data;

        if (typeDef != null) {
            typeDef = typeDef.toLowerCase();
            filePath = baseNoExt.toString() + "." + typeDef + ".rv";
            data = String.valueOf(value);
        } else if (value instanceof Boolean) {
            filePath = baseNoExt.toString() + ".bool.rv";
            data = ((Boolean) value) ? "1" : "0";
        } else if (value instanceof Integer || value instanceof Long) {
            long v = ((Number) value).longValue();
            if (v >= Integer.MIN_VALUE && v <= Integer.MAX_VALUE) {
                filePath = baseNoExt.toString() + ".dword.rv";
            } else {
                filePath = baseNoExt.toString() + ".qword.rv";
            }
            data = String.valueOf(v);
        } else if (value instanceof Float || value instanceof Double) {
            double v = ((Number) value).doubleValue();
            if (Math.abs(v) < 3.4e38) {
                filePath = baseNoExt.toString() + ".float.rv";
            } else {
                filePath = baseNoExt.toString() + ".double.rv";
            }
            data = String.valueOf(v);
        } else if (value instanceof List) {
            filePath = baseNoExt.toString() + ".list.rv";
            List<?> l = (List<?>) value;
            data = l.stream().map(o -> String.valueOf(o).replace(",", "\\,")).collect(Collectors.joining(", "));
        } else {
            // String fallback
            filePath = baseNoExt.toString() + ".str.rv";
            data = String.valueOf(value);
        }

        Path targetFile = Paths.get(filePath);
        Files.writeString(targetFile, data, StandardCharsets.UTF_8);

        // Apply ownership to the file
        if ("HKEY_CURRENT_USER".equals(targetHive) && owner != null) {
            try {
                Files.setOwner(targetFile, owner);
            } catch (IOException | SecurityException e) {
                // Ignore
            }
        }
    }

    /**
     * Delete a value or key.
     */
    public static boolean delete(String registryPath, Map<String, String> hiveMap) {
        Map<String, String> expandedMap = expandHivePaths(hiveMap);
        HiveSplit split = splitHiveAndRel(registryPath);

        String targetHive = (split.canonicalHive != null) ? split.canonicalHive : "HKEY_CURRENT_USER";

        if (!expandedMap.containsKey(targetHive)) return false;
        String root = expandedMap.get(targetHive);
        if (root == null) return false;

        Path target = Paths.get(root, split.relativePath);

        if (Files.isDirectory(target)) {
            // Recursive delete
            try {
                try (Stream<Path> walk = Files.walk(target)) {
                    walk.sorted(Comparator.reverseOrder())
                            .forEach(p -> {
                                try {
                                    Files.delete(p);
                                } catch (IOException e) {
                                    e.printStackTrace();
                                }
                            });
                }
                return true;
            } catch (IOException e) {
                return false;
            }
        }

        // Try deleting value file
        boolean found = false;
        for (String fpath : valueFileCandidates(target.toString())) {
            try {
                if (Files.deleteIfExists(Paths.get(fpath))) {
                    found = true;
                    // Python breaks after first find, assuming only one type exists per key name
                    break;
                }
            } catch (IOException e) {
                // error
            }
        }
        return found;
    }

    // ----------------------------
    // CLI Utility
    // ----------------------------

    public static void main(String[] args) {
        if (args.length < 3) {
            System.out.println("Usage: java com.aqua.oscore.RegistryEdit <user> <action> <registry_path> [type (for write)] [value (for write)]");
            return;
        }

        String user = args[0];
        String action = args[1].toLowerCase();
        String path = args[2];

        // Custom Hive Map for HKCU based on user
        Map<String, String> customHiveMap = new HashMap<>(HIVE_MAP_DEFAULTS);
        // We construct the path manually assuming standard Linux home layout if not resolving actual user home object
        // Note: Python used expanduser(f"~{user}"), in Java we'll assume /home/user or similar if we can't resolve.
        // Or simply assume the runner knows the path. For translation, let's approximate:
        String userHome = (user.equals("root")) ? "/root" : "/home/" + user;
        // A more robust way would involve system calls, but this suffices for translation logic.

        customHiveMap.put("HKEY_CURRENT_USER", userHome + "/" + DEFAULT_LOCAL_PATH);

        try {
            switch (action) {
                case "read":
                    String defVal = (args.length >= 4) ? args[3] : null;
                    Object result = read(path, defVal, customHiveMap);
                    System.out.println(result);
                    break;

                case "write":
                    if (args.length < 5) {
                        System.out.println("Value and type is required for write action.");
                        return;
                    }
                    String typeDef = args[3];
                    String valueStr = args[4];
                    write(user, path, valueStr, customHiveMap, typeDef);
                    System.out.println("Wrote to '" + path + "': " + valueStr);
                    break;

                case "install":
                    if (args.length < 4) {
                        System.out.println("File path is required for install action.");
                        return;
                    }
                    String filePath = args[3];
                    Path p = Paths.get(filePath);
                    if (!Files.exists(p)) {
                        System.out.println("File '" + filePath + "' does not exist.");
                        return;
                    }

                    List<String> lines = Files.readAllLines(p, StandardCharsets.UTF_8);
                    for (String line : lines) {
                        line = line.strip();
                        if (line.isEmpty() || line.startsWith("#")) continue;

                        boolean skipIfExists = false;
                        if (line.startsWith("?")) {
                            skipIfExists = true;
                            line = line.substring(1).strip();
                        }

                        if (line.contains("=")) {
                            String[] kv = line.split("=", 2);
                            String keyPath = kv[0].strip();
                            String rawValue = kv[1].strip();

                            String explicitType = null;
                            if (keyPath.contains(":")) {
                                int idx = keyPath.lastIndexOf(":");
                                explicitType = keyPath.substring(idx + 1);
                                keyPath = keyPath.substring(0, idx).strip();
                            }

                            if (skipIfExists) {
                                Object existing = read(keyPath, null, customHiveMap);
                                if (existing != null) {
                                    System.out.println("Skipping existing key/value '" + keyPath + "'");
                                    continue;
                                }
                            }
                            write(user, keyPath, rawValue, customHiveMap, explicitType);
                            System.out.println("Wrote '" + keyPath + "': " + rawValue);

                        } else {
                            // Key creation
                            String keyPath = line;
                            if (skipIfExists) {
                                Object existing = read(keyPath, null, customHiveMap);
                                if (existing != null) {
                                    System.out.println("Skipping existing key '" + keyPath + "'");
                                    continue;
                                }
                            }
                            // Create dummy and delete to ensure directory exists
                            String dummyPath = (keyPath.endsWith("/") ? keyPath : keyPath + "/") + "__dummy__";
                            write(user, dummyPath, "", customHiveMap, "str");
                            delete(dummyPath, customHiveMap);
                            System.out.println("Created key '" + keyPath + "'");
                        }
                    }
                    break;

                case "delete":
                    boolean ok = delete(path, customHiveMap);
                    System.out.println("Deleted '" + path + "': " + ok);
                    break;

                default:
                    System.out.println("Unknown action: " + action);
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
