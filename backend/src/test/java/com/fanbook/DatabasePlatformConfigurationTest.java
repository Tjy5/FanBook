package com.fanbook;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Properties;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.config.YamlPropertiesFactoryBean;
import org.springframework.core.io.ClassPathResource;

class DatabasePlatformConfigurationTest {

    @Test
    void applicationDefaultsUseMysqlDatasource() {
        Properties properties = loadYaml("application.yml");

        assertThat(properties.getProperty("spring.datasource.url"))
                .contains("jdbc:mysql://localhost:3306/fanbook")
                .doesNotContain("postgresql");
    }

    @Test
    void localProfileUsesH2MysqlCompatibilityMode() {
        Properties properties = loadYaml("application-local.yml");

        assertThat(properties.getProperty("spring.datasource.url"))
                .contains("MODE=MySQL")
                .doesNotContain("MODE=PostgreSQL");
    }

    @Test
    void applicationNormalizesOffsetDateTimeStorageForMysqlDatetimeColumns() {
        Properties properties = loadYaml("application.yml");

        assertThat(properties.getProperty("spring.jpa.properties.hibernate.timezone.default_storage"))
                .isEqualTo("NORMALIZE");
    }

    @Test
    void initialMigrationUsesMysqlDialect() throws IOException {
        String migration = readResource("db/migration/V1__initial_schema.sql");

        assertThat(migration)
                .contains("AUTO_INCREMENT")
                .contains("DATETIME(6)");
        assertThat(migration)
                .doesNotContain("BIGSERIAL")
                .doesNotContain("TIMESTAMP WITH TIME ZONE")
                .doesNotContain("DOUBLE PRECISION")
                .doesNotContain("now()");
    }

    private static Properties loadYaml(String resourcePath) {
        YamlPropertiesFactoryBean factory = new YamlPropertiesFactoryBean();
        factory.setResources(new ClassPathResource(resourcePath));
        return factory.getObject();
    }

    private static String readResource(String resourcePath) throws IOException {
        return new String(new ClassPathResource(resourcePath).getInputStream().readAllBytes(), StandardCharsets.UTF_8);
    }
}
