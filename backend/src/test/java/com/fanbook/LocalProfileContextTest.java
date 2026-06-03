package com.fanbook;

import static org.assertj.core.api.Assertions.assertThat;

import com.fanbook.common.lock.BookTranslationLock;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.core.env.Environment;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest(properties = {
        "spring.datasource.url=jdbc:h2:mem:local_profile_context;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1",
        "fanbook.storage.root=target/local-profile-storage"
})
@ActiveProfiles("local")
class LocalProfileContextTest {

    @Autowired
    Environment environment;

    @Autowired
    BookTranslationLock lock;

    @Test
    void localProfileUsesEmbeddedDatabaseAndInMemoryLock() {
        assertThat(environment.getProperty("spring.datasource.url")).startsWith("jdbc:h2:");
        assertThat(environment.getProperty("spring.datasource.url")).contains("MODE=MySQL");
        assertThat(environment.getProperty("spring.datasource.driver-class-name")).isEqualTo("org.h2.Driver");
        assertThat(environment.getProperty("management.health.redis.enabled")).isEqualTo("false");
        assertThat(lock.getClass().getSimpleName()).isEqualTo("InMemoryBookTranslationLock");
    }

    @Test
    void localProfileLockUsesInMemoryOwnershipRules() {
        assertThat(lock.acquire(1L, 100L)).isTrue();
        assertThat(lock.acquire(1L, 101L)).isFalse();

        lock.release(1L, 101L);
        assertThat(lock.acquire(1L, 101L)).isFalse();

        lock.release(1L, 100L);
        assertThat(lock.acquire(1L, 101L)).isTrue();
    }
}
