# Java/Kotlin Backend Connection Templates (PG Wire)

## JDBC with HikariCP

```java
// config/DataSourceConfig.java
import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;

public class DataSourceConfig {
    public static DataSource build() {
        HikariConfig config = new HikariConfig();
        config.setJdbcUrl(String.format(
            "jdbc:postgresql://%s:%s/%s?sslmode=require",
            System.getenv("LAKEBASE_HOST"),
            System.getenv().getOrDefault("LAKEBASE_PORT", "5432"),
            System.getenv("LAKEBASE_DB")
        ));
        config.setUsername(System.getenv("LAKEBASE_USER"));
        config.setPassword(TokenRotator.getToken());
        config.setMaximumPoolSize(1);
        config.addDataSourceProperty("sslmode", "require");
        return new HikariDataSource(config);
    }
}
```

The `TokenRotator.getToken()` should implement the same pattern as the Python/Node.js
token rotators in `references/security-backend.md` — calling
`generate_database_credential` via the Databricks Java SDK and caching the result
with a 60-second refresh buffer.
